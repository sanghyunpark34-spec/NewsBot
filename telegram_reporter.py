import os, json, gspread, requests, time
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import pytz

KST = pytz.timezone('Asia/Seoul')

def send_telegram_message(chat_id, bot_token, text):
    if not chat_id or not bot_token: return False
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        res = requests.post(url, json={"chat_id": chat_id, "text": text[:4000], "disable_web_page_preview": True})
        res.raise_for_status()
        return True
    except Exception as e:
        print(f"발송 중 오류가 발생했습니다. 내용은 {e} 입니다.")
        return False

def run_reporter():
    creds_json = os.environ.get("GOOGLE_SHEETS_CREDENTIALS")
    if not creds_json: return
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        json.loads(creds_json), ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    )
    spreadsheet = gspread.authorize(creds).open("News_Management_DB")

    sys_data = spreadsheet.worksheet("Config_System").get_all_records()
    config = {str(r.get("Key")): str(r.get("Value")) for r in sys_data}
    
    tg_group_send = config.get("TELEGRAM_GROUP_SEND", "OFF")
    tg_author_send = config.get("TELEGRAM_AUTHOR_SEND", "OFF")
    extra_ids = [eid.strip() for eid in config.get("EXTRA_TELEGRAM_IDS", "").split(',') if eid.strip()]

    if tg_group_send != "ON" and tg_author_send != "ON" and not extra_ids:
        return print("수신처가 지정되어 있지 않으므로 메세지는 발송되지 않습니다.")

    is_schedule = (os.environ.get("GITHUB_EVENT_NAME") == "schedule")
    
    now_kst = datetime.now(KST)
    lookback_days = 3.5 if now_kst.weekday() in [0, 5, 6] else 1.5
    cutoff_date = (now_kst - timedelta(days=lookback_days)).replace(tzinfo=None)

    archive_sheet = spreadsheet.worksheet("DB_Archive")
    all_records = archive_sheet.get_all_values()
    
    valid_articles = []
    rows_to_mark_sent = [] 

    for idx, r in enumerate(all_records[1:], start=2):
        if len(r) < 9: continue
        
        try:
            pub_date = datetime.strptime(r[0], "%Y-%m-%d %H:%M:%S")
            if pub_date < cutoff_date: continue
        except Exception: continue
            
        if is_schedule and str(r[8]).strip().upper() == 'Y':
            continue
            
        valid_articles.append((idx, r))

    if not valid_articles:
        return print("조건에 부합하는 발송 대상 기사가 없습니다.")

    valid_articles.sort(key=lambda x: float(x[1][7]) if str(x[1][7]).replace('.', '', 1).isdigit() else 0.0, reverse=True)
    top20_articles = valid_articles[:20]

    msg = f"📊 뉴스 자동화 리포트 ({now_kst.strftime('%Y-%m-%d %H:%M')})\n\n"
    for rank, (sheet_row_idx, row) in enumerate(top20_articles, 1):
        msg += f"{rank}. {row[1]}\n🔗 {row[2]}\n⭐ 총점: {row[7]}점 (AI 세부 평가: {row[6]})\n🏷️ {row[4]}\n\n"
        if is_schedule: rows_to_mark_sent.append(sheet_row_idx)

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    group_chat_id = os.environ.get("TELEGRAM_GROUP_CHAT_ID", "")
    my_chat_id = os.environ.get("MY_CHAT_ID", "") 

    sent_success = False
    if tg_group_send == "ON": sent_success = send_telegram_message(group_chat_id, bot_token, msg) or sent_success
    if tg_author_send == "ON": sent_success = send_telegram_message(my_chat_id, bot_token, msg) or sent_success
    for eid in extra_ids: sent_success = send_telegram_message(eid, bot_token, msg) or sent_success

    if is_schedule and sent_success and rows_to_mark_sent:
        print(f"스케줄 발송 성공으로 {len(rows_to_mark_sent)}개의 기사를 발송 완료 처리합니다.")
        for row_idx in rows_to_mark_sent:
            archive_sheet.update_cell(row_idx, 9, 'Y')
            time.sleep(1) 

if __name__ == "__main__":
    run_reporter()
