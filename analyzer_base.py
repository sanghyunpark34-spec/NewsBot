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
        
    # 대시보드 구조 변경에 맞춰 Keyword와 Coefficient를 매핑하는 딕셔너리를 빌드합니다.
    try:
        neg_sheet = spreadsheet.worksheet("Config_Negative")
        neg_records = neg_sheet.get_all_records()
        penalty_dict = {}
        for r in neg_records:
            kw = str(r.get('Keyword', '')).strip()
            if not kw: continue
            try: val = float(r.get('Coefficient', r.get('Weight', 20.0)))
            except: val = 20.0
            penalty_dict[kw] = val
    except:
        penalty_dict = {}
        
    rows = inbox_sheet.get_all_values()
    if len(rows) <= 1: return

    keyword_records = keyword_sheet.get_all_records()
    media_records = media_sheet.get_all_records()
    
    kw_weights = []
    for kw_rec in keyword_records:
        try: w = float(kw_rec.get('Weight', kw_rec.get('Coefficient', 1)))
        except: w = 1.0
        kw_weights.append(w)
    kw_weights.sort(reverse=True)
    max_5_kw_sum = sum(kw_weights[:5]) if kw_weights else 5.0

    media_weights = []
    for mr in media_records:
        try: w = float(mr.get('Weight', mr.get('Coefficient', 0)))
        except: w = 0.0
        media_weights.append(w)
    max_media_weight = max(media_weights) if media_weights else 5.0

    max_denominator = max_5_kw_sum + max_media_weight
    media_dict = {str(mr.get('Domain', '')).strip().lower(): float(mr.get('Weight', mr.get('Coefficient', 0))) for mr in media_records if str(mr.get('Domain', '')).strip()}

    stage_rows = []
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
                
        matched_coefs = []
        matched_kw_details = []
        for kw_rec in keyword_records:
            kw = str(kw_rec.get('Keyword', '')).strip()
            if not kw: continue
            try: coef = float(kw_rec.get('Weight', kw_rec.get('Coefficient', 1)))
            except: coef = 1.0
            if kw in title: 
                matched_coefs.append(coef)
                matched_kw_details.append((coef, f"{kw}({int(coef)})"))
        
        matched_kw_details.sort(key=lambda x: x[0], reverse=True)
        sorted_coefs = sorted(matched_coefs, reverse=True)
        
        if sorted_coefs or media_score > 0:
            base_score = min(round((sum(sorted_coefs[:5]) + media_score) / max_denominator * 100, 2), 100.0) 
        else:
            base_score = 0.0 
            
        # 기사 제목에 들어있는 제외 키워드와 개별 감점 수치를 매칭합니다.
        found_penalties = []
        for pk, penalty_val in penalty_dict.items():
            if pk in title:
                found_penalties.append((pk, penalty_val))
                
        # 감점 수치가 큰 단어 순서대로 정렬하여 상위 최대 2개만 선별합니다.
        found_penalties.sort(key=lambda x: x[1], reverse=True)
        applied_penalties = found_penalties[:2]
        total_penalty = sum([item[1] for item in applied_penalties])
        
        if total_penalty > 0:
            base_score = max(0.0, round(base_score - total_penalty, 2))
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
    print("개별 계수 기반 기초 점수 산정 및 감점 수식 연산 완료.")

if __name__ == "__main__":
    process_base_score()
