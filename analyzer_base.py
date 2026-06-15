import os, json, gspread, difflib
from oauth2client.service_account import ServiceAccountCredentials

# 1. 설정 및 연결
creds = ServiceAccountCredentials.from_json_keyfile_dict(
    json.loads(os.environ["GOOGLE_SHEETS_CREDENTIALS"]),
    ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
)
spreadsheet = gspread.authorize(creds).open("News_Management_DB")

def is_similar(title1, title2, threshold=0.65):
    seq = difflib.SequenceMatcher(None, title1.replace(" ", ""), title2.replace(" ", ""))
    return seq.ratio() >= threshold

def process_base_score():
    inbox_sheet = spreadsheet.worksheet("DB_Inbox")
    stage_sheet = spreadsheet.worksheet("DB_Stage")
    keyword_sheet = spreadsheet.worksheet("Config_Keywords")
    
    # 2. 매체, 키워드, 감점 데이터 로드
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

    # 💡 [핵심 복구] 100점 만점 환산을 위한 최대 분모(Max Denominator) 계산
    # 상위 4개 키워드 점수 합 + 최고 매체 점수
    top_kw_scores = sorted(keywords.values(), reverse=True)
    max_4_kw_sum = sum(top_kw_scores[:4]) if top_kw_scores else 40.0
    max_media_score = max(media_dict.values()) if media_dict else 5.0
    max_denominator = max_4_kw_sum + max_media_score
    if max_denominator <= 0: max_denominator = 45.0

    rows = inbox_sheet.get_all_values()
    if len(rows) <= 1: return

    # 3. 기초 점수 산정 및 100점 정규화
    processed_rows = []
    for row in rows[1:]:
        if len(row) < 3: continue
        date, title, url = row[0], row[1], row[2]
        
        matched_media = 'Naver'
        media_score = 0.0
        for domain, coef in media_dict.items():
            if domain in url.lower():
                matched_media = domain
                media_score = coef
                break
        
        matched_kws = []
        kw_score_sum = 0.0
        # 키워드 점수 높은 순으로 매칭하기 위해 정렬된 키워드 사용
        sorted_kw_items = sorted(keywords.items(), key=lambda item: item[1], reverse=True)
        for kw, pt in sorted_kw_items:
            if kw in title:
                matched_kws.append(f"{kw}({int(pt)})")
                kw_score_sum += pt
                
        if kw_score_sum == 0:
            continue

        applied_penalties = []
        penalty_sum = 0.0
        for pk, penalty_val in penalty_dict.items():
            if pk in title:
                applied_penalties.append(f"{pk}({int(penalty_val)})")
                penalty_sum += penalty_val
        
        # 순수 합산 점수(Raw Score)
        raw_score = max(0.0, (kw_score_sum + media_score) - penalty_sum)
        
        # 💡 [핵심 복구] 100점 만점 스케일링 (정규화)
        if raw_score > 0:
            base_score = min(round((raw_score / max_denominator) * 100, 2), 100.0)
            
            kw_str = ", ".join(matched_kws)
            if applied_penalties:
                kw_str += f" [🔻 감점: {', '.join(applied_penalties)}]"
            
            processed_rows.append([date, title, url, matched_media, kw_str, base_score])

    # 4. 점수 기반 정렬 후 우선순위 중복 제거
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
        else:
            pass # 중복 기사 조용히 탈락
            
    # 5. DB_Stage 반영
    stage_sheet.resize(rows=1)
    if final_survivors:
        stage_sheet.append_rows(final_survivors)
        print(f"✅ 총 {len(final_survivors)}개의 기사가 100점 만점 기준으로 정규화되어 선별되었습니다.")
    else:
        print("⚠️ 발송 기준을 충족하는 기사가 없습니다.")
        
    inbox_sheet.resize(rows=1)

if __name__ == "__main__":
    process_base_score()
