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
    
    # 중복 검사용 세트 구성 (탐색 속도 최적화)
    archive_links = set(archive_sheet.col_values(3))
    rows = inbox_sheet.get_all_values()
    
    if len(rows) <= 1:
        print("분석할 기사가 없습니다.")
        return

    # 1. 시트에서 키워드 및 가중치(Coefficient) 정보 로드
    keyword_records = keyword_sheet.get_all_records()
    
    articles = []
    
    # 인박스의 모든 기사에 대해 1차 Base Score 계산
    for row in rows[1:]:
        if len(row) < 3:
            continue
        date, title, url = row[0], row[1], row[2]
        
        # 이미 아카이브에 존재하는 중복 기사는 원천 제외
        if url in archive_links:
            continue
            
        # 제목과 매칭되는 키워드의 가중치 추출
        matched_coefs = []
        for kw_rec in keyword_records:
            kw = str(kw_rec.get('Keyword', '')).strip()
            coef = kw_rec.get('Coefficient', 1)
            try:
                coef = int(coef)
            except:
                coef = 1
            if kw in title:
                matched_coefs.append(coef)
        
        # 가중치 기반 점수 환산 (가장 높은 가중치 점수 5점을 100점 만점으로 계산)
        if matched_coefs:
            base_score = min(max(matched_coefs) * 20, 100)
        else:
            base_score = 40 # 매칭되는 키워드가 없는 경우 기본 점수 부여
            
        articles.append({
            'date': date,
            'title': title,
            'url': url,
            'base_score': base_score
        })
        
    if not articles:
        print("새롭게 분석할 기사가 없습니다.")
        inbox_sheet.resize(rows=1) # 중복 항목 제거를 위한 인박스 초기화
        return

    # 2. Base Score 기준으로 내림차순 정렬 (가장 유망한 기사가 상위로 이동)
    articles.sort(key=lambda x: x['base_score'], reverse=True)
    
    # 상위 20개 기사만 정밀 분석 대상으로 선별하고 나머지는 보류
    top_20 = articles[:20]
    remainder = articles[20:]
    
    print(f"전체 {len(articles)}개의 기사 중 가중치가 높은 상위 {len(top_20)}개의 기사 정밀 AI 분석을 시작합니다.")
    
    # 3. 선별된 20개 기사에 대해서만 AI Score 측정 및 가중 평균 산출
    for art in top_20:
        try:
            prompt = f"다음 뉴스 기사 제목을 분석해서 100점 만점으로 점수를 매기고 점수만 숫자로 답변해줘 기사 제목 {art['title']}"
            response = model.generate_content(prompt)
            score_text = ''.join(filter(str.isdigit, response.text))
            ai_score = int(score_text) if score_text else 80
        except Exception as e:
            print(f"AI 호출 과정에서 오류가 발생하여 기본 점수를 부여합니다 에러 내용 {e}")
            ai_score = 80
            
        # 최종 점수 산출 (Base Score 40% + AI Score 60%)
        total_score = round((art['base_score'] * 0.4) + (ai_score * 0.6), 2)
        
        # 아카이브 시트 규격에 맞춰 데이터 정밀 적재
        archive_sheet.append_row([art['date'], art['title'], art['url'], 'Naver', art['base_score'], ai_score, total_score, 'N'])
        print(f"아카이브 이동 완료 기사 제목 {art['title']} (Base {art['base_score']}점 / AI {ai_score}점 / 최종 {total_score}점)")
        
        time.sleep(2) # 안정적인 호출을 위한 숨 고르기
        
    # 4. 시트 부하 최소화를 위한 일괄 비우기 및 잔여 데이터 재기록
    inbox_sheet.resize(rows=1) # 헤더 행만 남기고 전체 삭제
    if remainder:
        remainder_rows = [[r['date'], r['title'], r['url']] for r in remainder]
        inbox_sheet.append_rows(remainder_rows)
        print(f"분석 한도를 초과하여 처리되지 않은 {len(remainder)}개의 기사는 다음 주기에 처리하기 위해 인박스 시트에 보존합니다.")

if __name__ == "__main__":
    process_inbox()
