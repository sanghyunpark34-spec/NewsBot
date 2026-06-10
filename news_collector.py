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
    
    # 아카이브 시트의 3번째 열(C열) 전체를 가져와 메모리에 저장 (중복 체크용)
    archive_links = archive_sheet.col_values(3) 
    
    keywords = [r['Keyword'] for r in spreadsheet.worksheet("Config_Keywords").get_all_records()]
    media_list = [r['Domain'] for r in spreadsheet.worksheet("Config_Media").get_all_records()]
    
    for media in media_list:
        for kw in keywords:
            items = get_naver_news(f"{media} {kw}")
            for item in items:
                # 기사 주소 변수: link
                link = item['link']
                
                # 메모리에 저장된 링크 리스트에 없으면 수집
                if link not in archive_links:
                    # 기사 작성 시간 파싱
                    pub_date = datetime.strptime(item['pubDate'], "%a, %d %b %Y %H:%M:%S %z")
                    # 24시간 이내 기사만
                    if pub_date >= datetime.now(KST) - timedelta(days=1):
                        # 실제 기사 작성 시간을 Date 형식으로 변환하여 저장
                        pub_date_str = pub_date.strftime("%Y-%m-%d %H:%M:%S")
                        inbox_sheet.append_row([pub_date_str, item['title'], link])
                        
                        # 중복 방지를 위해 메모리 리스트에 추가
                        archive_links.append(link) 

if __name__ == "__main__":
    collect_news()
