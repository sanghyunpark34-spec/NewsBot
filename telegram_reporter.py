import os, json, gspread, requests
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd

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
    tg_author_send = config
