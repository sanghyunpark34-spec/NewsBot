import os, json, gspread
import time
from datetime import datetime
import pytz
from oauth2client.service_account import ServiceAccountCredentials

KST = pytz.timezone('Asia/Seoul')

# 1. 안전한 API 키 로드 (키가 없어도 프로그램이 뻗지 않도록 방어)
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
GROQ_KEY = os.environ.get("GROQ_API_KEY", "")
CLAUDE_KEY = os.environ.get("CLAUDE_API_KEY", "")

# 각 AI 라이브러리 안전 임포트 (버전 충돌 무시)
try:
    import google.generativeai as genai
    if GEMINI_KEY: genai.configure(api_key=GEMINI_KEY)
except ImportError:
    genai = None

try:
    from groq import Groq
    groq_client = Groq(api_key=GROQ_KEY) if GROQ_KEY else None
except ImportError:
    groq_client = None

try:
    import anthropic
    claude_client = anthropic.Anthropic(api_key=CLAUDE_KEY) if CLAUDE_KEY else None
except ImportError:
    claude_client = None

# 구글 시트 연결
creds = ServiceAccountCredentials.from_json_keyfile_dict(
    json.loads(os.environ["GOOGLE_SHEETS_CREDENTIALS"]),
    ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
)
spreadsheet = gspread.authorize(creds).open("News_Management_DB")

def get_persona_and_rubric():
    sys_sheet = spreadsheet.worksheet("Config_System")
    config = {str(r.get("Key")): str(r.get("Value")) for r in sys_sheet.get_all_records()}
    active_opt = config.get("ACTIVE_PERSONA", "옵션 1 (기본 금융 전문가)")
    default_persona = config.get("PERSONA_1", "당신은 냉철한 금융 전문가입니다.") if "옵션 1" in active_opt else config.get("PERSONA_2", "당신은 트렌드에 민감한 기술 전문 투자자입니다.")
    
    rubric_text = "채점 기준:\n"
    try:
        for row in spreadsheet.worksheet("Config_Rubric").get_all_records():
            rubric_text += f"- {row.get('Criteria', '')} (최대 {row.get('Score', 0)}점): {row.get('Description', '')}\n"
    except: pass
    return default_persona, rubric_text

def process_ai_score():
    print("🤖 AI 분석(배치 처리)을 시작합니다...")
    stage_sheet = spreadsheet.worksheet("DB_Stage")
    archive_sheet = spreadsheet.worksheet("DB_Archive")
    
    rows = stage_sheet.get_all_values()
    if len(rows) <= 1:
        print("⚠️ DB_Stage에 분석할 기사가 없습니다.")
        return

    # 대시보드 시스템 설정에서 선택한 엔진 가져오기
    try:
        sys_sheet = spreadsheet.worksheet("Config_System")
        config = {str(r.get("Key")): str(r.get("Value")) for r in sys_sheet.get_all_records()}
        engine_choice = config.get("AI_ENGINE", "전체")
    except:
        engine_choice = "전체"

    system_persona, rubric_prompt = get_persona_and_rubric()
    
    # 💡 최상위 20개 기사만 선별하여 한 번에 채점
    target_rows = rows[1:21]
    print(f"📊 총 {len(target_rows)}개의 기사를 선별하여 AI에게 한 번에 채점을 요청합니다. (선택된 엔진: {engine_choice})")

    batch_prompt = f"{system_persona}\n\n{rubric_prompt}\n\n다음 {len(target_rows)}개 기사 제목에 대해 각각 0~100점 사이로 채점해줘.\n형식은 반드시 JSON으로: {{'1': 점수, '2': 점수, ...}}\n\n기사 리스트:\n"
    for i, row in enumerate(target_rows):
        batch_prompt += f"{i+1}. {row[1]}\n"

    scores_map = {}
    engines_to_run = []
    
    if "Gemini" in engine_choice or "전체" in engine_choice: engines_to_run.append("Gemini")
    if "Groq" in engine_choice or "전체" in engine_choice: engines_to_run.append("Groq")
    if "Claude" in engine_choice or "전체" in engine_choice: engines_to_run.append("Claude")

    if not engines_to_run or engine_choice == "AI 사용 안 함":
        print("⚠️ AI 엔진이 선택되지 않았습니다. 기초 점수만으로 아카이브에 이관합니다.")
    else:
        for model_name in engines_to_run:
            print(f"🚀 {model_name} 엔진에 20개 기사 채점 요청 중...")
            try:
                res_json = ""
                if model_name == "Gemini" and genai:
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    res = model.generate_content(batch_prompt)
                    res_json = res.text
                elif model_name == "Groq" and groq_client:
                    res = groq_client.chat.completions.create(model="llama3-70b-8192", messages=[{"role": "user", "content": batch_prompt}])
                    res_json = res.choices[0].message.content
                elif model_name == "Claude" and claude_client:
                    msg = claude_client.messages.create(model="claude-haiku-4-5-20251001", max_tokens=2000, system=system_persona, messages=[{"role": "user", "content": batch_prompt}])
                    res_json = msg.content[0].text
                
                # 결과물에서 JSON만 깔끔하게 파싱
                if res_json:
                    start, end = res_json.find('{'), res_json.rfind('}')
                    if start != -1 and end != -1:
                        data = json.loads(res_json[start:end+1])
                        for k, v in data.items():
                            if k not in scores_map: scores_map[k] = []
                            scores_map[k].append((model_name, int(v)))
                        print(f"✅ {model_name} 엔진 채점 완벽 성공!")
                    else:
                        print(f"❌ {model_name} 응답에서 점수를 찾을 수 없습니다.")
            except Exception as e:
                print(f"❌ {model_name} 엔진 에러 발생 (스킵합니다): {e}")

    # 최종 점수 병합 및 DB 저장
    archive_rows = []
    now_str = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    
    for i, row in enumerate(target_rows):
        idx_str = str(i+1)
        base_score = float(row[5])
        details = scores_map.get(idx_str, [])
        if details:
            avg = sum([d[1] for d in details]) / len(details)
            detail_str = f"{round(avg, 1)} ({', '.join([f'{d[0]} {d[1]}' for d in details])})"
            total = round((base_score * 0.45) + (avg * 0.55), 2)
        else:
            detail_str, total = "0", base_score
        
        # 새로운 시간, 제목, 링크, 매체, 키워드, 기초점수, AI상세, 총점, 발송여부
        archive_rows.append([now_str, row[1], row[2], row[3], row[4], base_score, detail_str, total, 'N'])

    if archive_rows:
        archive_sheet.append_rows(archive_rows)
        print(f"💾 총 {len(archive_rows)}개의 기사를 DB_Archive에 성공적으로 영구 저장했습니다.")
    
    stage_sheet.resize(rows=1) # 대기실 비우기
    print("🏁 AI 분석 및 이관 작업이 모두 완료되었습니다.")

if __name__ == "__main__":
    process_ai_score()
