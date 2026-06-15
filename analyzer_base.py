import os, json, gspread, difflib
from oauth2client.service_account import ServiceAccountCredentials

creds = ServiceAccountCredentials.from_json_keyfile_dict(
    json.loads(os.environ["GOOGLE_SHEETS_CREDENTIALS"]),
    ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
)
spreadsheet = gspread.authorize(creds).open("News_Management_DB")

# 💡 [핵심 추가] 두 기사 제목의 유사도를 판별하는 함수 (65% 이상이면 중복으로 간주)
def is_similar(title1, title2, threshold=0.65):
    ratio = difflib.SequenceMatcher(None, title1.replace(" ", ""), title2.replace(" ", "")).ratio()
    return ratio >= threshold

def process_base_score():
    inbox_sheet = spreadsheet.worksheet("DB_Inbox")
    stage_sheet = spreadsheet.worksheet("DB_Stage")
    keyword_sheet = spreadsheet.worksheet("Config_Keywords")
    
    try: media_sheet = spreadsheet.worksheet("Config_Media")
    except: media_sheet = spreadsheet.worksheet("Config_Media_Sites")
        
    try:
        neg_sheet = spreadsheet.worksheet("Config_Negative")
        neg_records = neg_sheet.get_all_records()
        penalty_dict = {}
        for r in neg_records:
            kw = str(r.get('Keyword', '')).strip()
            if not kw: continue
            try: val = float(r.get('Coefficient', r.get('Weight', 2.0)))
            except: val = 2.0
            penalty_dict[kw] = val
    except:
        penalty_dict = {}
        
    rows = inbox_sheet.get_all_values()
    if len(rows) <= 1: return

    keyword_records = keyword_sheet.get_all_records()
    media_records = media_sheet.get_all_records()
    
    kw_weights = []
    for kw_rec in keyword_records:
        try: w = float(kw_rec.get('Weight', kw_rec.get('Coefficient', 1.0)))
        except: w = 1.0
        kw_weights.append(w)
    kw_weights.sort(reverse=True)
    max_4_kw_sum = sum(kw_weights[:4]) if kw_weights else 40.0

    media_weights = []
    for mr in media_records:
        try: w = float(mr.get('Weight', mr.get('Coefficient', 0.0)))
        except: w = 0.0
        media_weights.append(w)
    max_media_weight = max(media_weights) if media_weights else 5.0

    max_denominator = max_4_kw_sum + max_media_weight
    if max_denominator == 0: max_denominator = 45.0

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
            try: coef = float(kw_rec.get('Weight', kw_rec.get('Coefficient', 1.0)))
            except: coef = 1.0
            if kw in title: 
                matched_coefs.append(coef)
                matched_kw_details.append((coef, f"{kw}({int(coef)})"))
        
        matched_kw_details.sort(key=lambda x: x[0], reverse=True)
        sorted_coefs = sorted(matched_coefs, reverse=True)
        positive_raw_sum = sum(sorted_coefs[:4]) 
            
        found_penalties = []
        for pk, penalty_val in penalty_dict.items():
            if pk in title:
                found_penalties.append((pk, penalty_val))
                
        found_penalties.sort(key=lambda x: x[1], reverse=True)
        applied_penalties = found_penalties[:2]
        penalty_raw_sum = sum([item[1] for item in applied_penalties]) 
        
        if sorted_coefs:
            final_raw_score = (positive_raw_sum + media_score) - penalty_raw_sum
            final_raw_score = max(0.0, final_raw_score) 
            base_score = min(round((final_raw_score / max_denominator) * 100, 2), 100.0)
        else:
            base_score = 0.0 
            
        if penalty_raw_sum > 0:
            neg_text = ", ".join([f"{item[0]}({int(item[1])})" for item in applied_penalties])
            kw_text = ", ".join([item[1] for item in matched_kw_details]) if matched_kw_details else "-"
            matched_keywords_str = f"{kw_text} [🔻 감점: {neg_text}]"
        else:
            matched_keywords_str = ", ".join([item[1] for item in matched_kw_details]) if matched_kw_details else "-"
            
        stage_rows.append([date, title, url, matched_media, matched_keywords_str, base_score])

    if stage_rows:
        # 💡 1. 기초 점수 기준으로 최상위 기사부터 정렬
        stage_rows.sort(key=lambda x: x[5], reverse=True)
        
        # 💡 2. 중복 기사 필터링 (De-duplication)
        final_survivors = []
        accepted_titles = []
        
        for row in stage_rows:
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
                print(f"🚫 중복 기사 탈락: {current_title[:20]}...")
                
        # 💡 3. 생존한 엑기스 기사들만 DB에 저장
        stage_sheet.append_rows(final_survivors)
        
    inbox_sheet.resize(rows=1)
    print("4+1 가중치 정규화 및 중복 기사 제거 연산 완료.")

if __name__ == "__main__":
    process_base_score()
