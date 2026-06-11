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
    
    try: media_sheet = spreadsheet.worksheet("Config_Media_Sites")
    except: media_sheet = spreadsheet.worksheet("Config_Media")
        
    rows = inbox_sheet.get_all_values()
    if len(rows) <= 1:
        print("기초 분석을 진행할 기사가 없습니다.")
        return

    keyword_records = keyword_sheet.get_all_records()
    media_records = media_sheet.get_all_records()
    
    # 1. 스케일 정규화를 위한 분모 최댓값 계산
    kw_weights = []
    for kw_rec in keyword_records:
        try: w = float(kw_rec.get('Weight', kw_rec.get('Coefficient', kw_rec.get('가중치', 1))))
        except: w = 1.0
        kw_weights.append(w)
    kw_weights.sort(reverse=True)
    max_3_kw_sum = sum(kw_weights[:3]) if kw_weights else 3.0

    media_weights = []
    for mr in media_records:
        try: w = float(mr.get('Weight', mr.get('Coefficient', mr.get('가중치', 0))))
        except: w = 0.0
        media_weights.append(w)
    max_media_weight = max(media_weights) if media_weights else 5.0
    if max_media_weight == 0: max_media_weight = 5.0

    max_denominator = max_3_kw_sum + max_media_weight

    # 2. 매체 도메인 매핑 사전 구축
    media_dict = {}
    for mr in media_records:
        domain = str(mr.get('Domain', mr.get('도메인', ''))).strip().lower()
        if not domain: continue
        try: coef = float(mr.get('Weight', mr.get('Coefficient', mr.get('가중치', 0))))
        except: coef = 0.0
        media_dict[domain] = coef

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
        for kw_rec in keyword_records:
            kw = str(kw_rec.get('Keyword', '')).strip()
            if not kw: continue
            try: coef = float(kw_rec.get('Weight', kw_rec.get('Coefficient', kw_rec.get('가중치', 1))))
            except: coef = 1.0
            if kw in title:
                matched_coefs.append(coef)
        
        if matched_coefs or media_score > 0:
            matched_coefs.sort(reverse=True) 
            top_3_sum = sum(matched_coefs[:3]) 
            # 최댓값 기준 산식 적용 후 100점 만점 스케일 변환
            base_score = min(round((top_3_sum + media_score) / max_denominator * 100, 2), 100.0) 
        else:
            base_score = 0.0 
            
        stage_rows.append([date, title, url, matched_media, base_score])

    if stage_rows:
        stage_rows.sort(key=lambda x: x[4], reverse=True)
        stage_sheet.append_rows(stage_rows)
        
    inbox_sheet.resize(rows=1)
    print("기초 점수 정규화 및 스테이지 이동 완료.")

if __name__ == "__main__":
    process_base_score()
