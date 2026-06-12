import os, json, gspread
from oauth2client.service_account import ServiceAccountCredentials

creds = ServiceAccountCredentials.from_json_keyfile_dict(
    json.loads(os.environ["GOOGLE_SHEETS_CREDENTIALS"]),
    ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
)
spreadsheet = gspread.authorize(creds).open("News_Management_DB")

def process_base_score():
    inbox_sheet = spreadsheet.worksheet("DB_Inbox")
    stage_sheet = spreadsheet.worksheet("DB_Stage")
    keyword_sheet = spreadsheet.worksheet("Config_Keywords")
    
    try: media_sheet = spreadsheet.worksheet("Config_Media")
    except: media_sheet = spreadsheet.worksheet("Config_Media_Sites")
        
    # 제외 단어와 감점 계수(Coefficient)를 딕셔너리로 빌드합니다.
    try:
        neg_sheet = spreadsheet.worksheet("Config_Negative")
        neg_records = neg_sheet.get_all_records()
        penalty_dict = {}
        for r in neg_records:
            kw = str(r.get('Keyword', '')).strip()
            if not kw: continue
            # 오류 방지를 위해 기본 예비 값을 20.0에서 2.0으로 낮추고 시트 값을 우선적으로 읽습니다.
            try: val = float(r.get('Coefficient', r.get('Weight', 2.0)))
            except: val = 2.0
            penalty_dict[kw] = val
    except:
        penalty_dict = {}
        
    rows = inbox_sheet.get_all_values()
    if len(rows) <= 1: return

    keyword_records = keyword_sheet.get_all_records()
    media_records = media_sheet.get_all_records()
    
    # 기준 분모 산정을 위한 가중치 최고점 추출
    kw_weights = []
    for kw_rec in keyword_records:
        try: w = float(kw_rec.get('Weight', kw_rec.get('Coefficient', 1.0)))
        except: w = 1.0
        kw_weights.append(w)
    max_kw_weight = max(kw_weights) if kw_weights else 10.0

    media_weights = []
    for mr in media_records:
        try: w = float(mr.get('Weight', mr.get('Coefficient', 0.0)))
        except: w = 0.0
        media_weights.append(w)
    max_media_weight = max(media_weights) if media_weights else 5.0

    max_denominator = max_kw_weight + max_media_weight
    if max_denominator == 0: max_denominator = 15.0

    media_dict = {str(mr.get('Domain', '')).strip().lower(): float(mr.get('Weight', mr.get('Coefficient', 0))) for mr in media_records if str(mr.get('Domain', '')).strip()}

    stage_rows = []
    for row in rows[1:]:
        if len(row) < 3: continue
        date, title, url = row[0], row[1], row[2]
        
        # 1. 언론사 점수 매칭
        matched_media = 'Naver' 
        media_score = 0.0
        for domain, coef in media_dict.items():
            if domain in url.lower():
                matched_media = domain
                media_score = coef
                break
                
        # 2. 긍정 키워드 매칭 및 원본 점수 합산
        matched_coefs = []
        matched_kw_details = []
        for kw_rec in keyword_records:
            kw = str(kw_rec.get('Keyword', '')).strip()
            if not kw: continue
            try: coef = float(kw_rec.get('Weight', kw_rec.get('Coefficient', 1.0)))
            except: coef = 1.0
            if kw in title: 
                matched_coefs.append(coef)
                matched_kw_details.append((coef, f"{kw}({int(coef)})"))
        
        matched_kw_details.sort(key=lambda x: x[0], reverse=True)
        sorted_coefs = sorted(matched_coefs, reverse=True)
        positive_raw_sum = sum(sorted_coefs[:5]) # 상위 5개 긍정 단어 합
            
        # 3. 제외 키워드 매칭 및 감점 규모 계산 (최대 2개 단어 제한)
        found_penalties = []
        for pk, penalty_val in penalty_dict.items():
            if pk in title:
                found_penalties.append((pk, penalty_val))
                
        found_penalties.sort(key=lambda x: x[1], reverse=True)
        applied_penalties = found_penalties[:2]
        penalty_raw_sum = sum([item[1] for item in applied_penalties]) # 상위 최대 2개 감점 단어 합
        
        # 4. 💡 [핵심 개편] 분모로 나누기 전, 원본 점수 상태에서 감점을 먼저 수행합니다.
        if sorted_coefs or media_score > 0:
            final_raw_score = (positive_raw_sum + media_score) - penalty_raw_sum
            final_raw_score = max(0.0, final_raw_score) # 음수 방어
            
            # 감점 처리가 완료된 깨끗한 원본 점수를 기반으로 최종 100점 만점 정규화를 진행합니다.
            base_score = min(round((final_raw_score / max_denominator) * 100, 2), 100.0)
        else:
            base_score = 0.0 
            
        # 대시보드 출력용 텍스트 매칭 키워드 조립
        if penalty_raw_sum > 0:
            neg_text = ", ".join([f"{item[0]}({int(item[1])})" for item in applied_penalties])
            kw_text = ", ".join([item[1] for item in matched_kw_details]) if matched_kw_details else "-"
            matched_keywords_str = f"{kw_text} [🔻 감점: {neg_text}]"
        else:
            matched_keywords_str = ", ".join([item[1] for item in matched_kw_details]) if matched_kw_details else "-"
            
        stage_rows.append([date, title, url, matched_media, matched_keywords_str, base_score])

    if stage_rows:
        stage_rows.sort(key=lambda x: x[5], reverse=True)
        stage_sheet.append_rows(stage_rows)
        
    inbox_sheet.resize(rows=1)
    print("정규화 전 차감 방식 수식 연산 완료.")

if __name__ == "__main__":
    process_base_score()
