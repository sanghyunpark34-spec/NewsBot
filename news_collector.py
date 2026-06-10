import os, json, gspread, requests, time
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import pytz

# 설정 및 인증
KST = pytz.timezone('Asia/Seoul')
HEADERS = {
    "X-Naver-Client-Id": os.environ["NAVER_CLIENT_ID"], 
    "X-Naver-Client-Secret": os.environ["NAVER_CLIENT_SECRET"]
}

creds = ServiceAccountCredentials.from_json_keyfile_dict(
    json.loads(os.environ["GOOGLE_SHEETS_CREDENTIALS"]),
    ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
)
spreadsheet = gspread.authorize(creds).open("News_Management_DB")

def get_naver_news_bulk(query):
    all_items = []
    
    for start in range(1, 1000, 100):
        url = "https://openapi.naver.com/v1/search/news.json"
        params = {"query": query, "display": 100, "start": start, "sort": "date"}
        
        try:
            response = requests.get(url, headers=HEADERS, params=params)
            if response.status_code != 200:
                break
                
            data = response.json()
            items = data.get('items', [])
            if not items:
                break
                
            all_items.extend(items)
            
            last_pub_date = datetime.strptime(items[-1]['pubDate'], "%a, %d %b %Y %H:%M:%S %z")
            if last_pub_date < datetime.now(KST) - timedelta(days=1):
                break
                
        except Exception as e:
            print(f"API 호출 중 오류 발생: {e}")
            break
            
        time.sleep(0.3) 
        
    return all_items

def collect_news():
    inbox_sheet = spreadsheet.worksheet("DB_Inbox")
    archive_sheet = spreadsheet.worksheet("DB_Archive")
    
    archive_links = archive_sheet.col_values(3)
    inbox_links = inbox_sheet.col_values(3)
    existing_links = archive_links + inbox_links 
    
    keywords = [r['Keyword'] for r in spreadsheet.worksheet("Config_Keywords").get_all_records()]
    media_list = [r['Domain'] for r in spreadsheet.worksheet("Config_Media").get_all_records()]
    
    # Config_Negative 시트에서 NegativeKeyword 열의 데이터를 실시간으로 불러옵니다.
    try:
        negative_sheet = spreadsheet.worksheet("Config_Negative")
        negative_keywords = [str(r['NegativeKeyword']).strip() for r in negative_sheet.get_all_records() if str(r.get('NegativeKeyword', '')).strip()]
    except Exception as e:
