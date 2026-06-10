import os, json, gspread, time
import google.generativeai as genai
from oauth2client.service_account import ServiceAccountCredentials

# 설정 및 인증
creds = ServiceAccountCredentials.from_json_keyfile_dict(
    json.loads(os.environ["GOOGLE_SHEETS_CREDENTIALS"]),
    ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
)
spreadsheet = gspread.authorize(creds).open("News_Management_DB")
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-1.5-flash')

def process_inbox():
    inbox_sheet = spreadsheet.worksheet("DB_Inbox")
    archive_sheet = spreadsheet.worksheet("DB_Archive")
    
    # 1. 아카이브 캐싱
    archive_links = archive_sheet.col_values(3)
    rows = inbox_sheet.get_all_records()
    
    if not rows:
        print("분석할 기사가 없습니다.")
        return

    for row in rows:
        url = row['Link']
        if url in archive_links:
            print(f"이미 아카이브에 존재함, 삭제: {url}")
            inbox_sheet.delete_rows(2)
            continue
            
        # 3. 분석 수행 (Gemini 활용)
        try:
            # 사장님의 기존 분석 프롬프트 및 점수 산정 로직이 여기 들어갑니다
            prompt = f"다음 기사를 분석하여 100점 만점으로 점수를 매겨줘. 기사 제목: {row['Title']}"
            response = model.generate_content(prompt)
            total_score = 80 # 예시 점수 (여기에 실제 로직 결과값 대입)
            
            # 4. 아카이브 기록 (Date, Title, Link, Media, Base_Score, AI_Score, Total_Score, Sent)
            archive_sheet.append_row([
                row['Date'], row['Title'], url, 'NaverNews', 0, 0, total_score, 'N'
            ])
            
            # 5. Inbox 삭제
            inbox_sheet.delete_rows(2)
            archive_links.append(url)
            print(f"분석 완료: {row['Title']} (점수: {total_score})")
            
        except Exception as e:
            print(f"분석 실패: {e}")
            
        time.sleep(2)

if __name__ == "__main__":
    process_inbox()
