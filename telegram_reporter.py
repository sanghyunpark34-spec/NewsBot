import os, json, gspread, requests, time
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import pytz

KST = pytz.timezone('Asia/Seoul')
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# [수정] 그룹챗 변수를 안전하게 로드하고, 깃허브 실행 방식을 확인합니다.
GROUP_CHAT_ID = os.environ.get("GROUP_CHAT_ID", "")
TRIGGER_EVENT = os.environ.get("GITHUB_EVENT_NAME", "unknown")

creds = ServiceAccountCredentials.from_json_keyfile_dict(
    json.loads(os.environ["GOOGLE_SHEETS_CREDENTIALS"]),
    ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
)
spreadsheet = gspread.authorize(creds).open("News_Management_DB")

def report_top_news():
    if datetime.now(KST).weekday() >= 5: 
        print("주말이라 보고를 생략합니다.")
        return 
    
    archive_sheet = spreadsheet.worksheet("DB_Archive")
    all_news = archive_sheet.get_all_records()
    
    recent_news = []
    for r in all_news:
        try:
            date_obj = datetime.strptime(str(r['Date']), "%Y-%m-%d %H:%M:%S").replace(tzinfo=KST)
            if date_obj >= datetime.now(KST) - timedelta(days=1):
                score_raw = str(r.get('Total_Score', r.get('Total Score', '0'))).replace(',', '').strip()
                if not score_raw: score_raw = '0'
                r['Total_Score_Num'] = float(score_raw) 
                recent_news.append(r)
        except Exception:
            continue 
    
    if not recent_news:
        print("최근 24시간 내 분석된 기사가 없습니다.")
        return

    top_15 = sorted(recent_news, key=lambda x: x['Total_Score_Num'], reverse=True)[:15]
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    # [수정] 스케줄로 실행된 경우에만 그룹방 전송을 허가합니다.
    is_scheduled = (TRIGGER_EVENT == "schedule")
    print(f"상위 {len(top_15)}개 기사 보고를 시작합니다. (실행방식: {TRIGGER_EVENT}, 그룹방 전송 여부: {bool(GROUP_CHAT_ID) and is_scheduled})")

    for i, news in enumerate(top_15, 1):
        msg = f"[{i}위] {news['Title']}\n점수: {news['Total_Score_Num']}점\n링크: {news['Link']}"
        
        # 1. 개인 챗방은 조건 없이 무조건 전송
        try:
            requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
        except Exception as e:
            print(f"개인 챗방 전송 중 에러: {e}")
            
        # 2. 그룹 챗방은 자동 스케줄 실행(schedule)일 때만 전송
        if GROUP_CHAT_ID and is_scheduled:
            try:
                requests.post(url, data={"chat_id": GROUP_CHAT_ID, "text": msg})
            except Exception as e:
                print(f"그룹 챗방 전송 중 에러: {e}")
                
        time.sleep(1.5)

if __name__ == "__main__":
    report_top_news()
