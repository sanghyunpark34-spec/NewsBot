import os, json, gspread, time
import google.generativeai as genai
from oauth2client.service_account import ServiceAccountCredentials

# 인증 (기존과 동일)
creds = ServiceAccountCredentials.from_json_keyfile_dict(
    json.loads(os.environ["GOOGLE_SHEETS_HEAD"]), # 만약 이전과 다르다면 환경변수명 확인!
    ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
)
spreadsheet = gspread.authorize(creds).open("News_Management_DB")

# 모델 설정 (혹시 나중에 AI를 다시 쓸 때를 위해 유지)
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-1.5-flash') 

def process_inbox():
    inbox_sheet = spreadsheet.worksheet("DB_Inbox")
    archive_sheet = spreadsheet.worksheet("DB_Archive")
    
    archive_links = archive_sheet.col_values(3)
    rows = inbox_sheet.get_all_values()
    
    if len(rows) <= 1:
        print("분석할 기사가 없습니다.")
        return

    for i in range(len(rows) - 1, 0, -1):
        row_data = rows[i]
        date, title, url = row_data[0], row_data[1], row_data[2]
        
        if url in archive_links:
            inbox_sheet.delete_rows(i + 1)
            continue
            
        try:
            # [테스트 구간] AI 분석 대신 강제로 점수 부여
            print(f"테스트 분석 중: {title}")
            total_score = 80 
            
            # 아카이브 저장 (성공하는지 확인)
            archive_sheet.append_row([date, title, url, 'Naver', 0, 0, total_score, 'N'])
            archive_links.append(url)
            
            # 성공 시에만 Inbox에서 해당 행 삭제
            inbox_sheet.delete_rows(i + 1)
            print(f"이동 완료: {title}")
            
        except Exception as e:
            print(f"실패: {e}")
            
        time.sleep(1)

if __name__ == "__main__":
    process_inbox()
