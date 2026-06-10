import gspread, json, os, time
import google.generativeai as genai
from oauth2client.service_account import ServiceAccountCredentials
from google.api_core import exceptions

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
    
    rows = inbox_sheet.get_all_records()
    for row in rows:
        url = row['Link']
        # 분석 로직 수행 (생략된 세부 분석 코드를 여기 통합하시면 됩니다)
        # 결과 저장 후
        # archive_sheet.append_row([..., row['Title'], url, ..., total_score])
        inbox_sheet.delete_rows(2) # 분석 완료 시 행 삭제
        time.sleep(2) # 쿼터 방어용 대기

if __name__ == "__main__":
    process_inbox()
