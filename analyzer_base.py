import os, json, gspread, difflib
from oauth2client.service_account import ServiceAccountCredentials
import pytz

# 1. 환경 설정 및 구글 시트 연결
creds = ServiceAccountCredentials.from_json_keyfile_dict(
    json.loads(os.environ["GOOGLE_SHEETS_CREDENTIALS"]),
    ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
)
spreadsheet = gspread.authorize(creds).open("News_Management_DB")

def is_similar(title1, title2, threshold=0.65):
    """제목 유사도 비교 로직"""
    seq = difflib.SequenceMatcher(None, title1, title2)
    return seq.ratio() >= threshold

def process_base_score():
    """기초 점수 산정 및 우선순위 기반 중복 제거"""
    stage_sheet = spreadsheet.worksheet("DB_Stage")
    keyword_sheet = spreadsheet.worksheet("Config_Keywords")
    
    # 데이터 가져오기
    rows = stage_sheet.get_all_values()
    if len(rows) <= 1: return
    
    keywords = {str(r.get("Keyword")): int(r.get("Score")) for r in keyword_sheet.get_all_records()}
    
    # 기초 점수 산정 및 데이터 정제
    processed_rows = []
    for row in rows[1:]:
        title = row[1]
        score = 0
        for kw, pt in keywords.items():
            if kw in title:
                score += pt
        
        # 점수가 0점인 기사는 가차 없이 탈락 (필터링 강화)
        if score > 0:
            row[5] = score # 점수 업데이트
            processed_rows.append(row)
            
    # 💡 [핵심 수정] 우선순위 기반 중복 제거
    # 1. 기사들을 기초 점수(index 5) 내림차순으로 먼저 정렬 (높은 점수 우선)
    processed_rows.sort(key=lambda x: int(x[5]), reverse=True)
    
    final_survivors = []
    accepted_titles = []
    
    for row in processed_rows:
        current_title = row[1]
        is_duplicate = False
        
        # 2. 이미 합격한 기사들과 유사도 비교
        for accepted_title in accepted_titles:
            if is_similar(current_title, accepted_title, threshold=0.65):
                is_duplicate = True
                break
        
        # 3. 중복되지 않은 기사만 생존
        if not is_duplicate:
            final_survivors.append(row)
            accepted_titles.append(current_title)
        else:
            print(f"🚫 중복 탈락 (우선순위 보존): {current_title[:20]}...")
            
    # 시트 비우고 생존 기사만 다시 기록
    stage_sheet.resize(rows=1)
    if final_survivors:
        stage_sheet.append_rows(final_survivors)
        print(f"✅ {len(final_survivors)}개의 우량 기사가 선별되었습니다.")
    else:
        print("⚠️ 발송 기준을 충족하는 기사가 없습니다.")

if __name__ == "__main__":
    process_base_score()
