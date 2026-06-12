import os, json, gspread, requests

def send_telegram_message(chat_id, bot_token, text):
    if not chat_id or not bot_token: 
        print("🚨 Chat ID 또는 Bot Token이 누락되어 메시지 발송을 건너뜁니다.")
        return
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id, 
        "text": text[:4000], 
        "disable_web_page_preview": True
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print(f"✅ 텔레그램 메시지 발송 성공! (수신 ID: {chat_id})")
    except Exception as e:
        print(f"❌ 텔레그램 발송 중 오류가 발생했습니다: {e}")

def run_reporter():
    creds_json = os.environ.get("GOOGLE_SHEETS_CREDENTIALS")
    if not creds_json:
        print("🚨 구글 시트 파일 인증 정보(Credentials)가 서버에 설정되지 않았습니다.")
        return

    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        json.loads(creds_json),
        ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    )
    spreadsheet = gspread.authorize(creds).open("News_Management_DB")

    try:
        sys_sheet = spreadsheet.worksheet("Config_System")
        sys_data = sys_sheet.get_all_records()
        config = {str(row.get("Key")): str(row.get("Value")) for row in sys_data}
    except Exception as e:
        print(f"🚨 Config_System 설정 시트를 읽는 데 실패했습니다: {e}")
        return

    # 대시보드 제어판의 실시간 토글 스위치 상태를 정상적으로 연동하여 불러옵니다.
    tg_group_send = config.get("TELEGRAM_GROUP_SEND", "OFF")
    tg_author_send = config.get("TELEGRAM_AUTHOR_SEND", "OFF")
    tg_author_id = config.get("TELEGRAM_AUTHOR_ID", "")

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    group_chat_id = os.environ.get("TELEGRAM_GROUP_CHAT_ID", "")

    # 깃허브 로그창에서 송신 여부를 직관적으로 진단할 수 있도록 상태 메시지를 출력합니다.
    print(f"ℹ️ 시스템 설정 검증 - 단톡방 발송: {tg_group_send}, 작성자 개인 발송: {tg_author_send}, 작성자 계정 ID: {tg_author_id}")

    try:
        top20_sheet = spreadsheet.worksheet("DB_Top20")
        data_values = top20_sheet.get_all_values()
    except Exception as e:
        print(f"🚨 DB_Top20 시트 데이터를 불러오지 못했습니다: {e}")
        return

    if len(data_values) <= 1:
        print("ℹ️ 발송 대기 중인 리포트용 기사 데이터가 시트에 존재하지 않습니다.")
        return

    # 공백 데이터 행을 전처리 필터링합니다.
    rows = [r for r in data_values[1:] if r and len(r) > 0 and r[0].strip()]
    if not rows:
        print("ℹ️ 유효한 타임스탬프를 가진 뉴스 실행 내역이 없습니다.")
        return

    latest_time = max(row[0] for row in rows)
    latest_rows = [row for row in rows if row[0] == latest_time]
    print(f"ℹ️ 가장 최근 배치 실행 타임({latest_time}) 기사 총 {len(latest_rows)}건 취합 완료.")

    msg = f"📊 [뉴스 자동화 파이프라인 리포트]\n"
    msg += f"실행 시간: {latest_time}\n\n"
    
    for idx, row in enumerate(latest_rows, 1):
        title = row[2] if len(row) > 2 else "제목 없음"
        link = row[3] if len(row) > 3 else ""
        matched_keywords = row[5] if len(row) > 5 else "-"
        base_score = row[6] if len(row) > 6 else "0"
        total_score = row[8] if len(row) > 8 else "0"
        
        msg += f"{idx}. {title}\n"
        msg += f"🔗 {link}\n"
        msg += f"⭐ 총점: {total_score} (기초: {base_score})\n"
        msg += f"🏷️ {matched_keywords}\n\n"

    # 설정 제어 스위치가 ON으로 켜져 있을 때만 실제 발송을 트리거합니다.
    if tg_group_send == "ON":
        print("📡 [부서 단톡방] 채널로 리포트 송신을 시작합니다.")
        send_telegram_message(group_chat_id, bot_token, msg)

    if tg_author_send == "ON" and tg_author_id:
        print("📡 [작성자 개인 봇] 채널로 리포트 사본 송신을 시작합니다.")
        send_telegram_message(tg_author_id, bot_token, msg)

if __name__ == "__main__":
    run_reporter()
