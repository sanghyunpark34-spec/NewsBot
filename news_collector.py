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
    now_kst = datetime.now(KST)
    is_monday = now_kst.weekday() == 0
    is_weekend = now_kst.weekday() in [5, 6]
    is_manual = (os.environ.get("GITHUB_EVENT_NAME", "") == "workflow_dispatch")

    if is_monday or is_weekend or is_manual:
        return 3
    return 1

def get_latest_archive_time(archive_sheet):
    """DB_Archive에 기록된 기사 중 가장 최신 기사의 발행 시간을 구합니다."""
    try:
        col_dates = archive_sheet.col_values(1)[1:] # 첫 번째 열(Date) 가져오기
        if not col_dates:
            return None
        # 문자열 시간을 datetime 객체로 변환하여 가장 최신 값을 찾습니다.
        date_objects = [datetime.strptime(d.strip(), "%Y-%m-%d %H:%M:%S") for d in col_dates if d.strip()]
        if date_objects:
            return max(date_objects)
    except Exception as e:
        print(f"최신 아카이브 시간 조회 중 참고용 오류 발생: {e}")
    return None

def get_naver_news_bulk(query, lookback_days, latest_db_time):
    all_items = []
    early_stop_triggered = False

    for start in range(1, 1000, 100):
        if early_stop_triggered: 
            break
            
        url = "https://openapi.naver.com/v1/search/news.json"
        params = {"query": query, "display": 100, "start": start, "sort": "date"}
        try:
            response = requests.get(url, headers=HEADERS, params=params)
            if response.status_code != 200: break
            data = response.json()
            items = data.get('items', [])
            if not items: break
            
            for item in items:
                pub_date = datetime.strptime(item['pubDate'], "%a, %d %b %Y %H:%M:%S %z").replace(tzinfo=None)
                
                # 💡 [핵심 최적화 1] 네이버에서 읽어온 기사가 우리 DB의 가장 최신 기사보다 과거 데이터라면 즉시 크롤링 전면 중단
                if latest_db_time and pub_date <= latest_db_time:
                    print(f" -> DB 최신 기사 시점({latest_db_time}) 도달로 인해 [{query}] 검색을 조기 종료합니다.")
                    early_stop_triggered = True
                    break
                
                all_items.append(item)
            
            # 마지막 기사의 발행일이 설정한 lookback_days(24시간 또는 72시간) 이전이어도 중단합니다.
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
    
    # DB에 보관된 가장 최신 기사의 타임스탬프를 획득합니다.
    latest_db_time = get_latest_archive_time(archive_sheet)
    if latest_db_time:
        print(f"현재 데이터베이스의 가장 최신 기사 타임스탬프는 {latest_db_time} 입니다.")
    
    keyword_records = spreadsheet.worksheet("Config_Keywords").get_all_records()
    for r in keyword_records:
        try: r['Weight'] = float(r.get('Weight', r.get('Coefficient', 1)))
        except: r['Weight'] = 1.0
            
    keyword_records.sort(key=lambda x: x['Weight'], reverse=True)
    keywords = [r['Keyword'] for r in keyword_records if str(r.get('Keyword', '')).strip()]
    media_list = [r['Domain'] for r in spreadsheet.worksheet("Config_Media").get_all_records() if str(r.get('Domain', '')).strip()]
    
    lookback_days = get_lookback_days()
    print(f"기사 수집을 시작합니다. 타깃 키워드는 총 {len(keywords)}개입니다.")
    
    rows_to_add = []

    for kw in keywords:
        print(f"[{kw}] 키워드로 뉴스 원본을 수집합니다.")
        # 최신 DB 시간을 수집기에 넘겨주어 추적하게 합니다.
        items = get_naver_news_bulk(kw, lookback_days, latest_db_time)
        
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
        print(f"총 {len(rows_to_add)}개의 새로운 기사를 DB_Inbox에 추가했습니다.")
    else:
        print("조건에 부합하는 새로운 기사가 전혀 없으므로 리소스를 사용하지 않고 안전하게 종료합니다.")

if __name__ == "__main__":
    collect_news()
