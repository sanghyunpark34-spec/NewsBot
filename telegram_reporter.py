import os, json, gspread, requests, time
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import pytz

# 설정 및 인증
KST = pytz.timezone('Asia/Seoul')
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
# Secrets에서 그룹 챗 ID를 추가로 로드합니다 (설정되지 않은 경우를 대비해 get 사용)
# GROUP_CHAT_ID = os.environ.get("GROUP_CHAT_ID")

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
        except Exception as e:
            continue 
    
    if not recent_news:
        print("최근 24시간 내 분석된 기사가 없습니다.")
        return

    # [수정] 기존 상위 10개에서 상위 15개로 확장하여 정렬 추출
    top_15 = sorted(recent_news, key=lambda x: x['Total_Score_Num'], reverse=True)[:15]
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    print(f"상위 {len(top_15)}개 기사 보고를 시작합니다. (그룹방 전송 활성화: {bool(GROUP_CHAT_ID)})")

    for i, news in enumerate(top_15, 1):
        msg = f"[{i}위] {news['Title']}\n점수: {news['Total_Score_Num']}점\n링크: {news['Link']}"
        
        # 1. 기존 개인 챗방으로 전송
        try:
            requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
        except Exception as e:
            print(f"개인 챗방 전송 중 에러 발생: {e}")
            
        # 2. [추가] 그룹 챗방 변수가 존재할 경우 그룹방으로도 동시 전송
        if GROUP_CHAT_ID:
            try:
                requests.post(url, data={"chat_id": GROUP_CHAT_ID, "text": msg})
            except Exception as e:
                print(f"그룹 챗방 전송 중 에러 발생: {e}")
                
        # API 호출 제한 안정성을 위해 1.5초 숨고르기
        time.sleep(1.5)

if __name__ == "__main__":
    report_top_news()
