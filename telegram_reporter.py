import os, json, gspread, requests
from oauth2client.service_account import ServiceAccountCredentials

def send_telegram_message(chat_id, bot_token, text):
    if not chat_id or not bot_token: 
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
    except Exception as e:
        print(f"텔레그램 발송 중 오류가 발생했습니다. {e}")

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

    try:
        sys_sheet = spreadsheet.worksheet("Config_System")
        sys_data = sys_sheet.get_all_records()
        config = {str(row.get("Key")): str(row.get("Value")) for row in sys_data}
    except Exception as e:
        print(f"설정 시트를 읽는 데 실패했습니다. {e}")
        return

    tg_group_send = config.get("TELEGRAM_GROUP_SEND", "OFF")
    tg_author_send = config.get("TELEGRAM_AUTHOR_SEND", "OFF")
    tg_author_id = config.get("TELEGRAM_AUTHOR_ID", "")

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    group_chat_id = os.environ.get("TELEGRAM_GROUP_CHAT_ID", "")

    try:
        top20_sheet = spreadsheet.worksheet("DB_Top20")
        # pandas 없이 구글 시트의 데이터를 기본 리스트로 가볍게 가져옵니다.
        data_values = top20_sheet.get_all_values()
    except Exception as e:
        print(f"Top 20 데이터를 불러오지 못했습니다. {e}")
        return

    if len(data_values) <= 1:
        print("발송할 최신 데이터가 없습니다.")
        return

    # 첫 번째 행(헤더)을 제외하고, 실행 시간(0번째 인덱스) 기준 가장 최근 데이터만 필터링합니다.
    rows = data_values[1:]
    latest_time = max(row[0] for row in rows)
    latest_rows = [row for row in rows if row[0] == latest_time]

    msg = f"📊 [뉴스 자동화 파이프라인 리포트]\n"
    msg += f"실행 시간: {latest_time}\n\n"
    
    for idx, row in enumerate(latest_rows, 1):
        # 시트 구조: 0:Exec_Time, 1:Date, 2:Title, 3:Link, 4:Media, 5:Keywords, 6:Base_Score, 7:AI_Score, 8:Total_Score
        title = row[2] if len(row) > 2 else "제목 없음"
        link = row[3] if len(row) > 3 else ""
        matched_keywords = row[5] if len(row) > 5 else "-"
        base_score = row[6] if len(row) > 6 else "0"
        total_score = row[8] if len(row) > 8 else "0"
        
        msg += f"{idx}. {title}\n"
        msg += f"🔗 {link}\n"
        msg += f"⭐ 총점: {total_score} (기초: {base_score})\n"
        msg += f"🏷️ {matched_keywords}\n\n"

    if tg_group_send == "ON":
        print("부서 단톡방으로 메시지 전송을 시도합니다.")
        send_telegram_message(group_chat_id, bot_token, msg)

    if tg_author_send == "ON" and tg_author_id:
        print("작성자에게 메시지 전송을 시도합니다.")
        send_telegram_message(tg_author_id, bot_token, msg)

if __name__ == "__main__":
    run_reporter()
