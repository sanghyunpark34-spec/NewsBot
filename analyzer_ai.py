import os, json, gspread
import time
from datetime import datetime
import pytz
from oauth2client.service_account import ServiceAccountCredentials

KST = pytz.timezone('Asia/Seoul')

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
GROQ_KEY = os.environ.get("GROQ_API_KEY", "")
CLAUDE_KEY = os.environ.get("CLAUDE_API_KEY", "")

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
    
    # 💡 DB_AI_Report 시트 준비 (Top20을 대체하는 명확한 기준의 시트)
    try:
        ai_report_sheet = spreadsheet.worksheet("DB_AI_Report")
    except:
        ai_report_sheet = spreadsheet.add_worksheet(title="DB_AI_Report", rows="1000", cols="8")
        ai_report_sheet.append_row(["Execution_Time", "Date", "Title", "Link", "Media", "Matched_Keywords", "Total_Score", "Sent"])
    
    rows = stage_sheet.get_all_values()
    if len(rows) <= 1:
        print("⚠️ DB_Stage에 분석할 기사가 없습니다.")
        return

    try:
        sys_sheet = spreadsheet.worksheet("Config_System")
        config = {str(r.get("Key")): str(r.get("Value")) for r in sys_sheet.get_all_records()}
        engine_choice = config.get("AI_ENGINE", "전체")
    except:
        engine_choice = "전체"

    system_persona, rubric_prompt = get_persona_and_rubric()
    
    # 현재는 속도/비용 최적화를 위해 상위 20개만 AI에게 보냅니다. (이 숫자는 나중에 언제든 조절 가능)
    target_rows = rows[1:21]
    remaining_rows = rows[21:]
    
    print(f"📊 총 {len(rows)-1}개의 통과 기사 중, 상위 {len(target_rows)}개 그룹만 AI에게 평가를 요청합니다.")

    batch_prompt = f"{system_persona}\n\n{rubric_prompt}\n\n다음 {len(target_rows)}개 기사 제목에 대해 각각 0~100점 사이로 채점해줘.\n형식은 반드시 JSON으로: {{'1': 점수, '2': 점수, ...}}\n\n기사 리스트:\n"
    for i, row in enumerate(target_rows):
        batch_prompt += f"{i+1}. {row[1]}\n"

    scores_map = {}
    engines_to_run = []
    
    if "Gemini" in engine_choice or "전체" in engine_choice: engines_to_run.append("Gemini")
    if "Groq" in engine_choice or "전체" in engine_choice: engines_to_run.append("Groq")
    if "Claude" in engine_choice or "전체" in engine_choice: engines_to_run.append("Claude")

    if not engines_to_run or engine_choice == "AI 사용 안 함":
        print("⚠️ AI 엔진이 선택되지 않았습니다.")
    else:
        for model_name in engines_to_run:
            print(f"🚀 {model_name} 엔진에 채점 요청 중...")
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
                
                if res_json:
                    start, end = res_json.find('{'), res_json.rfind('}')
                    if start != -1 and end != -1:
                        data = json.loads(res_json[start:end+1])
                        for k, v in data.items():
                            if k not in scores_map: scores_map[k] = []
                            scores_map[k].append((model_name, int(v)))
                        print(f"✅ {model_name} 채점 완료!")
            except Exception as e:
                print(f"❌ {model_name} 에러 (스킵): {e}")

    archive_rows = []
    ai_report_rows = [] # 💡 AI 평가를 받은 기사들만 모이는 전용 리스트
    now_str = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    
    # 1. AI 평가를 받은 그룹 처리 (Archive + AI_Report 양쪽 모두 저장)
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
        
        # Archive 보존용 (모든 상세 데이터)
        archive_rows.append([now_str, row[1], row[2], row[3], row[4], base_score, detail_str, total, 'N'])
        
        # 💡 AI_Report 발송 대기용 (텔레그램이 요구하는 필수 규격)
        ai_report_rows.append([now_str, row[0], row[1], row[2], row[3], row[4], total, 'N'])

    # 2. AI 평가를 받지 못한 나머지 그룹 처리 (Archive에만 조용히 보존)
    for row in remaining_rows:
        base_score = float(row[5])
        archive_rows.append([now_str, row[1], row[2], row[3], row[4], base_score, "AI 미평가 (순위 밖)", base_score, 'N'])

    # 시트 업데이트
    if archive_rows:
        archive_sheet.append_rows(archive_rows)
        print(f"💾 총 {len(archive_rows)}개의 전체 기사를 DB_Archive에 영구 저장했습니다.")
        
    if ai_report_rows:
        # AI 평가 총점을 기준으로 가장 높은 기사가 위로 오도록 정렬
        ai_report_rows.sort(key=lambda x: float(x[6]), reverse=True)
        ai_report_sheet.append_rows(ai_report_rows)
        print(f"🎯 AI 평가가 완료된 {len(ai_report_rows)}개의 기사를 DB_AI_Report 발송 대기열에 등록했습니다.")
    
    stage_sheet.resize(rows=1) # 작업이 끝난 Stage는 깨끗하게 초기화
    print("🏁 AI 분석 및 이관 작업이 모두 완료되었습니다.")

if __name__ == "__main__":
    process_ai_score()
