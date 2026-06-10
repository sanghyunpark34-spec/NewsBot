import gspread, json, os, time
from oauth2client.service_account import ServiceAccountCredentials
from google.api_core import exceptions
import google.generativeai as genai

# 인증 및 연결
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
    
    # 1. [핵심 수정] 루프 시작 전 아카이브 링크를 메모리에 캐싱
    archive_links = archive_sheet.col_values(3) # C열(Link)
    
    rows = inbox_sheet.get_all_records()
    if not rows:
        print("분석할 기사가 없습니다.")
        return

    for row in rows:
        url = row['Link']
        
        # 2. [수정] 메모리상의 리스트와 비교 (API 호출 방지)
        if url in archive_links:
            print(f"이미 아카이브에 존재함, Inbox에서 삭제: {url}")
            inbox_sheet.delete_rows(2)
            continue
            
        # 3. 분석 수행 (기존 AI 분석 로직)
        # ... (분석 및 점수 산출 로직) ...
        
        # 4. 저장 및 Inbox 삭제
        # archive_sheet.append_row([...])
        inbox_sheet.delete_rows(2)
        
        # 5. [수정] 메모리 리스트에도 추가하여 실시간 중복 방지
        archive_links.append(url)
        
        print(f"분석 완료: {url}")
        time.sleep(2) # API 쿼터 보호

if __name__ == "__main__":
    process_inbox()
