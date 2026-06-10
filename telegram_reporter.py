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
    archive_sheet = spreadsheet.worksheet("DB_Archive")
    all_data = archive_sheet.get_all_records()
    
    # 최근 24시간 필터링
    yesterday = datetime.now(KST) - timedelta(days=1)
    recent_news = [
        row for row in all_data 
        if datetime.strptime(row['Date'], "%Y-%m-%d %H:%M:%S").replace(tzinfo=KST) >= yesterday
    ]
    
    # 점수 상위 10개 정렬
    top_10 = sorted(recent_news, key=lambda x: int(x['Total_Score']), reverse=True)[:10]
    
    # 개별 메시지 발송
    for i, news in enumerate(top_10, 1):
        message = f"[{i}위] {news['Title']}\n점수: {news['Total_Score']}점\n링크: {news['Link']}"
        send_telegram_message(message)
        # 메시지 간격 유지
        import time
        time.sleep(1)

if __name__ == "__main__":
    report_top_news()
    print("리포트 전송 완료!")
