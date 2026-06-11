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
                # 빈 칸이나 에러가 날 수 있는 값들을 안전하게 float(소수점)으로 변환
                score_str = str(r.get('Total_Score', '0')).strip()
                if not score_str: score_str = '0'
                r['Total_Score_Num'] = float(score_str)
                recent_news.append(r)
        except Exception:
            continue # 날짜 형식이 안 맞거나 문제가 있는 행은 부드럽게 패스
    
    if not recent_news:
        print("최근 24시간 내 분석된 기사가 없습니다.")
        return

    # 안전하게 변환된 Total_Score_Num 기준으로 정렬
    top_10 = sorted(recent_news, key=lambda x: x['Total_Score_Num'], reverse=True)[:10]
    
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
