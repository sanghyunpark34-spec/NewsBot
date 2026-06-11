import os, json, gspread, requests, time
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import pytz

KST = pytz.timezone('Asia/Seoul')
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

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
                # 헤더 이름이 Total_Score 인지 Total Score 인지 유연하게 대처
                score_raw = str(r.get('Total_Score', r.get('Total Score', '0'))).replace(',', '').strip()
                if not score_raw: score_raw = '0'
                r['Total_Score_Num'] = float(score_raw) # 무조건 숫자로 강제 변환
                recent_news.append(r)
        except Exception as e:
            continue 
    
    if not recent_news:
        print("최근 24시간 내 분석된 기사가 없습니다.")
        return

    # 완벽하게 숫자로 변환된 Total_Score_Num을 기준으로 내림차순 정렬
    top_10 = sorted(recent_news, key=lambda x: x['Total_Score_Num'], reverse=True)[:10]
    
    for i, news in enumerate(top_10, 1):
        # 메시지에 소수점까지 깔끔하게 보이도록 Total_Score_Num 사용
        msg = f"[{i}위] {news['Title']}\n점수: {news['Total_Score_Num']}점\n링크: {news['Link']}"
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
        time.sleep(1)

if __name__ == "__main__":
    report_top_news()
