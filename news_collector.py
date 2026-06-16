import os
import json
import re
import html
import requests
from datetime import datetime, timedelta
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
    
    # 💡 [핵심 방어 1] DB가 완전히 비어있더라도 최대 3일(72시간)치만 가져오도록 절대 방어선 구축
    now_kst = datetime.now(KST).replace(tzinfo=None)
    cutoff_time = now_kst - timedelta(days=3)
    
    try:
        archive_rows = archive_sheet.get_all_values()
        if len(archive_rows) > 1:
            # 헤더를 확인하여 Date 열의 정확한 위치를 파악합니다.
            headers = archive_rows[0]
            date_idx = headers.index("Date") if "Date" in headers else 1
            
            date_strings = [row[date_idx] for row in archive_rows[1:] if len(row) > date_idx and row[date_idx].strip()]
            if date_strings:
                latest_str = max(date_strings)
                parsed_latest = datetime.strptime(latest_str, "%Y-%m-%d %H:%M:%S")
                
                # DB 최신 기록이 3일 전보다 더 최근이라면 그 시간을 사용
                if parsed_latest > cutoff_time:
                    cutoff_time = parsed_latest
                print(f"⏱️ 영구 창고 기준 최후 수집 시점은 {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')} 입니다.")
    except Exception as e:
        print(f"⚠️ 기준 시점 확인 실패 (기본 3일 전 커트라인 적용): {e}")

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
                        
                    # 💡 [핵심 방어 2] 날짜가 커트라인보다 과거라면 무조건 패스
                    if pub_date <= cutoff_time:
                        continue # 네이버 정렬이 꼬일 수 있으므로 break 대신 안전하게 continue 사용
                        
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
