import gspread
import json
import os
from oauth2client.service_account import ServiceAccountCredentials

# 1. 인증 정보 로드
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# 환경 변수(깃허브 시크릿)에 GOOGLE_SHEETS_CREDENTIALS가 있다면 그것을 사용
if "GOOGLE_SHEETS_CREDENTIALS" in os.environ:
    creds_dict = json.loads(os.environ["GOOGLE_SHEETS_CREDENTIALS"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
else:
    # 로컬 테스트용: 파일이 존재할 경우
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)

client = gspread.authorize(creds)

# 2. 시트 열기
sheet = client.open("News_Management_DB").sheet1

# 3. 테스트: 헤더 추가
header = ["Date", "Title", "Link", "Media", "Base_Score", "AI_Score", "Total_Score", "Sent"]
sheet.insert_row(header, 1)

print("시트 연결 및 헤더 생성 성공!")
