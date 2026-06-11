import os, json, gspread, time
import google.generativeai as genai
from oauth2client.service_account import ServiceAccountCredentials

# 설정 및 인증
creds = ServiceAccountCredentials.from_json_keyfile_dict(
    json.loads(os.environ["GOOGLE_SHEETS_CREDENTIALS"]),
    ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
)
spreadsheet = gspread.authorize(creds).open("News_Management_DB")

# 최신 에이피아이 규격에 맞춘 모델 설정
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-3.5-flash') 

def process_inbox():
    inbox_sheet = spreadsheet.worksheet("DB_Inbox")
    archive_sheet = spreadsheet.worksheet("DB_Archive")
    keyword_sheet = spreadsheet.worksheet("Config_Keywords")
    media_sheet = spreadsheet.worksheet("Config_Media")
    
    # 중복 검사용 세트 구성 (탐색 속도 최적화)
    archive_links = set(archive_sheet.col_values(3))
    rows = inbox_sheet.get_all_values()
    
    if len(rows) <= 1:
        print("분석할 기사가 없습니다.")
        return

    # 시트 데이터 로드
    keyword_records = keyword_sheet.get_all_records()
    media_list = [str(r['Domain']).strip() for r in media_sheet.get_all_records() if r.get('Domain')]
    
    articles = []
    
    # 1. 모든 기사에 대해 Base Score 계산 및 실제 미디어 식별
    for row in rows[1:]:
        if len(row) < 3: continue
        date, title, url = row[0], row[1], row[2]
        
        if url in archive_links:
            continue
            
        # 원본 링크나 뉴스 링크에서 실제 매체 도메인 매칭 추출
        matched_media = 'Naver' 
        for media in media_list:
            if media in url:
                matched_media = media
                break
                
        # 제목과 매칭되는 키워드의 가중치 추출
        matched_coefs = []
        for kw_rec in keyword_records:
            kw = str(kw_rec.get('Keyword', '')).strip()
            coef = kw_rec.get('Coefficient', 1)
            try: coef = int(coef)
            except: coef = 1
            
            if kw in title:
                matched_coefs.append(coef)
        
        # [수정] 새로운 Base Score 채점 방식: 상위 3개 합산 / 15 * 100
        if matched_coefs:
            matched_coefs.sort(reverse=True) # 내림차순 정렬 (높은 점수가 앞으로)
            top_3_sum = sum(matched_coefs[:3]) # 상위 3개 합산
            base_score = min(round((top_3_sum / 15) * 100, 2), 100) # 최대 100점 제한
        else:
            base_score = 0 # 매칭되는 키워드가 전혀 없으면 0점
            
        articles.append({
            'date': date, 
            'title': title, 
            'url': url, 
            'media': matched_media,
            'base_score': base_score
        })
        
    if not articles:
        print("새롭게 처리할 기사가 없습니다.")
        inbox_sheet.resize(rows=1)
        return

    # 2. Base Score 기준으로 내림차순 정렬
    articles.sort(key=lambda x: x['base_score'], reverse=True)
    
    rows_to_archive = []
    print(f"총 {len(articles)}개의 기사를 Archive로 이동합니다. (상위 20개만 AI 정밀 분석)")

    # 3. 상위 20개 AI 분석 (단, Base Score가 0점인 노이즈 기사는 AI 호출 제외), 나머지는 Base Score만 적용
    for i, art in enumerate(articles):
        if i < 20 and art['base_score'] > 0: 
            try:
                prompt = f"다음 뉴스 기사 제목을 분석해서 100점 만점으로 점수를 매기고 점수만 숫자로 답변해줘 기사 제목 {art['title']}"
                response = model.generate_content(prompt)
                score_text = ''.join(filter(str.isdigit, response.text))
                ai_score = int(score_text) if score_text else 80
            except Exception as e:
                print(f"AI 할당량 초과 또는 에러로 기본 점수 부여: {e}")
                ai_score = 0 
            
            total_score = round((art['base_score'] * 0.4) + (ai_score * 0.6), 2)
            print(f"[AI 분석O] {art['title'][:20]}... (Base: {art['base_score']}, AI: {ai_score}, Total: {total_score})")
            time.sleep(2) 
        else: 
            ai_score = 0
            total_score = round(art['base_score'] * 0.4, 2)
            
        rows_to_archive.append([art['date'], art['title'], art['url'], art['media'], art['base_score'], ai_score, total_score, 'N'])

    # 4. Archive 시트에 일괄 저장 및 Inbox 초기화
    if rows_to_archive:
        archive_sheet.append_rows(rows_to_archive)
        
    inbox_sheet.resize(rows=1)
    print("모든 기사의 분류 및 아카이브 이관이 성공적으로 완료되었습니다.")

if __name__ == "__main__":
    process_inbox()
