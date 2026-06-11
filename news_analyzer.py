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
    
    archive_links = set(archive_sheet.col_values(3))
    rows = inbox_sheet.get_all_values()
    
    if len(rows) <= 1:
        print("분석할 기사가 없습니다.")
        return

    keyword_records = keyword_sheet.get_all_records()
    articles = []
    
    # 1. 모든 기사에 대해 Base Score 계산 (중복 제외)
    for row in rows[1:]:
        if len(row) < 3: continue
        date, title, url = row[0], row[1], row[2]
        
        if url in archive_links:
            continue
            
        matched_coefs = []
        for kw_rec in keyword_records:
            kw = str(kw_rec.get('Keyword', '')).strip()
            coef = kw_rec.get('Coefficient', 1)
            try: coef = int(coef)
            except: coef = 1
            
            if kw in title:
                matched_coefs.append(coef)
        
        if matched_coefs:
            base_score = min(max(matched_coefs) * 20, 100)
        else:
            base_score = 40
            
        articles.append({'date': date, 'title': title, 'url': url, 'base_score': base_score})
        
    if not articles:
        print("새롭게 처리할 기사가 없습니다.")
        inbox_sheet.resize(rows=1)
        return

    # 2. Base Score 기준으로 정렬
    articles.sort(key=lambda x: x['base_score'], reverse=True)
    
    rows_to_archive = []
    
    print(f"총 {len(articles)}개의 기사를 Archive로 이동합니다. (상위 20개만 AI 정밀 분석)")

    # 3. 상위 20개 AI 분석, 나머지는 Base Score만 적용
    for i, art in enumerate(articles):
        if i < 20: # 상위 20개
            try:
                prompt = f"다음 뉴스 기사 제목을 분석해서 100점 만점으로 점수를 매기고 점수만 숫자로 답변해줘 기사 제목 {art['title']}"
                response = model.generate_content(prompt)
                score_text = ''.join(filter(str.isdigit, response.text))
                ai_score = int(score_text) if score_text else 80
            except Exception as e:
                print(f"AI 할당량 초과 또는 에러: {e}")
                ai_score = 0 # 에러 발생 시 AI 점수는 0점으로 처리
            
            total_score = round((art['base_score'] * 0.4) + (ai_score * 0.6), 2)
            print(f"[AI 분석O] {art['title'][:20]}... (Base: {art['base_score']}, AI: {ai_score}, Total: {total_score})")
            time.sleep(2) # Quota 초과 방지
        else: # 21등부터는 AI 호출 생략
            ai_score = 0
            total_score = round(art['base_score'] * 0.4, 2)
            
        # 모든 기사를 Archive 저장 리스트에 추가
        rows_to_archive.append([art['date'], art['title'], art['url'], 'Naver', art['base_score'], ai_score, total_score, 'N'])

    # 4. Archive 시트에 한 번에 밀어넣기
    if rows_to_archive:
        archive_sheet.append_rows(rows_to_archive)
        
    # 5. 처리가 끝난 Inbox는 비우기
    inbox_sheet.resize(rows=1)
    print("작업이 성공적으로 완료되었습니다.")

if __name__ == "__main__":
    process_inbox()
