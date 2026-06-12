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

def get_naver_news_bulk(query):
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
            last_pub_date = datetime.strptime(items[-1]['pubDate'], "%a, %d %b %Y %H:%M:%S %z")
            if last_pub_date < datetime.now(KST) - timedelta(days=1): break
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
    
    keyword_records = spreadsheet.worksheet("Config_Keywords").get_all_records()
    for r in keyword_records:
        try: r['Weight'] = float(r.get('Weight', r.get('Coefficient', 1)))
        except: r['Weight'] = 1.0
            
    keyword_records.sort(key=lambda x: x['Weight'], reverse=True)
    keywords = [r['Keyword'] for r in keyword_records if str(r.get('Keyword', '')).strip()]
    media_list = [r['Domain'] for r in spreadsheet.worksheet("Config_Media").get_all_records() if str(r.get('Domain', '')).strip()]
    
    # 🚨 상시 제외(입구컷) 키워드 5개 고정
    ABSOLUTE_NEGATIVES = ["바이오", "부동산", "뷰티", "스포츠", "이글스"]
    
    print(f"기사 수집을 시작합니다. 타깃 키워드는 총 {len(keywords)}개입니다.")
    rows_to_add = []

    for kw in keywords:
        print(f"[{kw}] 키워드로 뉴스 원본을 수집합니다.")
        items = get_naver_news_bulk(kw)
        
        for item in items:
            title = item['title'].replace('<b>', '').replace('</b>', '').replace('&quot;', '"').replace('&amp;', '&')
            description = item.get('description', '').replace('<b>', '').replace('</b>', '').replace('&quot;', '"').replace('&amp;', '&')
            
            # 파이썬 단계에서 5개 상시 제외 단어가 포함되어 있으면 즉시 버림(Continue)
            if any(neg in title or neg in description for neg in ABSOLUTE_NEGATIVES):
                continue
                
            org_link = item.get('originallink', '').strip()
            link = item['link'].strip()
            actual_link = org_link if org_link else link
            
            if actual_link in existing_links: continue
                
            is_target_media = any(media in actual_link for media in media_list)
            if not is_target_media: continue
                
            pub_date = datetime.strptime(item['pubDate'], "%a, %d %b %Y %H:%M:%S %z")
            if pub_date >= datetime.now(KST) - timedelta(days=1):
                pub_date_str = pub_date.strftime("%Y-%m-%d %H:%M:%S")
                rows_to_add.append([pub_date_str, title, actual_link])
                existing_links.append(actual_link)

    if rows_to_add:
        inbox_sheet.append_rows(rows_to_add)
        print(f"총 {len(rows_to_add)}개의 기사를 DB_Inbox에 추가했습니다. (상시 제외어 필터링 완료)")
    else:
        print("새롭게 수집된 기사가 없습니다.")

if __name__ == "__main__":
    collect_news()
