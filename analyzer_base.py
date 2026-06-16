import os, json, gspread, difflib
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
        if target_date.weekday() < 5 and target_date.date() not in kr_holidays:
            return target_date
        days_to_subtract += 1

def is_similar(title1, title2, threshold=0.65):
    seq = difflib.SequenceMatcher(None, title1.replace(" ", ""), title2.replace(" ", ""))
    return seq.ratio() >= threshold

def process_base_score():
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        json.loads(os.environ["GOOGLE_SHEETS_CREDENTIALS"]),
        ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    )
    spreadsheet = gspread.authorize(creds).open("News_Management_DB")

    inbox_sheet = spreadsheet.worksheet("DB_Inbox")
    stage_sheet = spreadsheet.worksheet("DB_Stage")
    keyword_sheet = spreadsheet.worksheet("Config_Keywords")
    
    try: media_sheet = spreadsheet.worksheet("Config_Media")
    except: media_sheet = spreadsheet.worksheet("Config_Media_Sites")
    media_records = media_sheet.get_all_records()
    media_dict = {str(mr.get('Domain', '')).strip().lower(): float(mr.get('Weight', mr.get('Score', mr.get('Coefficient', 0)))) for mr in media_records if str(mr.get('Domain', '')).strip()}

    try:
        kw_records = keyword_sheet.get_all_records()
        keywords = {}
        for r in kw_records:
            kw = str(r.get("Keyword", "")).strip()
            score_raw = r.get("Score")
            score = float(score_raw) if score_raw is not None and str(score_raw).strip() != "" else 0.0
            if kw: keywords[kw] = score
    except Exception as e: keywords = {}

    try:
        neg_sheet = spreadsheet.worksheet("Config_Negative")
        neg_records = neg_sheet.get_all_records()
        penalty_dict = {str(r.get("Keyword", "")).strip(): float(r.get("Coefficient", r.get("Score", 20.0))) for r in neg_records if str(r.get("Keyword", "")).strip()}
    except: penalty_dict = {}

    top_kw_scores = sorted(keywords.values(), reverse=True)
    max_3_kw_sum = sum(top_kw_scores[:3]) if top_kw_scores else 30.0
    max_media_score = max(media_dict.values()) if media_dict else 5.0
    max_denominator = max_3_kw_sum + max_media_score
    if max_denominator <= 0: max_denominator = 35.0

    rows = inbox_sheet.get_all_values()
    if len(rows) <= 1: return

    # 💡 [핵심 보완] 1영업일 전 커트라인 시간 생성
    now = datetime.now(KST)
    cutoff_time = get_previous_working_day_cutoff(now)

    processed_rows = []
    for row in rows[1:]:
        if len(row) < 3: continue
        date_str, title, url = row[0], row[1], row[2]
        
        # 💡 [핵심 보완] 조기 검역소: 1영업일 지난 기사는 AI 채점기로 안 넘기고 여기서 즉시 폐기!
        try:
            row_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            row_date = KST.localize(row_date)
            if row_date < cutoff_time:
                continue 
        except:
            pass

        desc = row[3] if len(row) > 3 else ""
        
        matched_media = 'Naver'
        media_score = 0.0
        for domain, coef in media_dict.items():
            if domain in url.lower():
                matched_media = domain
                media_score = coef
                break
        
        matched_kws = []
        kw_score_sum = 0.0
        sorted_kw_items = sorted(keywords.items(), key=lambda item: item[1], reverse=True)
        
        for kw, pt in sorted_kw_items:
            if kw in title or kw in desc:
                if len(matched_kws) < 3:
                    matched_kws.append(f"{kw}({int(pt)})")
                    kw_score_sum += pt
                
        if kw_score_sum == 0: continue

        applied_penalties = []
        penalty_sum = 0.0
        for pk, penalty_val in penalty_dict.items():
            if pk in title or pk in desc:
                applied_penalties.append(f"{pk}({int(penalty_val)})")
                penalty_sum += penalty_val
        
        raw_score = max(0.0, (kw_score_sum + media_score) - penalty_sum)
        
        if raw_score > 0:
            base_score = min(round((raw_score / max_denominator) * 100, 2), 100.0)
            kw_str = ", ".join(matched_kws)
            if applied_penalties:
                kw_str += f" [🔻 감점: {', '.join(applied_penalties)}]"
            processed_rows.append([date_str, title, url, matched_media, kw_str, base_score, desc])

    processed_rows.sort(key=lambda x: float(x[5]), reverse=True)
    
    final_survivors = []
    accepted_titles = []
    
    for row in processed_rows:
        current_title = row[1]
        is_duplicate = False
        for accepted_title in accepted_titles:
            if is_similar(current_title, accepted_title, threshold=0.65):
                is_duplicate = True
                break
        if not is_duplicate:
            final_survivors.append(row)
            accepted_titles.append(current_title)
            
    stage_sheet.resize(rows=1)
    if final_survivors:
        stage_sheet.append_rows(final_survivors)
        print(f"✅ 총 {len(final_survivors)}개의 기사가 요약문 검증(1영업일 조기 검역 완료)을 거쳐 선별되었습니다.")
    else:
        print("⚠️ 발송 기준을 충족하는 신선한 기사가 없습니다.")
        
    inbox_sheet.resize(rows=1)

if __name__ == "__main__":
    process_base_score()
