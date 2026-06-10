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
            print(f"API 호출 중 오류 발생 {e}")
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
    
    try:
        negative_sheet = spreadsheet.worksheet("Config_Negative")
        negative_keywords = [str(r['NegativeKeyword']).strip() for r in negative_sheet.get_all_records() if str(r.get('NegativeKeyword', '')).strip()]
    except Exception as e:
        print(f"부정 키워드 시트를 불러오는 중 오류가 발생했습니다 {e}")
        negative_keywords = []
    
    print(f"수집 시작 대상 키워드 {len(keywords)}개 대상 매체 {len(media_list)}개 부정 키워드 {len(negative_keywords)}개")

    rows_to_add = []

    for kw in keywords:
        print(f"{kw} 키워드 검색 및 벌크 수집 중입니다.")
        items = get_naver_news_bulk(kw)
        
        for item in items:
            link = item['link']
            org_link = item.get('originallink', '')
            title = item['title']
            description = item.get('description', '')
            
            if link in existing_links:
                continue
                
            is_target_media = any(media in org_link or media in link for media in media_list)
            if not is_target_media:
                continue
                
            has_negative = any(neg in title or neg in description for neg in negative_keywords)
            if has_negative:
                continue
                
            pub_date = datetime.strptime(item['pubDate'], "%a, %d %b %Y %H:%M:%S %z")
            if pub_date >= datetime.now(KST) - timedelta(days=1):
                pub_date_str = pub_date.strftime("%Y-%m-%d %H:%M:%S")
                
                rows_to_add.append([pub_date_str, title, link])
                existing_links.append(link)

    if rows_to_add:
        inbox_sheet.append_rows(rows_to_add)
        print(f"총 {len(rows_to_add)}개의 기사를 구글 시트에 성공적으로 추가했습니다.")

    print("모든 키워드에 대한 타깃 매체 뉴스 수집 작업이 완료되었습니다.")

if __name__ == "__main__":
    collect_news()
