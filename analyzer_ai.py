import os, json, gspread, time
from google import genai
from groq import Groq
from oauth2client.service_account import ServiceAccountCredentials

creds = ServiceAccountCredentials.from_json_keyfile_dict(
    json.loads(os.environ["GOOGLE_SHEETS_CREDENTIALS"]),
    ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
)
spreadsheet = gspread.authorize(creds).open("News_Management_DB")

gemini_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
groq_client = Groq(api_key=os.environ["GROQ_API_KEY"], timeout=15.0)

def get_rubric_text():
    try:
        rubric_sheet = spreadsheet.worksheet("Config_Rubric")
        records = rubric_sheet.get_all_records()
        rubric_text = "다음은 기사 제목을 평가할 상세 채점 기준입니다.\n\n"
        for row in records:
            criteria = row.get('평가 기준', row.get('Criteria', ''))
            desc = row.get('상세 설명', row.get('Description', ''))
            score = row.get('배점', row.get('Score', 0))
            if criteria:
                rubric_text += f"- {criteria} (최대 {score}점): {desc}\n"
        return rubric_text
    except Exception as e:
        return "자본 시장 동향 및 금융업 인수합병 관련성을 기준으로 평가해 주세요."

def evaluate_with_gemini(prompt):
    try:
        response = gemini_client.models.generate_content(model='gemini-3.5-flash', contents=prompt)
        score_text = ''.join(filter(str.isdigit, response.text))
        return min(int(score_text), 100) if score_text else None
    except: return None

def evaluate_with_groq(prompt):
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10, temperature=0.1
        )
        score_text = ''.join(filter(str.isdigit, response.choices[0].message.content))
        return min(int(score_text), 100) if score_text else None
    except: return None

def process_ai_score():
    stage_sheet = spreadsheet.worksheet("DB_Stage")
    archive_sheet = spreadsheet.worksheet("DB_Archive")
    
    rows = stage_sheet.get_all_values()
    if len(rows) <= 1: return

    rubric_prompt = get_rubric_text()
    archive_rows = []
    
    # AI에게 금융/M&A 전문가 역할을 강제 부여하여 분석의 질을 대폭 끌어올립니다.
    system_persona = (
        "당신은 금융/보험업계의 M&A, 대체투자 및 기업 전략 기획을 담당하는 최고 전문가입니다. "
        "주어진 기준에 따라 이 기사가 당사의 자본 전략, 경쟁사 동향 파악, 또는 거시경제 리스크 관리에 "
        "얼마나 중요한 인사이트를 주는지 100점 만점으로 변환하여 숫자만 대답하세요."
    )
    
    for i, row in enumerate(rows[1:]):
        if len(row) < 5: continue
        date, title, url, matched_media = row[0], row[1], row[2], row[3]
        try: base_score = float(row[4])
        except: base_score = 0.0
            
        if i < 20 and base_score >= 20: 
            print(f"\n[{i+1}/20] AI 분석 중 (Base: {base_score}): {title[:20]}...", flush=True)
            evaluation_prompt = f"{system_persona}\n\n{rubric_prompt}\n\n기사 제목: {title}"
            
            gemini_score = evaluate_with_gemini(evaluation_prompt)
            groq_score = evaluate_with_groq(evaluation_prompt)
            
            scores = [s for s in [gemini_score, groq_score] if s is not None]
            if scores:
                ai_score = sum(scores) / len(scores)
                print(f"  ✅ AI 점수: {ai_score}", flush=True)
            else:
                ai_score = 0
                print(f"  ❌ AI 실패", flush=True)
            time.sleep(15) 
        else: 
            ai_score = 0
            
        # 정확한 비율 적용: AI 점수가 있으면 Base 45% + AI 55%
        if ai_score > 0:
            total_score = round((base_score * 0.45) + (ai_score * 0.55), 2)
        else:
            total_score = round(base_score, 2)
            
        archive_rows.append([date, title, url, matched_media, base_score, ai_score, total_score, 'N'])

    if archive_rows:
        archive_sheet.append_rows(archive_rows)
    stage_sheet.resize(rows=1)
    print("\n🎉 인공지능 분석 완료.", flush=True)

if __name__ == "__main__":
    process_ai_score()
