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

def get_naver_news(query, display=20):
    url = "https://openapi.naver.com/v1/search/news.json"
    params = {"query": query, "display": display, "sort": "date"}
    response = requests.get(url, headers=HEADERS, params=params)
    return response.json().get('items', [])

def collect_news():
    inbox_sheet = spreadsheet.worksheet("DB_Inbox")
    archive_sheet = spreadsheet.worksheet("DB_Archive")
    
    # 1. Archive와 Inbox의 링크를 모두 가져와서 중복 체크 리스트로 통합
    archive_links = archive_sheet.col_values(3)
    inbox_links = inbox_sheet.col_values(3)
    existing_links = archive_links + inbox_links # 두 곳 다 뒤져서 중복을 원천 차단
    
    keywords = [r['Keyword'] for r in spreadsheet.worksheet("Config_Keywords").get_all_records()]
    media_list = [r['Domain'] for r in spreadsheet.worksheet("Config_Media").get_all_records()]
    
    for media in media_list:
        for kw in keywords:
            items = get_naver_news(f"{media} {kw}", display=20)
            for item in items:
                link = item['link']
                
                # 이제 Archive와 Inbox 어디에도 없는 링크만 수집
                if link not in existing_links:
                    pub_date = datetime.strptime(item['pubDate'], "%a, %d %b %Y %H:%M:%S %z")
                    if pub_date >= datetime.now(KST) - timedelta(days=1):
                        pub_date_str = pub_date.strftime("%Y-%m-%d %H:%M:%S")
                        inbox_sheet.append_row([pub_date_str, item['title'], link])
                        
                        # 수집 즉시 existing_links에 추가하여 루프 내 중복도 방지
                        existing_links.append(link)

if __name__ == "__main__":
    collect_news()
