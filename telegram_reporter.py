import os, json, gspread, requests
from datetime import datetime, timedelta
import pytz
import holidays
from oauth2client.service_account import ServiceAccountCredentials

# 💡 AI 편집장 호출을 위한 라이브러리 추가
import google.generativeai as genai
from groq import Groq
import anthropic

KST = pytz.timezone('Asia/Seoul')

def get_previous_working_day_cutoff(current_time):
    kr_holidays = holidays.KR()
    days_to_subtract = 1
    while True:
        target_date = current_time - timedelta(days=days_to_subtract)
        if target_date.weekday() < 5 and target_date.date() not in kr_holidays:
            return target_date
        days_to_subtract += 1

def send_telegram():
    is_scheduled = os.environ.get("GITHUB_EVENT_NAME") == "schedule"
    now = datetime.now(KST)
    cutoff_time = get_previous_working_day_cutoff(now)
    
    BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not BOT_TOKEN: return

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
        engine_choice = config.get("AI_ENGINE", "유료 Claude") # 💡 AI 편집장 엔진 선택용
    except:
        send_group, send_author, extra_ids, engine_choice = False, False, [], "유료 Claude"

    target_chats = list(set([os.environ.get("TELEGRAM_GROUP_CHAT_ID")] * send_group + [os.environ.get("MY_CHAT_ID")] * send_author + extra_ids))
    target_chats = [x for x in target_chats if x]
    if not target_chats: return

    ai_report_sheet = spreadsheet.worksheet("DB_AI_Report")
    rows = ai_report_sheet.get_all_values()
    if len(rows) <= 1: return

    headers = rows[0]
    col_idx = {h: i for i, h in enumerate(headers)}
    
    unsent_data = [] 
    expire_updates = []
    
    # 1. 1영업일 초과 기사 만료 처리 및 신선한 기사 수집
    for i, row in enumerate(rows[1:]):
        idx = i + 2
        if len(row) > col_idx.get('Sent', 9) and row[col_idx.get('Sent', 9)] == 'N':
            try:
                row_date = KST.localize(datetime.strptime(row[col_idx.get('Date', 1)], "%Y-%m-%d %H:%M:%S"))
            except:
                row_date = now
            if row_date < cutoff_time:
                expire_updates.append({'range': gspread.utils.rowcol_to_a1(idx, col_idx.get('Sent', 9) + 1), 'values': [['E']]})
            else:
                unsent_data.append((row, idx))

    if expire_updates: ai_report_sheet.batch_update(expire_updates)
    if not unsent_data: return

    # 2. 총점(Total_Score) 기준 1차 내림차순 정렬
    unsent_data.sort(key=lambda x: float(x[0][col_idx.get('Total_Score', 8)]) if x[0][col_idx.get('Total_Score', 8)].replace('.', '', 1).isdigit() else 0.0, reverse=True)

    # 💡 3. [핵심] AI 편집장을 통한 2차 큐레이션 (중복 제거)
    print("🕵️‍♂️ 발송 직전 AI 편집장의 최종 중복 검수 및 큐레이션을 시작합니다.")
    
    curation_candidates = unsent_data[:40] # 최대 40개를 AI에게 넘겨서 평가시킴
    prompt_text = "당신은 금융그룹 경영전략실의 최종 데스크 편집장입니다. 아래는 이미 중요도(점수) 순으로 정렬된 기사 목록입니다.\n\n"
    prompt_text += "[지시사항]\n1. 목록을 읽고, 다루는 핵심 이슈(기업, 딜, 사건)가 실질적으로 완전히 동일한 '중복 기사'들을 식별하세요.\n"
    prompt_text += "2. 중복된 기사 묶음이 있다면, 무조건 '가장 먼저 등장하는(ID가 빠른=점수가 높은) 기사' 딱 1개만 남기고 나머지는 제외하세요.\n"
    prompt_text += "3. 최종적으로 발송할 [고유하고 핵심적인 기사 최대 20개의 ID]만을 순서대로 JSON 배열(예: [1, 2, 5, 8]) 형식으로 반환하세요. 다른 설명은 절대 넣지 마세요.\n\n[기사 목록]\n"
    
    for temp_id, (row, _) in enumerate(curation_candidates):
        prompt_text += f"ID: {temp_id + 1} | 제목: {row[col_idx.get('Title', 2)]}\n"

    ai_filtered_ids = []
    try:
        res_json = ""
        if "Claude" in engine_choice and os.environ.get("CLAUDE_API_KEY"):
            client = anthropic.Anthropic(api_key=os.environ.get("CLAUDE_API_KEY"))
            msg = client.messages.create(model="claude-haiku-4-5-20251001", max_tokens=500, messages=[{"role": "user", "content": prompt_text}])
            res_json = msg.content[0].text
        elif "Gemini" in engine_choice and os.environ.get("GEMINI_API_KEY"):
            genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
            model = genai.GenerativeModel('gemini-1.5-flash')
            res_json = model.generate_content(prompt_text).text
        elif "Groq" in engine_choice and os.environ.get("GROQ_API_KEY"):
            client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
            res = client.chat.completions.create(model="llama3-70b-8192", messages=[{"role": "user", "content": prompt_text}])
            res_json = res.choices[0].message.content

        # 반환된 텍스트에서 JSON 리스트 추출
        start, end = res_json.find('['), res_json.rfind(']')
        if start != -1 and end != -1:
            ai_filtered_ids = json.loads(res_json[start:end+1])
            print(f"✨ AI 편집장 검수 완료! 고유 기사 {len(ai_filtered_ids)}개가 최종 선정되었습니다.")
    except Exception as e:
        print(f"⚠️ AI 큐레이션 지연으로 기본 정렬 기준 20개를 발송합니다. ({e})")
        ai_filtered_ids = list(range(1, 21)) # 에러 시 기본 위에서 20개 선택

    # AI가 선택한 ID 번호를 기반으로 최종 발송 리스트 구성
    final_top_data = []
    seen_urls = set() # 물리적 URL 중복 방지 (안전망)
    
    for temp_id in ai_filtered_ids:
        idx = temp_id - 1
        if 0 <= idx < len(curation_candidates):
            row_data = curation_candidates[idx]
            link = row_data[0][col_idx.get('Link', 3)]
            if link not in seen_urls:
                seen_urls.add(link)
                final_top_data.append(row_data)
                if len(final_top_data) == 20: break

    # 4. 메시지 조립 및 전송
    msg = f"📊 뉴스 자동화 큐레이션 리포트\n\n"
    for i, (row, original_idx) in enumerate(final_top_data):
        title = row[col_idx.get('Title', 2)]
        link = row[col_idx.get('Link', 3)]
        msg += f"{i+1}. {title}\n🔗 {link}\n\n"

    for chat_id in target_chats:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": chat_id, "text": msg, "disable_web_page_preview": True})

    # 5. 발송 처리 (Y)
    if is_scheduled:
        sent_updates = [{'range': gspread.utils.rowcol_to_a1(orig_idx, col_idx.get('Sent', 9) + 1), 'values': [['Y']]} for _, orig_idx in final_top_data]
        if sent_updates: ai_report_sheet.batch_update(sent_updates)

if __name__ == "__main__":
    send_telegram()
