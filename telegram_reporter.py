import os, json, gspread, requests, time
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import pytz

# 설정 및 인증
KST = pytz.timezone('Asia/Seoul')
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

creds = ServiceAccountCredentials.from_json_keyfile_dict(
    json.loads(os.environ["GOOGLE_SHEETS_CREDENTIALS"]),
    ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
)
spreadsheet = gspread.authorize(creds).open("News_Management_DB")

def report_top_news():
    # 1. 주말 패스 로직
    if datetime.now(KST).weekday() >= 5: 
        print("주말이라 보고를 생략합니다.")
        return 
    
    archive_sheet = spreadsheet.worksheet("DB_Archive")
    all_news = archive_sheet.get_all_records()
    
    # 2. 최근 24시간 이내의 데이터만 필터링
    recent_news = [r for r in all_news 
                  if datetime.strptime(r['Date'], "%Y-%m-%d %H:%M:%S").replace(tzinfo=KST) >= datetime.now(KST) - timedelta(days=1)]
    
    if not recent_news:
        print("최근 24시간 내 분석된 기사가 없습니다.")
        return

    # 3. 점수 순 정렬 및 상위 10개 추출
    top_10 = sorted(recent_news, key=lambda x: int(x['Total_Score']), reverse=True)[:10]
    
    # 4. 텔레그램 메시지 발송
    for i, news in enumerate(top_10, 1):
        msg = f"[{i}위] {news['Title']}\n점수: {news['Total_Score']}점\n링크: {news['Link']}"
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        response = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
        
        if response.status_code == 200:
            print(f"{i}위 메시지 전송 성공")
        else:
            print(f"메시지 전송 실패: {response.text}")
            
        time.sleep(1)

if __name__ == "__main__":
    report_top_news()
