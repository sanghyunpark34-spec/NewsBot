import os, json, gspread, requests
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import pytz

# 설정 및 인증
KST = pytz.timezone('Asia/Seoul')
HEADERS = {"X-Naver-Client-Id": os.environ["NAVER_CLIENT_ID"], "X-Naver-Client-Secret": os.environ["NAVER_CLIENT_SECRET"]}
creds = ServiceAccountCredentials.from_json_keyfile_dict(
    json.loads(os.environ["GOOGLE_SHEETS_CREDENTIALS"]),
    ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
)
spreadsheet = gspread.authorize(creds).open("News_Management_DB")

def is_already_analyzed(url):
    # 중복 체크: 이미 Archive에 있는 링크인가?
    return url in spreadsheet.worksheet("DB_Archive").col_values(3)

def get_naver_news(query, display=5):
    url = "https://openapi.naver.com/v1/search/news.json"
    params = {"query": query, "display": display, "sort": "date"}
    return requests.get(url, headers=HEADERS, params=params).json().get('items', [])

def collect_news():
    inbox_sheet = spreadsheet.worksheet("DB_Inbox")
    archive_sheet = spreadsheet.worksheet("DB_Archive")
    
    # 1. 루프 시작 전 아카이브 전체 링크를 한 번만 로드하여 메모리에 저장
    archive_links = archive_sheet.col_values(3) 
    
    keywords = [r['Keyword'] for r in spreadsheet.worksheet("Config_Keywords").get_all_records()]
    media_list = [r['Domain'] for r in spreadsheet.worksheet("Config_Media").get_all_records()]
    
    for media in media_list:
        for kw in keywords:
            items = get_naver_news(f"{media} {kw}")
            for item in items:
                link = item['link']
                
                # 2. API 호출 없이 메모리의 리스트(archive_links)만 확인
                if link not in archive_links:
                    # 24시간 이내 기사 필터링
                    pub_date = datetime.strptime(item['pubDate'], "%a, %d %b %Y %H:%M:%S %z")
                    if pub_date >= datetime.now(KST) - timedelta(days=1):
                        # DB_Inbox에 추가
                        inbox_sheet.append_row([datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"), item['title'], link])
                        
                        # 3. 추가된 링크는 메모리 리스트에도 넣어줘야 실시간 중복 체크 가능
                        archive_links.append(link)


if __name__ == "__main__":
    collect_news()
