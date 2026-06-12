import os, json, gspread, time
from google import genai
from groq import Groq
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz

KST = pytz.timezone('Asia/Seoul')

creds = ServiceAccountCredentials.from_json_keyfile_dict(
    json.loads(os.environ["GOOGLE_SHEETS_CREDENTIALS"]),
    ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
)
spreadsheet = gspread.authorize(creds).open("News_Management_DB")

gemini_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
groq_client = Groq(api_key=os.environ["GROQ_API_KEY"], timeout=15.0)

def get_engine_setting():
    try:
        sys_sheet = spreadsheet.worksheet("Config_System")
        for row in sys_sheet.get_all_records():
            if row.get("Key") == "AI_ENGINE":
                return row.get("Value")
    except: pass
    return "AI 사용 안 함"

def get_persona_and_rubric():
    default_persona = "당신은 금융 전문가입니다."
    rubric_text = "채점 기준:\n"
    try:
        records = spreadsheet.worksheet("Config_Rubric").get_all_records()
        for row in records:
            if str(row.get('Type', '')).strip().lower() == 'base':
                default_persona = str(row.get('Persona', default_persona)).strip()
            criteria = row.get('평가 기준', row.get('Criteria', ''))
            desc = row.get('상세 설명', row.get('Description', ''))
            score = row.get('배점', row.get('Score', 0))
            if criteria and criteria.lower() != 'type':
                rubric_text += f"- {criteria} (최대 {score}점): {desc}\n"
    except: pass
    return default_persona, rubric_text

def process_ai_score():
    stage_sheet = spreadsheet.worksheet("DB_Stage")
    archive_sheet = spreadsheet.worksheet("DB_Archive")
    
    try: archive_sheet.resize(rows=1)
    except: pass
    
    rows = stage_sheet.get_all_values()
    if len(rows) <= 1: return

    engine = get_engine_setting()
    system_persona, rubric_prompt = get_persona_and_rubric()
    archive_rows = []
    
    for i, row in enumerate(rows[1:]):
        if len(row) < 5: continue
        date, title, url, matched_media = row[0], row[1], row[2], row[3]
        try: base_score = float(row[4])
        except: base_score = 0.0
            
        ai_score = 0
        if i < 20 and base_score > 0 and engine != "AI 사용 안 함":
            print(f"\n분석 시작 [{engine}]: {title[:18]}...", flush=True)
            prompt = f"{system_persona}\n\n{rubric_prompt}\n\n기사 제목: {title}"
            
            scores = []
            if engine == "무료 Gemini" or engine == "전체":
                try:
                    res = gemini_client.models.generate_content(model='gemini-3.5-flash', contents=prompt)
                    score_text = ''.join(filter(str.isdigit, res.text))
                    scores.append(min(int(score_text), 100))
                except: pass
            
            if engine == "무료 Groq" or engine == "전체":
                try:
                    res = groq_client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}], max_tokens=10)
                    score_text = ''.join(filter(str.isdigit, res.choices[0].message.content))
                    scores.append(min(int(score_text), 100))
                except: pass
                
            if scores: ai_score = sum(scores) / len(scores)
            time.sleep(5) 
            
        if engine == "AI 사용 안 함":
            total_score = round(base_score, 2)
        else:
            total_score = round((base_score * 0.45) + (ai_score * 0.55), 2) if ai_score > 0 else round(base_score, 2)
            
        archive_rows.append([date, title, url, matched_media, base_score, ai_score, total_score, 'N'])

    if archive_rows:
        archive_sheet.append_rows(archive_rows)
        try: top20_sheet = spreadsheet.worksheet("DB_Top20")
        except: top20_sheet = spreadsheet.add_worksheet(title="DB_Top20", rows="5000", cols="9")
        exec_time = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
        top20_sheet.append_rows([[exec_time] + r for r in archive_rows])

    stage_sheet.resize(rows=1)

if __name__ == "__main__":
    process_ai_score()
