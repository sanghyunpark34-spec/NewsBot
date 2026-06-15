import os, json, gspread, difflib
from oauth2client.service_account import ServiceAccountCredentials

# 1. 설정 및 연결
creds = ServiceAccountCredentials.from_json_keyfile_dict(
    json.loads(os.environ["GOOGLE_SHEETS_CREDENTIALS"]),
    ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
)
spreadsheet = gspread.authorize(creds).open("News_Management_DB")

def is_similar(title1, title2, threshold=0.65):
    # 공백 무시하고 글자 패턴만 비교
    seq = difflib.SequenceMatcher(None, title1.replace(" ", ""), title2.replace(" ", ""))
    return seq.ratio() >= threshold

def process_base_score():
    inbox_sheet = spreadsheet.worksheet("DB_Inbox")
    stage_sheet = spreadsheet.worksheet("DB_Stage")
    keyword_sheet = spreadsheet.worksheet("Config_Keywords")
    
    # 미디어 시트 로드
    try: media_sheet = spreadsheet.worksheet("Config_Media")
    except: media_sheet = spreadsheet.worksheet("Config_Media_Sites")
    media_records = media_sheet.get_all_records()
    media_dict = {str(mr.get('Domain', '')).strip().lower(): float(mr.get('Weight', mr.get('Score', mr.get('Coefficient', 0)))) for mr in media_records if str(mr.get('Domain', '')).strip()}

    # 키워드 시트 로드 ('Score' 헤더 사용)
    try:
        kw_records = keyword_sheet.get_all_records()
        keywords = {}
        for r in kw_records:
            kw = str(r.get("Keyword", "")).strip()
            score_raw = r.get("Score")
            score = float(score_raw) if score_raw is not None and str(score_raw).strip() != "" else 0.0
            if kw: keywords[kw] = score
    except Exception as e:
        print(f"키워드 로드 실패: {e}"); keywords = {}

    # 감점 시트 로드
    try:
        neg_sheet = spreadsheet.worksheet("Config_Negative")
        neg_records = neg_sheet.get_all_records()
        penalty_dict = {str(r.get("Keyword", "")).strip(): float(r.get("Coefficient", r.get("Score", 20.0))) for r in neg_records if str(r.get("Keyword", "")).strip()}
    except: penalty_dict = {}

    rows = inbox_sheet.get_all_values()
    if len(rows) <= 1: return

    processed_rows = []
    for row in rows[1:]:
        if len(row) < 3: continue
        date, title, url = row[0], row[1], row[2]
        
        # 매체 점수 산출
        matched_media = 'Naver'
        media_score = 0.0
        for domain, coef in media_dict.items():
            if domain in url.lower():
                matched_media = domain
                media_score = coef
                break
        
        # 키워드 가점 확인
        matched_kws = []
        kw_score_sum = 0.0
        for kw, pt in keywords.items():
            if kw in title:
                matched_kws.append(f"{kw}({int(pt)})")
                kw_score_sum += pt
                
        # 키워드가 하나도 없으면 즉시 탈락
        if kw_score_sum == 0:
            continue

        # 감점 확인
        applied_penalties = []
        penalty_sum = 0.0
        for pk, penalty_val in penalty_dict.items():
            if pk in title:
                applied_penalties.append(f"{pk}({int(penalty_val)})")
                penalty_sum += penalty_val
        
        # 최종 기초 점수 계산
        final_score = max(0.0, (kw_score_sum + media_score) - penalty_sum)
        
        # 합격한 기사만 새로운 규격(6칸)으로 재생산
        if final_score > 0:
            kw_str = ", ".join(matched_kws)
            if applied_penalties:
                kw_str += f" [🔻 감점: {', '.join(applied_penalties)}]"
            
            # 💡 기존 데이터를 수정하지 않고 완벽한 6열 리스트로 새로 만듦 (IndexError 해결)
            processed_rows.append([date, title, url, matched_media, kw_str, final_score])

    # 💡 [핵심] 점수 내림차순 정렬 (높은 점수 우선순위)
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
            print(f"🚫 중복 탈락 (우선순위 보존): {current_title[:20]}...")
            
    # DB_Stage에 반영 및 Inbox 초기화
    stage_sheet.resize(rows=1)
    if final_survivors:
        stage_sheet.append_rows(final_survivors)
        print(f"✅ 총 {len(final_survivors)}개의 우량 기사가 선별되었습니다.")
    else:
        print("⚠️ 발송 기준을 충족하는 기사가 없습니다.")
        
    inbox_sheet.resize(rows=1)

if __name__ == "__main__":
    process_base_score()
