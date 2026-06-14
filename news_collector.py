import os, json, gspread, requests, time
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import pytz

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

def get_lookback_days():
    """
    현재 요일과 실행 트리거를 분석하여 기사 검색 기간(일수)을 결정합니다.
    """
    now_kst = datetime.now(KST)
    is_monday = now_kst.weekday() == 0  # 0: 월요일
    is_weekend = now_kst.weekday() in [5, 6]  # 5: 토요일, 6: 일요일
    
    # 깃허브 액션에서 전달된 실행 환경 변수를 확인합니다.
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    is_manual = (event_name == "workflow_dispatch")

    # 월요일, 주말, 또는 대시보드 수동 실행일 경우 3일(72시간)치 기사를 탐색합니다.
    if is_monday or is_weekend or is_manual:
        return 3
    # 화~금 일반적인 자동 실행일 경우 1일(24시간)치 기사만 탐색합니다.
    return 1

def get_naver_news_bulk(query, lookback_days):
    all_items = []
    for start in range(1, 1000, 100):
        url = "https://openapi.naver.com/v1/search/news.json"
        params = {"query": query, "display": 100, "start": start, "sort": "date"}
        try:
            response = requests.get(url, headers=HEADERS, params=params)
            if response.status_code != 200: break
            data = response.json()
            items = data.get('items', [])
            if not items: break
            all_items.extend(items)
            
            # 마지막 기사의 발행일이 lookback_days 이전이면 크롤링을 중단합니다.
            last_pub_date = datetime.strptime(items[-1]['pubDate'], "%a, %d %b %Y %H:%M:%S %z")
            if last_pub_date < datetime.now(KST) - timedelta(days=lookback_days): 
                break
        except Exception as e:
            print(f"API 호출 중 오류 발생하여 수집을 중단합니다. {e}")
            break
        time.sleep(0.3) 
    return all_items

def collect_news():
    inbox_sheet = spreadsheet.worksheet("DB_Inbox")
    archive_sheet = spreadsheet.worksheet("DB_Archive")
    
    archive_links = archive_sheet.col_values(3)
    inbox_links = inbox_sheet.col_values(3)
    existing_links = archive_links + inbox_links 
    
    keyword_records = spreadsheet.worksheet("Config_Keywords").get_all_records()
    for r in keyword_records:
        try: r['Weight'] = float(r.get('Weight', r.get('Coefficient', 1)))
        except: r['Weight'] = 1.0
            
    keyword_records.sort(key=lambda x: x['Weight'], reverse=True)
    keywords = [r['Keyword'] for r in keyword_records if str(r.get('Keyword', '')).strip()]
    media_list = [r['Domain'] for r in spreadsheet.worksheet("Config_Media").get_all_records() if str(r.get('Domain', '')).strip()]
    
    # 💡 동적 탐색 기간 계산
    lookback_days = get_lookback_days()
    print(f"기사 수집을 시작합니다. 타깃 키워드는 총 {len(keywords)}개이며, 최근 {lookback_days}일({lookback_days * 24}시간) 범위의 기사를 탐색합니다.")
    
    rows_to_add = []

    for kw in keywords:
        print(f"[{kw}] 키워드로 뉴스 원본을 수집합니다.")
        items = get_naver_news_bulk(kw, lookback_days)
        
        for item in items:
            title = item['title'].replace('<b>', '').replace('</b>', '').replace('&quot;', '"').replace('&amp;', '&')
            
            org_link = item.get('originallink', '').strip()
            link = item['link'].strip()
            actual_link = org_link if org_link else link
            
            if actual_link in existing_links: continue
                
            is_target_media = any(media in actual_link for media in media_list)
            if not is_target_media: continue
                
            pub_date = datetime.strptime(item['pubDate'], "%a, %d %b %Y %H:%M:%S %z")
            if pub_date >= datetime.now(KST) - timedelta(days=lookback_days):
                pub_date_str = pub_date.strftime("%Y-%m-%d %H:%M:%S")
                rows_to_add.append([pub_date_str, title, actual_link])
                existing_links.append(actual_link)

    if rows_to_add:
        inbox_sheet.append_rows(rows_to_add)
        print(f"총 {len(rows_to_add)}개의 기사를 DB_Inbox에 안전하게 추가했습니다.")
    else:
        print("조건에 부합하는 새로운 기사가 없습니다.")

if __name__ == "__main__":
    collect_news()
