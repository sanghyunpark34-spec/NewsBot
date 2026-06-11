import os, json, gspread, time
import google.generativeai as genai
from oauth2client.service_account import ServiceAccountCredentials

creds = ServiceAccountCredentials.from_json_keyfile_dict(
    json.loads(os.environ["GOOGLE_SHEETS_CREDENTIALS"]),
    ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
)
spreadsheet = gspread.authorize(creds).open("News_Management_DB")

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-3.5-flash') 

def process_inbox():
    inbox_sheet = spreadsheet.worksheet("DB_Inbox")
    archive_sheet = spreadsheet.worksheet("DB_Archive")
    keyword_sheet = spreadsheet.worksheet("Config_Keywords")
    
    try:
        media_sheet = spreadsheet.worksheet("Config_Media_Sites")
    except:
        media_sheet = spreadsheet.worksheet("Config_Media")
    
    archive_links = set(archive_sheet.col_values(3))
    rows = inbox_sheet.get_all_values()
    
    if len(rows) <= 1:
        print("분석할 기사가 없습니다.")
        return

    keyword_records = keyword_sheet.get_all_records()
    media_records = media_sheet.get_all_records()
    
    media_dict = {}
    for mr in media_records:
        domain = str(mr.get('Domain', '')).strip()
        if domain:
            try: coef = int(mr.get('Coefficient', 0))
            except: coef = 0
            media_dict[domain] = coef
            
    articles = []
    
    for row in rows[1:]:
        if len(row) < 3: continue
        date, title, url = row[0], row[1], row[2]
        
        if url in archive_links: continue
            
        matched_media = 'Naver' 
        media_score = 0
        for domain, coef in media_dict.items():
            if domain in url:
                matched_media = domain
                media_score = coef
                break
                
        matched_coefs = []
        for kw_rec in keyword_records:
            kw = str(kw_rec.get('Keyword', '')).strip()
            try: coef = int(kw_rec.get('Coefficient', 1))
            except: coef = 1
            
            if kw in title:
                matched_coefs.append(coef)
        
        # [변경 반영] Base Score = Sum(상위 3개 키워드 가중치 + 미디어점수) / 20 * 100
        if matched_coefs or media_score > 0:
            matched_coefs.sort(reverse=True) 
            top_3_sum = sum(matched_coefs[:3]) 
            base_score = min(round(((top_3_sum + media_score) / 20) * 100, 2), 100) 
        else:
            base_score = 0 
            
        articles.append({
            'date': date, 'title': title, 'url': url, 
            'media': matched_media, 'base_score': base_score
        })
        
    if not articles:
        print("새롭게 처리할 기사가 없습니다.")
        inbox_sheet.resize(rows=1)
        return

    articles.sort(key=lambda x: x['base_score'], reverse=True)
    rows_to_archive = []

    for i, art in enumerate(articles):
        if i < 20 and art['base_score'] > 0: 
            try:
                prompt = f"다음 뉴스 기사 제목을 분석해서 100점 만점으로 점수를 매기고 점수만 숫자로 답변해줘 기사 제목 {art['title']}"
                response = model.generate_content(prompt)
                score_text = ''.join(filter(str.isdigit, response.text))
                ai_score = int(score_text) if score_text else 80
            except Exception as e:
                ai_score = 0 
            
            total_score = round((art['base_score'] * 0.4) + (ai_score * 0.6), 2)
            time.sleep(2) 
        else: 
            ai_score = 0
            total_score = round(art['base_score'] * 0.4, 2)
            
        rows_to_archive.append([art['date'], art['title'], art['url'], art['media'], art['base_score'], ai_score, total_score, 'N'])

    if rows_to_archive:
        archive_sheet.append_rows(rows_to_archive)
        
    inbox_sheet.resize(rows=1)
    print("성공적으로 새 알고리즘이 적용 및 이관되었습니다.")

if __name__ == "__main__":
    process_inbox()
