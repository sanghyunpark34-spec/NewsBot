import gspread
import json
import os
import google.generativeai as genai
from oauth2client.service_account import ServiceAccountCredentials

# 1. 설정 및 인증
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(os.environ["GOOGLE_SHEETS_CREDENTIALS"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
spreadsheet = client.open("News_Management_DB")

# Gemini API 설정
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-1.5-flash')

def analyze_article(title, content, rubric):
    rubric_str = "\n".join([f"- {r['Criteria']}: {r['Description']} (점수: {r['Score']})" for r in rubric])
    prompt = f"""
    당신은 금융 전략가입니다. 다음 기사를 분석하여 점수를 매겨주세요.
    기준표:
    {rubric_str}
    
    기사 제목: {title}
    기사 본문: {content}
    
    반드시 JSON 형식으로만 응답하세요:
    {{"reasoning": "점수 산정 근거", "total_score": "총점"}}
    """
    response = model.generate_content(prompt)
    return json.loads(response.text)

# 2. 루브릭 가져오기
rubric_data = spreadsheet.worksheet("Config_Rubric").get_all_records()

# 3. 테스트 (실제 기사 제목/본문을 넣어서 테스트 가능)
# result = analyze_article("테스트 제목", "테스트 본문 내용", rubric_data)
# print(result)
print("분석 엔진 로직 준비 완료!")
