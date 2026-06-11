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
    raw_values = archive_sheet.get_all_values()
    if len(raw_values) <= 1: return
    
    all_news = archive_sheet.get_all_records()
    unique_news = {}
    
    for r in all_news:
        try:
            score_raw = str(r.get('Total_Score', '0')).replace(',', '').strip()
            r['Total_Score_Num'] = float(score_raw) if score_raw else 0.0
            title = str(r.get('Title', '')).strip()
            if title not in unique_news or r['Total_Score_Num'] > unique_news[title]['Total_Score_Num']:
                unique_news[title] = r
        except: continue 

    top_15 = sorted(unique_news.values(), key=lambda x: x['Total_Score_Num'], reverse=True)[:15]
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    is_scheduled = (TRIGGER_EVENT == "schedule")

    for i, news in enumerate(top_15, 1):
        msg = f"[{i}위] {news['Title']}\n점수: {news['Total_Score_Num']}점\n링크: {news['Link']}"
        sent_success = False
        
        try:
            res = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
            if res.status_code == 200: sent_success = True
        except: pass
        
        if GROUP_CHAT_ID and GROUP_CHAT_ID.strip() != "" and is_scheduled:
            try: requests.post(url, data={"chat_id": GROUP_CHAT_ID, "text": msg})
            except: pass
            
        if sent_success:
            for idx, row_val in enumerate(raw_values, 1):
                if idx == 1: continue
                if str(row_val[1]).strip() == str(news['Title']).strip() and str(row_val[2]).strip() == str(news['Link']).strip():
                    archive_sheet.update_cell(idx, 8, 'Y')
                    break
                    
        time.sleep(1.5)

if __name__ == "__main__":
    report_top_news()
