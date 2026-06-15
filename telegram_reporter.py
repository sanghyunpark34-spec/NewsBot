import os, json, gspread, requests
from oauth2client.service_account import ServiceAccountCredentials

def send_telegram():
    is_scheduled = os.environ.get("GITHUB_EVENT_NAME") == "schedule"
    
    if is_scheduled:
        print("⏰ [스케줄 가동] 공식 정기 리포트 발송을 시작합니다.")
    else:
        print("🚀 [수동 가동] 관리자 수동 발송 테스트를 시작합니다. (발송 후에도 Sent 상태는 N으로 유지됩니다.)")

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
    
    unsent_rows = []
    unsent_indices = []
    
    for i, row in enumerate(rows[1:]):
        sent_idx = col_idx.get('Sent', 9)
        if len(row) > sent_idx and row[sent_idx] == 'N':
            unsent_rows.append(row)
            unsent_indices.append(i + 2)

    if not unsent_rows:
        print("조건에 부합하는 발송 대상 기사가 없습니다.")
        return

    msg = f"📊 뉴스 자동화 리포트\n\n"
    for i, row in enumerate(unsent_rows[:20]):
        title = row[col_idx.get('Title', 2)]
        link = row[col_idx.get('Link', 3)]
        
        msg += f"{i+1}. {title}\n"
        msg += f"🔗 {link}\n\n"

    for chat_id in target_chats:
        res = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": msg, "disable_web_page_preview": True}
        )
        if res.status_code == 200:
            print(f"✅ {chat_id} 방 발송 완료!")

    if is_scheduled:
        for idx in unsent_indices[:20]:
            ai_report_sheet.update_cell(idx, col_idx.get('Sent', 9) + 1, 'Y')
        print("🏁 공식 발송 처리 완료: 해당 기사들은 Sent='Y'로 변경되어 다음 발송에서 제외됩니다.")
    else:
        print("🏁 수동 발송 테스트 완료: 기사들의 Sent 상태는 'N'으로 유지되어 다음 스케줄에 정식 포함됩니다.")

if __name__ == "__main__":
    send_telegram()
