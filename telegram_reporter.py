import gspread, os, requests, time
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import pytz

# 설정 및 인증
KST = pytz.timezone('Asia/Seoul')
TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(
    json.loads(os.environ["GOOGLE_SHEETS_CREDENTIALS"]),
    ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
)
spreadsheet = gspread.authorize(creds).open("News_Management_DB")

def report_top_news():
    if datetime.now(KST).weekday() >= 5: return # 주말 패스
    
    archive_sheet = spreadsheet.worksheet("DB_Archive")
    recent_news = [r for r in archive_sheet.get_all_records() 
                  if datetime.strptime(r['Date'], "%Y-%m-%d %H:%M:%S").replace(tzinfo=KST) >= datetime.now(KST) - timedelta(days=1)]
    
    top_10 = sorted(recent_news, key=lambda x: int(x['Total_Score']), reverse=True)[:10]
    
    for i, news in enumerate(top_10, 1):
        msg = f"[{i}위] {news['Title']}\n점수: {news['Total_Score']}점\n링크: {news['Link']}"
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": msg})
        time.sleep(1)

if __name__ == "__main__":
    report_top_news()
