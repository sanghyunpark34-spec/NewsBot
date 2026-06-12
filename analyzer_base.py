import os, json, gspread
from oauth2client.service_account import ServiceAccountCredentials

creds = ServiceAccountCredentials.from_json_keyfile_dict(
    json.loads(os.environ["GOOGLE_SHEETS_CREDENTIALS"]),
    ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
)
spreadsheet = gspread.authorize(creds).open("News_Management_DB")

# 단어당 차감할 점수를 정의합니다. (최대 2개 적용)
PENALTY_PER_KEYWORD = 20.0 

def process_base_score():
    inbox_sheet = spreadsheet.worksheet("DB_Inbox")
    stage_sheet = spreadsheet.worksheet("DB_Stage")
    keyword_sheet = spreadsheet.worksheet("Config_Keywords")
    
    try: media_sheet = spreadsheet.worksheet("Config_Media")
    except: media_sheet = spreadsheet.worksheet("Config_Media_Sites")
        
    # 수집기에서 5개 단어를 원천 차단하므로, 여기서는 오직 대시보드(시트)에 등록된 단어만 불러와 감점용으로 씁니다.
    try:
        neg_sheet = spreadsheet.worksheet("Config_Negative")
        penalty_keywords = [str(r.get('Keyword', '')).strip() for r in neg_sheet.get_all_records() if str(r.get('Keyword', '')).strip()]
    except:
        penalty_keywords = []
        
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
            
        # 대시보드 등록 단어로 차감 연산 진행 (최대 2개 단어로 제한)
        found_penalties = []
        for pk in penalty_keywords:
            if pk in title:
                found_penalties.append(pk)
                
        applied_penalties = found_penalties[:2]
        total_penalty = len(applied_penalties) * PENALTY_PER_KEYWORD
        
        if total_penalty > 0:
            base_score = max(0.0, round(base_score - total_penalty, 2))
            neg_text = ", ".join(applied_penalties)
            kw_text = ", ".join([item[1] for item in matched_kw_details]) if matched_kw_details else "-"
            matched_keywords_str = f"{kw_text} [🔻 감점: {neg_text}]"
        else:
            matched_keywords_str = ", ".join([item[1] for item in matched_kw_details]) if matched_kw_details else "-"
            
        stage_rows.append([date, title, url, matched_media, matched_keywords_str, base_score])

    if stage_rows:
        stage_rows.sort(key=lambda x: x[5], reverse=True)
        stage_sheet.append_rows(stage_rows)
        
    inbox_sheet.resize(rows=1)
    print("기초 점수 산정 및 대시보드 설정 감점 연산 완료.")

if __name__ == "__main__":
    process_base_score()
