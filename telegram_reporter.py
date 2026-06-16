import os, json, gspread, requests
from datetime import datetime, timedelta
import pytz
import holidays
from oauth2client.service_account import ServiceAccountCredentials

KST = pytz.timezone('Asia/Seoul')

def get_previous_working_day_cutoff(current_time):
    """현재 시간 기준으로 정확히 1영업일(24시간) 전의 시간을 계산합니다."""
    kr_holidays = holidays.KR()
    days_to_subtract = 1
    
    while True:
        target_date = current_time - timedelta(days=days_to_subtract)
        # weekday() 5: 토요일, 6: 일요일
        if target_date.weekday() < 5 and target_date.date() not in kr_holidays:
            return target_date
        days_to_subtract += 1

def send_telegram():
    is_scheduled = os.environ.get("GITHUB_EVENT_NAME") == "schedule"
    now = datetime.now(KST)
    cutoff_time = get_previous_working_day_cutoff(now)
    
    if is_scheduled:
        print("⏰ [스케줄 가동] 공식 정기 리포트 발송을 시작합니다.")
    else:
        print("🚀 [수동 가동] 관리자 수동 발송 테스트를 시작합니다.")
        
    print(f"🧹 [대기열 청소] 기준 시간(Cut-off): {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')} 이전 기사는 만료(E) 처리됩니다.")

    BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    GROUP_CHAT_ID = os.environ.get("TELEGRAM_GROUP_CHAT_ID")
    MY_CHAT_ID = os.environ.get("MY_CHAT_ID")

    if not BOT_TOKEN:
        print("⚠️ 텔레그램 봇 토큰이 없습니다.")
        return

    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        json.loads(os.environ["GOOGLE_SHEETS_CREDENTIALS"]),
        ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    )
    spreadsheet = gspread.authorize(creds).open("News_Management_DB")

    try:
        sys_sheet = spreadsheet.worksheet("Config_System")
        config = {str(r.get("Key")): str(r.get("Value")) for r in sys_sheet.get_all_records()}
        send_group = config.get("TELEGRAM_GROUP_SEND", "OFF") == "ON"
        send_author = config.get("TELEGRAM_AUTHOR_SEND", "OFF") == "ON"
        extra_ids = [x.strip() for x in config.get("EXTRA_TELEGRAM_IDS", "").split(",") if x.strip()]
    except:
        send_group, send_author, extra_ids = False, False, []

    target_chats = []
    if send_group and GROUP_CHAT_ID: target_chats.append(GROUP_CHAT_ID)
    if send_author and MY_CHAT_ID: target_chats.append(MY_CHAT_ID)
    target_chats.extend(extra_ids)
    target_chats = list(set(target_chats))

    if not target_chats:
        print("⚠️ 발송 대상 채팅방이 없습니다.")
        return

    ai_report_sheet = spreadsheet.worksheet("DB_AI_Report")
    rows = ai_report_sheet.get_all_values()
    if len(rows) <= 1:
        print("조건에 부합하는 발송 대상 기사가 없습니다.")
        return

    headers = rows[0]
    col_idx = {h: i for i, h in enumerate(headers)}
    date_idx = col_idx.get('Date', 1)
    sent_idx = col_idx.get('Sent', 9)
    
    unsent_rows = []
    unsent_indices = []
    expire_updates = []
    
    # 💡 데이터 스캔 및 만료 처리 로직
    for i, row in enumerate(rows[1:]):
        idx = i + 2
        if len(row) > sent_idx and row[sent_idx] == 'N':
            try:
                # 시트의 Date 값을 KST datetime 객체로 변환
                row_date = datetime.strptime(row[date_idx], "%Y-%m-%d %H:%M:%S")
                row_date = KST.localize(row_date)
            except:
                row_date = now # 날짜 파싱 실패 시 예외 처리
            
            # 발송 유효기간(1영업일 전)을 넘긴 기사는 'E'로 변경 예약
            if row_date < cutoff_time:
                # 배치 업데이트를 위한 데이터 구조 생성
                col_letter = gspread.utils.rowcol_to_a1(idx, sent_idx + 1)
                expire_updates.append({'range': col_letter, 'values': [['E']]})
            else:
                # 유효기간 내에 있는 신선한 기사만 발송 큐에 삽입
                unsent_rows.append(row)
                unsent_indices.append(idx)

    # 💡 만료된 기사들을 한 번에 시트에 업데이트 (API 호출 최적화)
    if expire_updates:
        ai_report_sheet.batch_update(expire_updates)
        print(f"♻️ 총 {len(expire_updates)}개의 오래된 기사가 대기열에서 만료(E) 처리되어 자리를 양보했습니다.")

    if not unsent_rows:
        print("조건에 부합하는 신선한 발송 대상 기사가 없습니다.")
        return

    # 💡 메시지 조립 및 전송 (최상위 20개만)
    msg = f"📊 뉴스 자동화 리포트\n\n"
    for i, row in enumerate(unsent_rows[:20]):
        title = row[col_idx.get('Title', 2)]
        link = row[col_idx.get('Link', 3)]
        msg += f"{i+1}. {title}\n🔗 {link}\n\n"

    for chat_id in target_chats:
        res = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": msg, "disable_web_page_preview": True}
        )
        if res.status_code == 200:
            print(f"✅ {chat_id} 방 발송 완료!")

    # 💡 발송된 기사 상태 업데이트
    if is_scheduled:
        sent_updates = []
        for idx in unsent_indices[:20]:
            col_letter = gspread.utils.rowcol_to_a1(idx, sent_idx + 1)
            sent_updates.append({'range': col_letter, 'values': [['Y']]})
        if sent_updates:
            ai_report_sheet.batch_update(sent_updates)
        print("🏁 공식 발송 완료: 발송된 기사는 'Y'로 변경되었습니다.")
    else:
        print("🏁 수동 발송 테스트 완료: 기사들의 Sent 상태는 'N'으로 유지되어 다음 스케줄에 정식 포함됩니다.")

if __name__ == "__main__":
    send_telegram()
