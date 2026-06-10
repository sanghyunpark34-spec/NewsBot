import os
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import pytz

# 1. 설정
KST = pytz.timezone('Asia/Seoul')
HEADERS = {
    "X-Naver-Client-Id": os.environ["NAVER_CLIENT_ID"],
    "X-Naver-Client-Secret": os.environ["NAVER_CLIENT_SECRET"]
}

# 2. 인증 및 시트 연결
creds = ServiceAccountCredentials.from_json_keyfile_dict(
    json.loads(os.environ["GOOGLE_SHEETS_CREDENTIALS"]),
    ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
)
spreadsheet = gspread.authorize(creds).open("News_Management_DB")

def get_naver_news(query, display=20):
    """네이버 검색 API 호출"""
    url = "https://openapi.naver.com/v1/search/news.json"
    params = {"query": query, "display": display, "sort": "date"}
    response = requests.get(url, headers=HEADERS, params=params)
    return response.json().get('items', [])

def is_already_analyzed(url):
    """DB_Archive에 이미 기록된 링크인지 확인"""
    # 쿼터 부하를 줄이기 위해 한 번만 전체 링크를 가져와서 리스트로 보관하는 것도 방법입니다
    archive_links = spreadsheet.worksheet("DB_Archive").col_values(3)
    return url in archive_links

def collect_news():
    inbox_sheet = spreadsheet.worksheet("DB_Inbox")
    keywords = [r['Keyword'] for r in spreadsheet.worksheet("Config_Keywords").get_all_records()]
    media_list = [r['Domain'] for r in spreadsheet.worksheet("Config_Media").get_all_records()]
    
    collected_links = []
    
    # 1단계: 매체 + 키워드 조합 타겟팅 수집
    for media in media_list:
        for kw in keywords:
            items = get_naver_news(f"{media} {kw}", display=5)
            for item in items:
                link = item['link']
                
                # 2. 링크 추가 전 '이미 있는지' 체크
                if not is_already_analyzed(link):
                    pub_date = datetime.strptime(item['pubDate'], "%a, %d %b %Y %H:%M:%S %z")
                    if pub_date >= datetime.now(KST) - timedelta(days=1):
                        # 중복이 아니고 날짜도 맞다면 리스트에 추가
                        collected_links.append([item['title'], link])
                else:
                    print(f"중복 기사 발견, 건너뜁니다: {link}")

    # 2단계: 기사 부족 시 전체 키워드 검색 추가 (생략 로직 포함 가능)
    
    # DB_Inbox 기록
    for row in collected_links:
        inbox_sheet.append_row([datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")] + row)

if __name__ == "__main__":
    collect_news()
    print("수집 완료: DB_Inbox를 확인하세요.")
