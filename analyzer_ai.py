import os, json, gspread
from google import genai
from groq import Groq
import anthropic
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import pytz

KST = pytz.timezone('Asia/Seoul')

creds = ServiceAccountCredentials.from_json_keyfile_dict(
    json.loads(os.environ["GOOGLE_SHEETS_CREDENTIALS"]),
    ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
)
spreadsheet = gspread.authorize(creds).open("News_Management_DB")

gemini_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])
claude_client = anthropic.Anthropic(api_key=os.environ["CLAUDE_API_KEY"])

def get_persona_and_rubric():
    # (기존 로직 동일)
    default_persona = "당신은 금융 전문가입니다."
    try:
        sys_sheet = spreadsheet.worksheet("Config_System")
        config = {str(r.get("Key")): str(r.get("Value")) for r in sys_sheet.get_all_records()}
        active_opt = config.get("ACTIVE_PERSONA", "옵션 1 (기본 금융 전문가)")
        default_persona = config.get("PERSONA_1", "당신은 냉철한 금융 전문가입니다.") if "옵션 1" in active_opt else config.get("PERSONA_2", "당신은 트렌드에 민감한 기술 전문 투자자입니다.")
    except: pass
    
    rubric_text = "채점 기준:\n"
    try:
        for row in spreadsheet.worksheet("Config_Rubric").get_all_records():
            rubric_text += f"- {row.get('Criteria', '')} (최대 {row.get('Score', 0)}점): {row.get('Description', '')}\n"
    except: pass
    return default_persona, rubric_text

def process_ai_score():
    stage_sheet = spreadsheet.worksheet("DB_Stage")
    archive_sheet = spreadsheet.worksheet("DB_Archive")
    rows = stage_sheet.get_all_values()
    if len(rows) <= 1: return

    engine = "전체" # 배치 처리 시 전체를 던져서 평균을 냅니다.
    system_persona, rubric_prompt = get_persona_and_rubric()
    
    # 💡 20개 기사 묶기
    target_rows = rows[1:21]
    batch_prompt = f"{system_persona}\n\n{rubric_prompt}\n\n다음 20개 기사 제목에 대해 각각 0~100점 사이로 채점해줘.\n형식은 반드시 JSON으로: {{'1': 점수, '2': 점수, ...}}\n\n기사 리스트:\n"
    for i, row in enumerate(target_rows):
        batch_prompt += f"{i+1}. {row[1]}\n"

    scores_map = {}
    
    # 각 엔진 호출 (성공하는 것 위주로 수집)
    for model_name in ["Gemini", "Groq", "Claude"]:
        try:
            res_json = ""
            if model_name == "Gemini":
                res = gemini_client.models.generate_content(model='gemini-3.5-flash', contents=batch_prompt)
                res_json = res.text
            elif model_name == "Groq":
                res = groq_client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": batch_prompt}])
                res_json = res.choices[0].message.content
            elif model_name == "Claude":
                msg = claude_client.messages.create(model="claude-3-5-haiku-20241022", max_tokens=2000, system=system_persona, messages=[{"role": "user", "content": batch_prompt}])
                res_json = msg.content[0].text
            
            # JSON 파싱
            start, end = res_json.find('{'), res_json.rfind('}')
            data = json.loads(res_json[start:end+1])
            for k, v in data.items():
                if k not in scores_map: scores_map[k] = []
                scores_map[k].append((model_name, v))
        except Exception as e: print(f"{model_name} 실패: {e}")

    # 데이터 저장
    archive_rows = []
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
        archive_rows.append([row[0], row[1], row[2], row[3], row[4], base_score, detail_str, total, 'N'])

    archive_sheet.append_rows(archive_rows)
    stage_sheet.resize(rows=1)
    # (이후 탑 20 선별 로직은 동일)
