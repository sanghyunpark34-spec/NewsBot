import os
import json
import gspread
import requests
from oauth2client.service_account import ServiceAccountCredentials

def send_telegram_message(chat_id, bot_token, text):
    if not chat_id or not bot_token: 
        print(f"오류: 채팅 아이디({chat_id}) 또는 봇 토큰이 누락되었습니다.")
        return
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        response = requests.post(url, json={"chat_id": chat_id, "text": text[:4000], "disable_web_page_preview": True})
        response.raise_for_status()
        print(f"✅ 텔레그램 메시지 발송 성공 (수신 ID: {chat_id})")
    except Exception as e:
        print(f"❌ 텔레그램 발송 오류: {e}")

def run_reporter():
    creds_json = os.environ.get("GOOGLE_SHEETS_CREDENTIALS")
    if not creds_json:
        print("구글 시트 인증 정보가 없습니다.")
        return

    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        json.loads(creds_json),
        ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    )
    spreadsheet = gspread.authorize(creds).open("News_Management_DB")

    # 대시보드의 스위치 및 추가 수신자 상태를 가져옵니다.
    try:
        sys_data = spreadsheet.worksheet("Config_System").get_all_records()
        config = {str(row.get("Key")): str(row.get("Value")) for row in sys_data}
    except Exception as e:
        print(f"시스템 설정 읽기 실패: {e}")
        return

    tg_group_send = config.get("TELEGRAM_GROUP_SEND", "OFF")
    tg_author_send = config.get("TELEGRAM_AUTHOR_SEND", "OFF")
    extra_ids_raw = config.get("EXTRA_TELEGRAM_IDS", "")

    # 추가 수신자 ID 목록 정리 (공백 제거 및 빈 값 필터링)
    extra_ids = [eid.strip() for eid in extra_ids_raw.split(',')] if extra_ids_raw else []
    extra_ids = [eid for eid in extra_ids if eid]

    # 💡 [핵심 추가] 모든 발송 옵션이 꺼져 있고 추가 ID도 없는 경우 즉시 종료
    if tg_group_send != "ON" and tg_author_send != "ON" and not extra_ids:
        print("수신처가 지정되어 있지 않으므로 텔레그램 메세지는 발송되지 않습니다.")
        return

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    group_chat_id = os.environ.get("TELEGRAM_GROUP_CHAT_ID", "")
    my_chat_id = os.environ.get("MY_CHAT_ID", "") 

    try:
        data_values = spreadsheet.worksheet("DB_Top20").get_all_values()
        rows = [r for r in data_values[1:] if r and len(r) > 0 and r[0].strip()]
        if not rows: return print("유효한 기사 데이터가 없습니다.")
        
        latest_time = max(row[0] for row in rows)
        latest_rows = [row for row in rows if row[0] == latest_time]
    except Exception as e:
        return print(f"데이터 추출 실패: {e}")

    msg = f"📊 뉴스 자동화 리포트 ({latest_time})\n\n"
    for idx, row in enumerate(latest_rows, 1):
        msg += f"{idx}. {row[2] if len(row)>2 else '제목 없음'}\n🔗 {row[3] if len(row)>3 else ''}\n⭐ 총점: {row[8] if len(row)>8 else '0'} (기초: {row[6] if len(row)>6 else '0'})\n🏷️ {row[5] if len(row)>5 else '-'}\n\n"

    # 1. 단톡방 발송 (TELEGRAM_GROUP_CHAT_ID)
    if tg_group_send == "ON":
        print("📢 부서 단톡방 발송을 시도합니다.")
        send_telegram_message(group_chat_id, bot_token, msg)

    # 2. 작성자 개인 발송 (MY_CHAT_ID)
    if tg_author_send == "ON":
        print("👤 작성자 개인 발송을 시도합니다.")
        send_telegram_message(my_chat_id, bot_token, msg)

    # 3. 추가 수신자 발송
    for extra_id in extra_ids:
        print(f"➕ 추가 수신자 발송을 시도합니다. (ID: {extra_id})")
        send_telegram_message(extra_id, bot_token, msg)

if __name__ == "__main__":
    run_reporter()
