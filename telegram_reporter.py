import os
import json
import gspread
import requests
from oauth2client.service_account import ServiceAccountCredentials

def send_telegram_message(chat_id, bot_token, text):
    if not chat_id or not bot_token: 
        print("채팅 아이디 또는 봇 토큰이 누락되어 메시지 발송을 건너뜁니다.")
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
        print(f"텔레그램 메시지 발송에 성공했습니다. 수신 아이디는 {chat_id} 입니다.")
    except Exception as e:
        print(f"텔레그램 발송 중 오류가 발생했습니다. 구체적인 오류는 {e} 입니다.")

def run_reporter():
    creds_json = os.environ.get("GOOGLE_SHEETS_CREDENTIALS")
    if not creds_json:
        print("구글 시트 파일 인증 정보가 서버에 설정되지 않았습니다.")
        return

    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        json.loads(creds_json),
        ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    )
    spreadsheet = gspread.authorize(creds).open("News_Management_DB")

    try:
        sys_sheet = spreadsheet.worksheet("Config_System")
        sys_data = sys_sheet.get_all_records()
        config = {}
        for row in sys_data:
            config[str(row.get("Key"))] = str(row.get("Value"))
    except Exception as e:
        print(f"시스템 설정 시트를 읽는 데 실패했습니다. 오류 내용은 {e} 입니다.")
        return

    tg_group_send = config.get("TELEGRAM_GROUP_SEND", "OFF")
    tg_author_send = config.get("TELEGRAM_AUTHOR_SEND", "OFF")
    tg_author_id = config.get("TELEGRAM_AUTHOR_ID", "")

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    group_chat_id = os.environ.get("TELEGRAM_GROUP_CHAT_ID", "")

    print(f"시스템 설정 검증을 진행합니다. 단톡방 발송은 {tg_group_send} 이고 작성자 개인 발송은 {tg_author_send} 이며 작성자 계정 아이디는 {tg_author_id} 입니다.")

    try:
        top20_sheet = spreadsheet.worksheet("DB_Top20")
        data_values = top20_sheet.get_all_values()
    except Exception as e:
        print(f"탑 20 시트 데이터를 불러오지 못했습니다. 오류 내용은 {e} 입니다.")
        return

    if len(data_values) <= 1:
        print("발송 대기 중인 리포트용 기사 데이터가 시트에 존재하지 않습니다.")
        return

    rows = []
    for r in data_values[1:]:
        if r and len(r) > 0 and r[0].strip():
            rows.append(r)
            
    if not rows:
        print("유효한 시간 기록을 가진 뉴스 실행 내역이 없습니다.")
        return

    latest_time = max(row[0] for row in rows)
    latest_rows = []
    for row in rows:
        if row[0] == latest_time:
            latest_rows.append(row)
            
    print(f"가장 최근 실행 시간인 {latest_time} 의 기사 총 {len(latest_rows)}건을 취합했습니다.")

    msg = "뉴스 자동화 파이프라인 리포트입니다.\n"
    msg += f"실행 시간은 {latest_time} 입니다.\n\n"
    
    for idx, row in enumerate(latest_rows, 1):
        title = row[2] if len(row) > 2 else "제목 없음"
        link = row[3] if len(row) > 3 else ""
        matched_keywords = row[5] if len(row) > 5 else "없음"
        base_score = row[6] if len(row) > 6 else "0"
        total_score = row[8] if len(row) > 8 else "0"
        
        msg += f"{idx}번 기사는 {title} 입니다.\n"
        msg += f"링크는 {link} 입니다.\n"
        msg += f"총점은 {total_score}점 이고 기초 점수는 {base_score}점 입니다.\n"
        msg += f"매칭된 키워드는 {matched_keywords} 입니다.\n\n"

    if tg_group_send == "ON":
        print("부서 단톡방 채널로 리포트 송신을 시작합니다.")
        send_telegram_message(group_chat_id, bot_token, msg)

    if tg_author_send == "ON" and tg_author_id:
        print("작성자 개인 봇 채널로 리포트 사본 송신을 시작합니다.")
        send_telegram_message(tg_author_id, bot_token, msg)

if __name__ == "__main__":
    run_reporter()
