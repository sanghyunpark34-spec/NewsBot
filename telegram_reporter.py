import os, json, gspread, requests, time
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import pytz

KST = pytz.timezone('Asia/Seoul')
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
GROUP_CHAT_ID = os.environ.get("GROUP_CHAT_ID", "")
TRIGGER_EVENT = os.environ.get("GITHUB_EVENT_NAME", "unknown")

creds = ServiceAccountCredentials.from_json_keyfile_dict(
    json.loads(os.environ["GOOGLE_SHEETS_CREDENTIALS"]),
    ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
)
spreadsheet = gspread.authorize(creds).open("News_Management_DB")

def report_top_news():
    if datetime.now(KST).weekday() >= 5: return 
    
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
        except Exception: continue 
    
    if not recent_news: return

    top_15 = sorted(recent_news, key=lambda x: x['Total_Score_Num'], reverse=True)[:15]
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    is_scheduled = (TRIGGER_EVENT == "schedule")

    for i, news in enumerate(top_15, 1):
        msg = f"[{i}위] {news['Title']}\n점수: {news['Total_Score_Num']}점\n링크: {news['Link']}"
        try:
            requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
        except: pass
        if GROUP_CHAT_ID and GROUP_CHAT_ID.strip() != "" and is_scheduled:
            try: requests.post(url, data={"chat_id": GROUP_CHAT_ID, "text": msg})
            except: pass
        time.sleep(1.5)

if __name__ == "__main__":
    report_top_news()
