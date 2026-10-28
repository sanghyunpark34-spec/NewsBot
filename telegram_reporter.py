import os, json, gspread, requests
from datetime import datetime, timedelta
import pytz
import holidays
from oauth2client.service_account import ServiceAccountCredentials

from google import genai
from groq import Groq
import anthropic

KST = pytz.timezone('Asia/Seoul')

DEFAULT_QUOTAS = [
    ["A. 한화 및 계열사", 5, "한화생명, 한화손보 등 금융 계열사 및 한화그룹 지배구조/승계/주요 딜"],
    ["B. 보험/금융 본업 및 규제", 6, "타 보험사/금융지주 동향, K-ICS, 금감원/금융위 규제 및 인사"],
    ["C. PEF 및 일반 M&A 딜", 6, "사모펀드(PEF) 동향, 비금융/일반 산업 주요 M&A 라이브 딜"],
    ["D. 글로벌 및 신사업/기타", 5, "해외 크로스보더 딜, 디지털자산/STO, 기타 주요 경제/금융 이슈"]
]

def get_previous_working_day_cutoff(current_time):
    kr_holidays = holidays.KR()
    days_to_subtract = 1
    while True:
        target_date = current_time - timedelta(days=days_to_subtract)
        if target_date.weekday() < 5 and target_date.date() not in kr_holidays:
            return target_date
        days_to_subtract += 1

def get_sector_quota_prompt(spreadsheet):
    """Config_Quota 시트에서 섹터별 쿼터 설정을 읽어와 프롬프트 텍스트로 변환합니다. 시트가 없으면 자동 생성합니다."""
    try:
        try:
            quota_sheet = spreadsheet.worksheet("Config_Quota")
        except Exception:
            quota_sheet = spreadsheet.add_worksheet(title="Config_Quota", rows="50", cols="3")
            quota_sheet.append_row(["Sector", "Max_Count", "Description"])
            quota_sheet.append_rows(DEFAULT_QUOTAS)
        
        records = quota_sheet.get_all_records()
        if not records:
            return ""
            
        quota_text = "\n[섹터별 최대 선발 쿼터(상한선) 기준]\n"
        for r in records:
            sector = str(r.get("Sector", "")).strip()
            max_cnt = r.get("Max_Count", 5)
            desc = str(r.get("Description", "")).strip()
            if sector:
                quota_text += f"- {sector} (최대 {max_cnt}개 이하): {desc}\n"
        return quota_text
    except Exception as e:
        print(f"⚠️ 쿼터 시트 로드 중 예외 발생 (기본 중복 제거만 수행): {e}")
        return ""

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
        engine_choice = config.get("AI_ENGINE", "유료 Claude")
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

    unsent_data.sort(key=lambda x: float(x[0][col_idx.get('Total_Score', 8)]) if x[0][col_idx.get('Total_Score', 8)].replace('.', '', 1).isdigit() else 0.0, reverse=True)

    print("🕵️‍♂️ 발송 직전 AI 편집장의 최종 중복 검수 및 섹터 쿼터 큐레이션을 시작합니다.")
    
    # 💡 200개 채점 풀을 활용하기 위해 편집장 검토 후보군을 상위 80개로 확대
    curation_candidates = unsent_data[:80]
    quota_guide = get_sector_quota_prompt(spreadsheet)

    prompt_text = "당신은 금융그룹 경영전략실의 최종 데스크 편집장입니다. 아래는 이미 중요도(점수) 순으로 정렬된 상위 후보 기사 목록입니다.\n\n"
    prompt_text += "[지시사항]\n"
    prompt_text += "1. 목록을 읽고, 다루는 핵심 이슈(기업, 딜, 사건)가 실질적으로 완전히 동일한 '중복 기사'들을 식별하세요.\n"
    prompt_text += "2. 중복된 기사 묶음이 있다면, 무조건 '가장 먼저 등장하는(ID가 빠른=점수가 높은) 기사' 딱 1개만 남기고 나머지는 제외하세요.\n"
    if quota_guide:
        prompt_text += "3. 특정 분야(예: 보험 등)에 기사가 편중되지 않도록, 아래 제시된 [섹터별 최대 선발 쿼터 기준]을 준수하여 다양한 분야에서 골고루 기사를 선발하세요. 특정 섹터가 최대 허용 개수를 채웠다면, 점수가 조금 낮더라도 다른 섹터의 차순위 핵심 기사를 끌어올려 균형을 맞추세요.\n"
        prompt_text += "4. 최종적으로 발송할 [고유하고 섹터 균형이 잡힌 기사 최대 20개의 ID]만을 중요도 순서대로 JSON 배열(예: [1, 2, 5, 8]) 형식으로 반환하세요. 다른 설명은 절대 넣지 마세요.\n"
        prompt_text += quota_guide
    else:
        prompt_text += "3. 최종적으로 발송할 [고유하고 핵심적인 기사 최대 20개의 ID]만을 순서대로 JSON 배열(예: [1, 2, 5, 8]) 형식으로 반환하세요. 다른 설명은 절대 넣지 마세요.\n"
        
    prompt_text += "\n[기사 목록]\n"
    
    for temp_id, (row, _) in enumerate(curation_candidates):
        title = row[col_idx.get('Title', 2)]
        kws = row[col_idx.get('Matched_Keywords', 5)] if len(row) > col_idx.get('Matched_Keywords', 5) else ""
        prompt_text += f"ID: {temp_id + 1} | 제목: {title} | 키워드: {kws}\n"

    ai_filtered_ids = []
    try:
        res_json = ""
        if ("Claude" in engine_choice or "전체" in engine_choice) and os.environ.get("CLAUDE_API_KEY"):
            client = anthropic.Anthropic(api_key=os.environ.get("CLAUDE_API_KEY"))
            msg = client.messages.create(model="claude-haiku-4-5-20251001", max_tokens=600, messages=[{"role": "user", "content": prompt_text}])
            res_json = msg.content[0].text
        elif "Gemini" in engine_choice and os.environ.get("GEMINI_API_KEY"):
            client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
            res_json = client.models.generate_content(
                model='gemini-1.5-flash', 
                contents=prompt_text
            ).text
        elif "Groq" in engine_choice and os.environ.get("GROQ_API_KEY"):
            client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
            res = client.chat.completions.create(model="llama3-70b-8192", messages=[{"role": "user", "content": prompt_text}])
            res_json = res.choices[0].message.content

        start, end = res_json.find('['), res_json.rfind(']')
        if start != -1 and end != -1:
            ai_filtered_ids = json.loads(res_json[start:end+1])
            print(f"✨ AI 편집장 검수 완료! 섹터 밸런싱이 적용된 고유 기사 {len(ai_filtered_ids)}개가 최종 선정되었습니다.")
    except Exception as e:
        print(f"⚠️ AI 큐레이션 지연으로 기본 정렬 기준 20개를 발송합니다. ({e})")
        ai_filtered_ids = list(range(1, 21))

    final_top_data = []
    seen_urls = set()
    
    for temp_id in ai_filtered_ids:
        try:
            idx = int(temp_id) - 1
        except:
            continue
        if 0 <= idx < len(curation_candidates):
            row_data = curation_candidates[idx]
            link = row_data[0][col_idx.get('Link', 3)]
            if link not in seen_urls:
                seen_urls.add(link)
                final_top_data.append(row_data)
                if len(final_top_data) == 20: break

    msg = f"📊 뉴스 자동화 큐레이션 리포트\n\n"
    for i, (row, original_idx) in enumerate(final_top_data):
        title = row[col_idx.get('Title', 2)]
        link = row[col_idx.get('Link', 3)]
        msg += f"{i+1}. {title}\n🔗 {link}\n\n"

    for chat_id in target_chats:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": chat_id, "text": msg, "disable_web_page_preview": True})

    if is_scheduled:
        sent_updates = [{'range': gspread.utils.rowcol_to_a1(orig_idx, col_idx.get('Sent', 9) + 1), 'values': [['Y']]} for _, orig_idx in final_top_data]
        if sent_updates: ai_report_sheet.batch_update(sent_updates)

if __name__ == "__main__":
    send_telegram()
