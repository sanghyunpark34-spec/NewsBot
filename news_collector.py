import os
import json
import re
import html
import requests
from datetime import datetime
import pytz
import gspread
from oauth2client.service_account import ServiceAccountCredentials

KST = pytz.timezone('Asia/Seoul')

def clean_html(text):
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = html.unescape(text)
    return text.strip()

def collect_news():
    print("📡 뉴스 수집 및 본문 요약문 파싱 가동을 시작합니다.")
    
    creds_dict = json.loads(os.environ["GOOGLE_SHEETS_CREDENTIALS"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        creds_dict,
        ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    )
    spreadsheet = gspread.authorize(creds).open("News_Management_DB")
    
    inbox_sheet = spreadsheet.worksheet("DB_Inbox")
    archive_sheet = spreadsheet.worksheet("DB_Archive")
    keyword_sheet = spreadsheet.worksheet("Config_Keywords")
    
    keywords = [r.get("Keyword", "").strip() for r in keyword_sheet.get_all_records() if r.get("Keyword", "").strip()]
    
    cutoff_time = datetime.min
    try:
        archive_rows = archive_sheet.get_all_values()
        if len(archive_rows) > 1:
            # 💡 [핵심 수정] row[1](제목)이 아니라 row[0](실행 시간)을 읽도록 수정 완료!
            date_strings = [row[0] for row in archive_rows[1:] if row[0].strip()]
            if date_strings:
                latest_str = max(date_strings)
                cutoff_time = datetime.strptime(latest_str, "%Y-%m-%d %H:%M:%S")
                print(f"⏱️ 영구 창고 기준 최후 수집 시점은 {latest_str} 입니다.")
    except Exception as e:
        print(f"⚠️ 기준 시점 확인 실패로 처음부터 수집을 시도합니다: {e}")

    client_id = os.environ.get("NAVER_CLIENT_ID")
    client_secret = os.environ.get("NAVER_CLIENT_SECRET")
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }
    
    rows_to_add = []
    seen_links = set()
    
    for kw in keywords:
        url = f"https://openapi.naver.com/v1/search/news.json?query={requests.utils.quote(kw)}&display=50&sort=date"
        try:
            res = requests.get(url, headers=headers)
            if res.status_code == 200:
                items = res.json().get("items", [])
                for item in items:
                    title = clean_html(item.get("title"))
                    link = item.get("originallink") or item.get("link")
                    description = clean_html(item.get("description"))
                    pub_date_str = item.get("pubDate")
                    
                    try:
                        pub_date = datetime.strptime(pub_date_str[:-6], "%a, %d %b %Y %H:%M:%S")
                    except:
                        continue
                        
                    if pub_date <= cutoff_time:
                        break
                        
                    if link not in seen_links:
                        seen_links.add(link)
                        rows_to_add.append([pub_date.strftime("%Y-%m-%d %H:%M:%S"), title, link, description])
        except Exception as e:
            print(f"❌ [{kw}] 검색 데이터 추출 중 오류가 발생했습니다: {e}")
            
    if rows_to_add:
        rows_to_add.sort(key=lambda x: x[0])
        inbox_sheet.append_rows(rows_to_add)
        print(f"✅ 총 {len(rows_to_add)}개의 신규 뉴스가 요약문과 함께 DB_Inbox 적재를 완료했습니다.")
    else:
        print("🟢 업데이트된 새로운 기사가 발견되지 않았습니다.")

if __name__ == "__main__":
    collect_news()
