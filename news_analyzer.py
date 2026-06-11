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
    
    # 미디어 시트 이름 오류 방지 (Config_Media_Sites 우선, 없으면 Config_Media)
    try:
        media_sheet = spreadsheet.worksheet("Config_Media_Sites")
    except:
        media_sheet = spreadsheet.worksheet("Config_Media")
    
    archive_links = set(archive_sheet.col_values(3))
    rows = inbox_sheet.get_all_values()
    
    if len(rows) <= 1:
        print("분석할 기사가 없습니다.")
        return

    # 시트 데이터 로드
    keyword_records = keyword_sheet.get_all_records()
    media_records = media_sheet.get_all_records()
    
    # 미디어와 가중치(Coefficient)를 딕셔너리로 저장 { 'mk.co.kr': 5, ... }
    media_dict = {}
    for mr in media_records:
        domain = str(mr.get('Domain', '')).strip()
        if domain:
            try: coef = int(mr.get('Coefficient', 0))
            except: coef = 0
            media_dict[domain] = coef
            
    articles = []
    
    # 1. Base Score 계산
    for row in rows[1:]:
        if len(row) < 3: continue
        date, title, url = row[0], row[1], row[2]
        
        if url in archive_links: continue
            
        # 미디어 매칭 및 미디어 점수 추출
        matched_media = 'Naver' 
        media_score = 0
        for domain, coef in media_dict.items():
            if domain in url:
                matched_media = domain
                media_score = coef
                break
                
        # 키워드 매칭
        matched_coefs = []
        for kw_rec in keyword_records:
            kw = str(kw_rec.get('Keyword', '')).strip()
            try: coef = int(kw_rec.get('Coefficient', 1))
            except: coef = 1
            
            if kw in title:
                matched_coefs.append(coef)
        
        # [수정] Base Score 산식: (상위 3개 키워드 합산 + 미디어 점수) / 20 * 100
        if matched_coefs:
            matched_coefs.sort(reverse=True) 
            top_3_sum = sum(matched_coefs[:3]) 
            base_score = min(round(((top_3_sum + media_score) / 20) * 100, 2), 100) 
        else:
            base_score = 0 # 노이즈 기사는 0점 처리
            
        articles.append({
            'date': date, 'title': title, 'url': url, 
            'media': matched_media, 'base_score': base_score
        })
        
    if not articles:
        print("새롭게 처리할 기사가 없습니다.")
        inbox_sheet.resize(rows=1)
        return

    # 2. Base Score 기준으로 내림차순 정렬
    articles.sort(key=lambda x: x['base_score'], reverse=True)
    
    rows_to_archive = []
    print(f"총 {len(articles)}개의 기사를 Archive로 이동합니다. (상위 20개만 AI 분석)")

    # 3. 상위 20개 AI 분석, 나머지는 Base Score만 적용
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
            print(f"[AI 분석O] {art['title'][:20]}... (Base: {art['base_score']}, AI: {ai_score}, Total: {total_score})")
            time.sleep(2) 
        else: 
            ai_score = 0
            total_score = round(art['base_score'] * 0.4, 2)
            
        rows_to_archive.append([art['date'], art['title'], art['url'], art['media'], art['base_score'], ai_score, total_score, 'N'])

    # 4. Archive 저장 및 Inbox 비우기
    if rows_to_archive:
        archive_sheet.append_rows(rows_to_archive)
        
    inbox_sheet.resize(rows=1)
    print("작업이 성공적으로 완료되었습니다.")

if __name__ == "__main__":
    process_inbox()
