import os, json, gspread, difflib
from oauth2client.service_account import ServiceAccountCredentials

# 1. 설정 및 연결
creds = ServiceAccountCredentials.from_json_keyfile_dict(
    json.loads(os.environ["GOOGLE_SHEETS_CREDENTIALS"]),
    ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
)
spreadsheet = gspread.authorize(creds).open("News_Management_DB")

def is_similar(title1, title2, threshold=0.65):
    seq = difflib.SequenceMatcher(None, title1, title2)
    return seq.ratio() >= threshold

def process_base_score():
    inbox_sheet = spreadsheet.worksheet("DB_Inbox")
    stage_sheet = spreadsheet.worksheet("DB_Stage")
    keyword_sheet = spreadsheet.worksheet("Config_Keywords")
    
    # 2. 키워드 및 감점 데이터 로드 (헤더를 'Score'로 통일하여 읽기)
    try:
        kw_records = keyword_sheet.get_all_records()
        keywords = {}
        for r in kw_records:
            kw = str(r.get("Keyword", "")).strip()
            score_raw = r.get("Score")
            # Score 값이 숫자 형태인지 확인하고 변환
            score = int(score_raw) if score_raw is not None and str(score_raw).strip() != "" else 0
            if kw: keywords[kw] = score
    except Exception as e:
        print(f"키워드 로드 실패: {e}"); keywords = {}

    try:
        neg_sheet = spreadsheet.worksheet("Config_Negative")
        neg_records = neg_sheet.get_all_records()
        penalty_dict = {str(r.get("Keyword", "")).strip(): int(r.get("Score", 0)) for r in neg_records}
    except: penalty_dict = {}
        
    rows = inbox_sheet.get_all_values()
    if len(rows) <= 1: return

    # 3. 기초 점수 산정
    processed_rows = []
    for row in rows[1:]:
        if len(row) < 3: continue
        title = row[1]
        
        score = sum([pt for kw, pt in keywords.items() if kw in title])
        
        # 감점 로직 적용
        penalty = sum([pt for kw, pt in penalty_dict.items() if kw in title])
        score = max(0, score - penalty)
        
        if score > 0:
            row[5] = score # 6번째 컬럼에 점수 저장
            processed_rows.append(row)
            
    # 4. [핵심] 점수 기반 정렬 후 우선순위 중복 제거
    processed_rows.sort(key=lambda x: int(x[5]), reverse=True)
    
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
            
    # 5. DB_Stage 반영
    stage_sheet.resize(rows=1)
    if final_survivors:
        stage_sheet.append_rows(final_survivors)
        print(f"✅ 총 {len(final_survivors)}개의 우량 기사가 선별되었습니다.")
    else:
        print("⚠️ 발송 기준을 충족하는 기사가 없습니다.")

if __name__ == "__main__":
    process_base_score()
