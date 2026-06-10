import gspread
from oauth2client.service_account import ServiceAccountCredentials

# 1. 시트 연결 설정
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
# 'credentials.json'은 다운로드하신 파일명을 그대로 사용하세요
creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
client = gspread.authorize(creds)

# 2. 시트 열기 (이름 확인)
sheet = client.open("News_Management_DB").sheet1

# 3. 테스트: 시트 구조 만들기 (첫 번째 행에 헤더 추가)
header = ["Date", "Title", "Link", "Media", "Base_Score", "AI_Score", "Total_Score", "Sent"]
sheet.insert_row(header, 1)

print("시트 연결 및 헤더 생성 성공!")
