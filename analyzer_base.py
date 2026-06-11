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
    
    try:
        media_sheet = spreadsheet.worksheet("Config_Media_Sites")
    except:
        media_sheet = spreadsheet.worksheet("Config_Media")
        
    rows = inbox_sheet.get_all_values()
    if len(rows) <= 1:
        print("기초 분석을 진행할 기사가 없습니다.")
        return

    keyword_records = keyword_sheet.get_all_records()
    media_records = media_sheet.get_all_records()
    
    media_dict = {}
    for mr in media_records:
        domain = str(mr.get('Domain', mr.get('도메인', ''))).strip().lower()
        if not domain:
            continue
        try:
            coef = int(mr.get('Coefficient', mr.get('가중치', 0)))
        except:
            coef = 0
        media_dict[domain] = coef

    stage_rows = []
    
    for row in rows[1:]:
        if len(row) < 3:
            continue
        date, title, url = row[0], row[1], row[2]
        
        matched_media = 'Naver' 
        media_score = 0
        for domain, coef in media_dict.items():
            if domain in url.lower():
                matched_media = domain
                media_score = coef
                break
                
        matched_coefs = []
        for kw_rec in keyword_records:
            kw = str(kw_rec.get('Keyword', '')).strip()
            if not kw:
                continue
            try:
                coef = int(kw_rec.get('Coefficient', 1))
            except:
                coef = 1
            if kw in title:
                matched_coefs.append(coef)
        
        if matched_coefs or media_score > 0:
            matched_coefs.sort(reverse=True) 
            top_3_sum = sum(matched_coefs[:3]) 
            base_score = min(round(((top_3_sum + media_score) / 20) * 100, 2), 100) 
        else:
            base_score = 0 
            
        stage_rows.append([date, title, url, matched_media, base_score])

    if stage_rows:
        stage_rows.sort(key=lambda x: x[4], reverse=True)
        stage_sheet.append_rows(stage_rows)
        
    inbox_sheet.resize(rows=1)
    print("기초 점수 산정 및 스테이지 이동이 완료되었습니다.")

if __name__ == "__main__":
    process_base_score()
