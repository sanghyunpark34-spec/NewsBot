import gspread
import json
import os
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# 1. 설정 및 인증
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(os.environ["GOOGLE_SHEETS_CREDENTIALS"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
spreadsheet = client.open("News_Management_DB")

# Gemini API 설정
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-3.5-flash')

def analyze_article(title, content, rubric):
    rubric_str = "\n".join([f"- {r['Criteria']}: {r['Description']} (점수: {r['Score']})" for r in rubric])
    prompt = f"""
    당신은 금융 전략가입니다. 다음 기사를 분석하여 점수를 매겨주세요.
    기준표:
    {rubric_str}
    
    기사 제목: {title}
    기사 본문: {content}
    
    반드시 JSON 형식으로만 응답하세요. (마크다운 코드 블록 제외하고 오직 JSON 텍스트만)
    {{"reasoning": "점수 산정 근거", "total_score": "총점"}}
    """
    response = model.generate_content(prompt)
    text = response.text.replace("```json", "").replace("```", "").strip()
    return json.loads(text)

def get_news_data(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    title = soup.select_one('h1.tit').text.strip() if soup.select_one('h1.tit') else soup.title.string
    content = soup.select_one('div.news_content').text.strip() if soup.select_one('div.news_content') else soup.get_text()
    return title, content[:2000]

# --- 실행부 ---
test_url = "https://www.newstomato.com/ReadNews.aspx?no=1303051"
title, content = get_news_data(test_url)
rubric_data = spreadsheet.worksheet("Config_Rubric").get_all_records()
result = analyze_article(title, content, rubric_data)

# 기록
date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
db_sheet = spreadsheet.worksheet("DB_Archive")
db_sheet.append_row([date_str, title, test_url, "뉴스토마토", "분석완료", result['total_score'], result['reasoning']])

print(f"분석 완료: {title}")
print("결과가 DB_Archive 시트에 기록되었습니다.")
