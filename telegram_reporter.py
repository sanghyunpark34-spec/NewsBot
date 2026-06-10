import gspread
import os
import requests
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import pytz

# 1. 설정
TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
KST = pytz.timezone('Asia/Seoul')

# 2. 시트 연결
creds = ServiceAccountCredentials.from_json_keyfile_dict(
    json.loads(os.environ["GOOGLE_SHEETS_CREDENTIALS"]),
    ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
)
spreadsheet = gspread.authorize(creds).open("News_Management_DB")

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text}
    requests.post(url, data=payload)

def report_top_news():
    # 평일(0=월 ~ 4=금)에만 실행
    if datetime.now(KST).weekday() >= 5:
        print("주말입니다. 보고를 건너뜁니다.")
        return
        
    archive_sheet = spreadsheet.worksheet("DB_Archive")
    all_data = archive_sheet.get_all_records()
    
    # 최근 24시간 필터링
    yesterday = datetime.now(KST) - timedelta(days=1)
    # 최근 24시간 필터링 로직 내의 row[...] 키 값을 시트 헤더와 맞춤
    recent_news = [
        row for row in all_data 
        if datetime.strptime(row['Date'], "%Y-%m-%d %H:%M:%S").replace(tzinfo=KST) >= yesterday
    ]
    
    # 정렬 및 출력 시에도 'Total_Score' 키 사용
    top_10 = sorted(recent_news, key=lambda x: int(x['Total_Score']), reverse=True)[:10]
    
    # 개별 메시지 발송
    for i, news in enumerate(top_10, 1):
        # 헤더명 그대로 사용: Title, Total_Score, Link
        message = f"[{i}위] {news['Title']}\n점수: {news['Total_Score']}점\n링크: {news['Link']}"
        send_telegram_message(message)
        time.sleep(1)
        
if __name__ == "__main__":
    report_top_news()
    print("리포트 전송 완료!")
