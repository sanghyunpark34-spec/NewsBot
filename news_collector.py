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
    keywords = [r['Keyword'] for r in spreadsheet.worksheet("Config_Keywords").get_all_records()]
    media_list = [r['Domain'] for r in spreadsheet.worksheet("Config_Media").get_all_records()]
    
    for media in media_list:
        for kw in keywords:
            for item in get_naver_news(f"{media} {kw}"):
                if not is_already_analyzed(item['link']):
                    # 24시간 이내 기사 필터링
                    pub_date = datetime.strptime(item['pubDate'], "%a, %d %b %Y %H:%M:%S %z")
                    if pub_date >= datetime.now(KST) - timedelta(days=1):
                        inbox_sheet.append_row([datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"), item['title'], item['link']])

if __name__ == "__main__":
    collect_news()
