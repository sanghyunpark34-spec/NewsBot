import os, json, gspread, time
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
groq_client = Groq(api_key=os.environ["GROQ_API_KEY"], timeout=15.0)

# 클로드 클라이언트를 초기화합니다.
claude_client = anthropic.Anthropic(api_key=os.environ.get("CLAUDE_API_KEY", ""))

def get_lookback_days():
    now_kst = datetime.now(KST)
    is_monday = now_kst.weekday() == 0
    is_weekend = now_kst.weekday() in [5, 6]
    is_manual = (os.environ.get("GITHUB_EVENT_NAME", "") == "workflow_dispatch")

    if is_monday or is_weekend or is_manual:
        return 3.5
    return 1.5

def get_engine_setting():
    try:
        sys_sheet = spreadsheet.worksheet("Config_System")
        for row in sys_sheet.get_all_records():
            if row.get("Key") == "AI_ENGINE":
                return row.get("Value")
    except Exception: pass
    return "AI 사용 안 함"

def get_persona_and_rubric():
    default_persona = "당신은 금융 전문가입니다."
    try:
        sys_sheet = spreadsheet.worksheet("Config_System")
        config = {str(r.get("Key")): str(r.get("Value")) for r in sys_sheet.get_all_records()}
        active_opt = config.get("ACTIVE_PERSONA", "옵션 1 (기본 금융 전문가)")
        
        if "옵션 1" in active_opt:
            default_persona = config.get("PERSONA_1", "당신은 냉철한 금융 전문가입니다.")
        else:
            default_persona = config.get("PERSONA_2", "당신은 트렌드에 민감한 기술 전문 투자자입니다.")
    except Exception:
        pass

    rubric_text = "채점 기준:\n"
    try:
        records = spreadsheet.worksheet("Config_Rubric").get_all_records()
        for row in records:
            criteria = row.get('평가 기준', row.get('Criteria', ''))
            desc = row.get('상세 설명', row.get('Description', ''))
            score = row.get('배점', row.get('Score', 0))
            if criteria and criteria.lower() != 'type':
                rubric_text += f"- {criteria} (최대 {score}점): {desc}\n"
    except Exception: pass
    return default_persona, rubric_text

def process_ai_score():
    stage_sheet = spreadsheet.worksheet("DB_Stage")
    archive_sheet = spreadsheet.worksheet("DB_Archive")
    
    rows = stage_sheet.get_all_values()
    if len(rows) > 1:
        engine = get_engine_setting()
        system_persona, rubric_prompt = get_persona_and_rubric()
        archive_rows = []
        
        for i, row in enumerate(rows[1:]):
            if len(row) < 6: continue
            date, title, url, matched_media, matched_keywords = row[0], row[1], row[2], row[3], row[4]
            try: base_score = float(row[5])
            except Exception: base_score = 0.0
                
            engine_scores = {}
            ai_evaluated = False 
            
            if i < 20 and base_score > 0 and engine != "AI 사용 안 함":
                print(f"\n분석 시작 [{engine}]: {title[:18]}...", flush=True)
                evaluation_prompt = f"{rubric_prompt}\n\n기사 제목: {title}\n\n위 기사를 평가 기준에 따라 분석하고, 최종 점수를 0에서 100 사이의 숫자만으로 대답해주세요."
                
                if engine == "무료 Gemini" or engine == "전체":
                    try:
                        gemini_prompt = f"{system_persona}\n\n{evaluation_prompt}"
                        res = gemini_client.models.generate_content(model='gemini-3.5-flash', contents=gemini_prompt)
                        score_text = ''.join(filter(str.isdigit, res.text))
                        if score_text:
                            engine_scores["Gemini"] = min(int(score_text), 100)
                    except Exception: pass
                
                if engine == "무료 Groq" or engine == "전체":
                    try:
                        groq_prompt = f"{system_persona}\n\n{evaluation_prompt}"
                        res = groq_client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": groq_prompt}], max_tokens=10)
                        score_text = ''.join(filter(str.isdigit, res.choices[0].message.content))
                        if score_text:
                            engine_scores["Groq"] = min(int(score_text), 100)
                    except Exception: pass

                if engine == "유료 Claude" or engine == "전체":
                    try:
                        msg = claude_client.messages.create(
                            model="claude-haiku-4-5-20251001",
                            max_tokens=10,
                            system=system_persona,
                            messages=[{"role": "user", "content": evaluation_prompt}]
                        )
                        score_text = ''.join(filter(str.isdigit, msg.content[0].text))
                        if score_text:
                            engine_scores["Claude"] = min(int(score_text), 100)
                    except Exception as e:
                        print(f"Claude 엔진 호출 중 오류가 발생했습니다. 내용은 {e} 입니다.")
                    
                if engine_scores: 
                    ai_score_avg = sum(engine_scores.values()) / len(engine_scores)
                    details_list = []
                    for k, v in engine_scores.items():
                        details_list.append(f"{k} {v}")
                    details_str = ", ".join(details_list)
                    ai_score_formatted = f"{round(ai_score_avg, 1)} ({details_str})"
                    ai_evaluated = True 
                else:
                    ai_score_formatted = "0"
                
                time.sleep(5) 
                
            if engine == "AI 사용 안 함":
                total_score = round(base_score, 2)
                ai_score_formatted = "0"
            else:
                if ai_evaluated:
                    total_score = round((base_score * 0.45) + (ai_score_avg * 0.55), 2)
                else:
                    total_score = 0.0 
                    ai_score_formatted = "0"
                
            archive_rows.append([date, title, url, matched_media, matched_keywords, base_score, ai_score_formatted, total_score, 'N'])

        if archive_rows:
            archive_sheet.append_rows(archive_rows)
        stage_sheet.resize(rows=1) 
        print("신규 수집 기사에 대한 AI 채점 및 보관소 이관을 완료했습니다.")

    lookback_days = get_lookback_days()
    now_kst_naive = datetime.now(KST).replace(tzinfo=None)
    cutoff_date = now_kst_naive - timedelta(days=lookback_days)
    
    all_archive_records = archive_sheet.get_all_values()[1:] 
    valid_articles = []
    
    for r in all_archive_records:
        if len(r) < 8: continue
        try:
            pub_date = datetime.strptime(r[0], "%Y-%m-%d %H:%M:%S")
            if pub_date >= cutoff_date:
                valid_articles.append(r)
        except Exception: pass
        
    if not valid_articles:
        print("최근 설정된 기간 내에 발행된 기사가 데이터베이스에 존재하지 않습니다.")
        return
        
    valid_articles.sort(key=lambda x: float(x[7]) if str(x[7]).replace('.', '', 1).isdigit() else 0.0, reverse=True)
    top20_articles = valid_articles[:20]
    
    try: 
        top20_sheet = spreadsheet.worksheet("DB_Top20")
    except Exception: 
        top20_sheet = spreadsheet.add_worksheet(title="DB_Top20", rows="5000", cols="10")
        top20_sheet.append_row(["Execution_Time", "Date", "Title", "Link", "Media", "Matched_Keywords", "Base_Score", "AI_Score", "Total_Score", "Sent"])
        
    exec_time = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    top20_rows = [[exec_time] + r for r in top20_articles]
    
    top20_sheet.append_rows(top20_rows)
    print(f"최근 기준 통합 탑 20 기사 선별 및 저장이 완료되었습니다.")

if __name__ == "__main__":
    process_ai_score()
