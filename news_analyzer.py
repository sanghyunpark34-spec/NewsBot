import gspread
import json
import os
import requests
from bs4 import BeautifulSoup # 뉴스 본문을 긁어오는 도구
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

def get_news_data(url):
    """뉴스 URL에서 제목과 본문을 자동으로 추출"""
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # 네이버 뉴스 외의 일반 경제지 기사(뉴스토마토 등)의 제목/본문 태그 찾기
    # 일반적인 기사 페이지는 <title>이나 특정 클래스를 사용합니다.
    title = soup.select_one('h1.tit').text.strip() if soup.select_one('h1.tit') else soup.title.string
    content = soup.select_one('div.news_content').text.strip() if soup.select_one('div.news_content') else soup.get_text()
    
    return title, content[:2000] # 토큰 제한을 위해 본문은 2000자까지만 가져오기

# 실행부
test_url = "https://www.newstomato.com/ReadNews.aspx?no=1303051"
title, content = get_news_data(test_url)
rubric_data = spreadsheet.worksheet("Config_Rubric").get_all_records()

result = analyze_article(title, content, rubric_data)
print(f"추출된 제목: {title}")
print(f"분석 결과: {result}")
