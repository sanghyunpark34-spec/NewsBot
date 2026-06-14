import os, json, gspread, time
from google import genai
from groq import Groq
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
groq_client = Groq(api_key=os.environ["GROQ_API_KEY"], timeout=15.0)

def get_lookback_days():
    """현재 요일과 실행 방식을 판별하여 1.5일(36시간) 또는 3.5일(84시간) 탐색을 결정합니다."""
    now_kst = datetime.now(KST)
    is_monday = now_kst.weekday() == 0
    is_weekend = now_kst.weekday() in [5, 6]
    is_manual = (os.environ.get("GITHUB_EVENT_NAME", "") == "workflow_dispatch")

    # 월요일, 주말, 수동 실행 시 3.5일(84시간)
    if is_monday or is_weekend or is_manual:
        return 3.5
    # 화~금 일반 워크데이 시 1.5일(36시간)
    return 1.5

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
    
    # --- 1단계: 신규 수집된 기사(DB_Stage)만 AI 평가 진행 및 보관소 저장 ---
    rows = stage_sheet.get_all_values()
    if len(rows) > 1:
        engine = get_engine_setting()
        system_persona, rubric_prompt = get_persona_and_rubric()
        archive_rows = []
        
        for i, row in enumerate(rows[1:]):
            if len(row) < 6: continue
            date, title, url, matched_media, matched_keywords = row[0], row[1], row[2], row[3], row[4]
            try: base_score = float(row[5])
            except: base_score = 0.0
                
            ai_score = 0
            ai_evaluated = False 
            
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
                    
                if scores: 
                    ai_score = sum(scores) / len(scores)
                    ai_evaluated = True 
                time.sleep(5) 
                
            if engine == "AI 사용 안 함":
                total_score = round(base_score, 2)
            else:
                if ai_evaluated:
                    total_score = round((base_score * 0.45) + (ai_score * 0.55), 2)
                else:
                    total_score = 0.0 
                
            archive_rows.append([date, title, url, matched_media, matched_keywords, base_score, ai_score, total_score, 'N'])

        if archive_rows:
            archive_sheet.append_rows(archive_rows)
        # 평가가 끝난 스테이지 시트는 비워줍니다.
        stage_sheet.resize(rows=1) 
        print("신규 수집 기사에 대한 AI 채점 및 보관소(Archive) 이관을 완료했습니다.")

    # --- 2단계: 전체 보관소에서 최근 발행된 기사만 필터링하여 통합 랭킹 산출 ---
    lookback_days = get_lookback_days()
    now_kst_naive = datetime.now(KST).replace(tzinfo=None)
    cutoff_date = now_kst_naive - timedelta(days=lookback_days)
    
    all_archive_records = archive_sheet.get_all_values()[1:] 
    valid_articles = []
    
    for r in all_archive_records:
        if len(r) < 8: continue
        try:
            pub_date = datetime.strptime(r[0], "%Y-%m-%d %H:%M:%S")
            # 발행일이 탐색 기간(24시간/72시간) 이내인 기사만 선별합니다.
            if pub_date >= cutoff_date:
                valid_articles.append(r)
        except: pass
        
    if not valid_articles:
        print("최근 설정된 기간 내에 발행된 기사가 데이터베이스에 존재하지 않습니다.")
        return
        
    # Total_Score 기준으로 강력하게 내림차순 정렬합니다.
    valid_articles.sort(key=lambda x: float(x[7]) if str(x[7]).replace('.', '', 1).isdigit() else 0.0, reverse=True)
    top20_articles = valid_articles[:20]
    
    # DB_Top20 시트에 최종 선발대 기록
    try: 
        top20_sheet = spreadsheet.worksheet("DB_Top20")
    except: 
        top20_sheet = spreadsheet.add_worksheet(title="DB_Top20", rows
