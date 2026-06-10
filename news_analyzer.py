import gspread
import json
import os
import requests
import time
import pytz
from bs4 import BeautifulSoup
import google.generativeai as genai
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from google.api_core import exceptions

# 1. 설정 및 인증
creds_dict = json.loads(os.environ["GOOGLE_SHEETS_CREDENTIALS"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(
    creds_dict, ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
)
spreadsheet = gspread.authorize(creds).open("News_Management_DB")
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-1.5-flash') # 안정적인 1.5 버전 권장

def get_news_data(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    title = soup.select_one('h1.tit').text.strip() if soup.select_one('h1.tit') else soup.title.string
    content = soup.select_one('div.news_content').text.strip() if soup.select_one('div.news_content') else soup.get_text()
    return title, content[:2000]

def process_inbox():
    inbox_sheet = spreadsheet.worksheet("DB_Inbox")
    archive_sheet = spreadsheet.worksheet("DB_Archive")
    
    # 1. 수집된 모든 기사 가져오기
    rows = inbox_sheet.get_all_records()
    if not rows:
        print("분석할 기사가 없습니다.")
        return

    # 2. 기사 하나씩 순회하며 분석
    for row in rows:
        url = row['Link'] # 시트 헤더가 Link라고 가정
        
        # 중복 분석 방지 (이미 Archive에 있는지 확인)
        if url in archive_sheet.col_values(3):
            print(f"이미 분석됨: {url}")
            inbox_sheet.delete_rows(2) # 분석된 건 Inbox에서 제거
            continue
            
        # 3. 분석 수행 (기존 AI 분석 및 점수 로직 사용)
        # ... [analyze_article 또는 계산 로직] ...
        
        # 4. 분석 결과 저장 후 Inbox에서 삭제
        # ... [archive_sheet.append_row(...)] ...
        inbox_sheet.delete_rows(2)
        print(f"분석 완료 및 삭제: {url}")
        time.sleep(2) # API 호출 간격 확보

if __name__ == "__main__":
    process_inbox()

def get_ai_keywords(title, content, keyword_list):
    prompt = f"""
    기사 제목: {title}
    기사 본문: {content}
    참고 키워드 리스트: {keyword_list}
    
    위 기사에서 핵심 키워드 5개를 뽑아주세요. 
    JSON 형식: {{"keywords": ["키워드1", ..., "키워드5"]}}
    """
    
    # 재시도 로직 (최대 3회)
    for attempt in range(3):
        try:
            response = model.generate_content(prompt)
            text = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(text).get("keywords", [])
        except exceptions.ResourceExhausted:
            print(f"쿼터 초과! {attempt+1}번째 시도 실패. 60초 대기 후 재시도...")
            time.sleep(60) # 60초 대기
        except Exception as e:
            print(f"오류 발생: {e}")
            break
    return []

def calculate_score(ai_keywords, rubric_keywords, media_weight):
    sorted_keywords = sorted(rubric_keywords.items(), key=lambda x: int(x[1]), reverse=True)
    top_4_keywords = sorted_keywords[:4] 
    
    total_score = 0
    matched_keywords = []
    
    for ai_kw in ai_keywords:
        for official_kw, coeff in top_4_keywords:
            if official_kw in ai_kw:
                total_score += int(coeff)
                matched_keywords.append(f"{ai_kw}({official_kw})")
                
    total_score += int(media_weight)
    return total_score, matched_keywords

# --- 실행부 ---
rubric_keywords = {r['Keyword']: r['Coefficient'] for r in spreadsheet.worksheet("Config_Keywords").get_all_records()}
media_data = {r['Domain']: r['Weight'] for r in spreadsheet.worksheet("Config_Media").get_all_records()}

test_url = "https://www.newstomato.com/ReadNews.aspx?no=1303051"
title, content = get_news_data(test_url)

ai_keywords = get_ai_keywords(title, content, list(rubric_keywords.keys()))
media_weight = next((val for dom, val in media_data.items() if dom in test_url), 0)
final_score, matches = calculate_score(ai_keywords, rubric_keywords, media_weight)

spreadsheet.worksheet("DB_Archive").append_row([
    datetime.now().strftime("%Y-%m-%d %H:%M:%S"), title, test_url, 
    ", ".join(ai_keywords), ", ".join(matches), final_score
])

print(f"분석 완료: {title} | 최종점수: {final_score}")
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# 1. 설정 및 인증
creds_dict = json.loads(os.environ["GOOGLE_SHEETS_CREDENTIALS"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(
    creds_dict, ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
)
spreadsheet = gspread.authorize(creds).open("News_Management_DB")
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-2.0-flash')

def get_news_data(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    title = soup.select_one('h1.tit').text.strip() if soup.select_one('h1.tit') else soup.title.string
    content = soup.select_one('div.news_content').text.strip() if soup.select_one('div.news_content') else soup.get_text()
    return title, content[:2000]

def get_ai_keywords(title, content, keyword_list):
    prompt = f"""
    기사 제목: {title}
    기사 본문: {content}
    참고 키워드 리스트: {keyword_list}
    
    위 기사에서 핵심 키워드 5개를 뽑아주세요. 
    가능하면 '참고 키워드 리스트'에 있는 단어를 우선적으로 선정하세요.
    JSON 형식: {{"keywords": ["키워드1", ..., "키워드5"]}}
    """
    response = model.generate_content(prompt)
    text = response.text.replace("```json", "").replace("```", "").strip()
    return json.loads(text).get("keywords", [])

def calculate_score(ai_keywords, rubric_keywords, media_weight):
    # 가중치 높은 순 정렬 후 상위 4개 추출
    sorted_keywords = sorted(rubric_keywords.items(), key=lambda x: int(x[1]), reverse=True)
    top_4_keywords = sorted_keywords[:4] 
    
    total_score = 0
    matched_keywords = []
    
    # 키워드 매칭 로직
    for ai_kw in ai_keywords:
        for official_kw, coeff in top_4_keywords:
            if official_kw in ai_kw:
                total_score += int(coeff)
                matched_keywords.append(f"{ai_kw}({official_kw})")
                
    total_score += int(media_weight)
    return total_score, matched_keywords

# --- 실행부 ---
# 데이터 로드
rubric_keywords = {r['Keyword']: r['Coefficient'] for r in spreadsheet.worksheet("Config_Keywords").get_all_records()}
media_data = {r['Domain']: r['Weight'] for r in spreadsheet.worksheet("Config_Media").get_all_records()}

test_url = "https://www.newstomato.com/ReadNews.aspx?no=1303051"
title, content = get_news_data(test_url)

# 분석 및 점수 산출
ai_keywords = get_ai_keywords(title, content, list(rubric_keywords.keys()))
media_weight = next((val for dom, val in media_data.items() if dom in test_url), 0)
final_score, matches = calculate_score(ai_keywords, rubric_keywords, media_weight)

# DB 기록
spreadsheet.worksheet("DB_Archive").append_row([
    datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
    title, test_url, 
    ", ".join(ai_keywords), 
    ", ".join(matches), 
    final_score
])

print(f"분석 완료: {title} | 최종점수: {final_score} | 매칭: {matches}")
