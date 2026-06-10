import gspread
import json
import os
from oauth2client.service_account import ServiceAccountCredentials

# 1. 인증 설정 (이전과 동일)
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

if "GOOGLE_SHEETS_CREDENTIALS" in os.environ:
    creds_dict = json.loads(os.environ["GOOGLE_SHEETS_CREDENTIALS"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
else:
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)

client = gspread.authorize(creds)
spreadsheet = client.open("News_Management_DB")

# 2. 키워드 설정 시트 불러오기
keyword_sheet = spreadsheet.worksheet("Config_Keywords")
# get_all_records()는 첫 행을 헤더로 인식하고 데이터를 딕셔너리 리스트로 가져옵니다.
keywords_data = keyword_sheet.get_all_records()

# 3. 결과 확인
print("불러온 키워드 설정:")
for entry in keywords_data:
    print(f"키워드: {entry['Keyword']}, 계수(Coefficient): {entry['Coefficient']}")
