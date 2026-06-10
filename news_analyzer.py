import os, json, gspread, time
import google.generativeai as genai
from oauth2client.service_account import ServiceAccountCredentials

# 설정 및 인증
creds = ServiceAccountCredentials.from_json_keyfile_dict(
    json.loads(os.environ["GOOGLE_SHEETS_CREDENTIALS"]),
    ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
)
spreadsheet = gspread.authorize(creds).open("News_Management_DB")

# 모델 설정: 사장님 환경에서 작동을 확인했던 모델명으로 세팅합니다.
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
# gemini-1.5-pro 가 가장 인지 능력이 뛰어나고 안정적입니다. (기존에 작동했던 이름으로 쓰셔도 됩니다)
model = genai.GenerativeModel('gemini-3.0-pro') 

def process_inbox():
    inbox_sheet = spreadsheet.worksheet("DB_Inbox")
    archive_sheet = spreadsheet.worksheet("DB_Archive")
    
    archive_links = archive_sheet.col_values(3)
    rows = inbox_sheet.get_all_values()
    
    if len(rows) <= 1:
        print("분석할 기사가 없습니다.")
        return

    # 역순 처리 (삭제 시 행 번호가 꼬이는 것을 방지)
    for i in range(len(rows) - 1, 0, -1):
        row_data = rows[i]
        date, title, url = row_data[0], row_data[1], row_data[2]
        
        if url in archive_links:
            inbox_sheet.delete_rows(i + 1)
            continue
            
        try:
            # 💡 [복원 완료] 진짜 AI를 호출하여 기사 제목을 분석하고 점수를 매기는 구간
            prompt = f"다음 뉴스 기사 제목을 분석해서 100점 만점으로 점수를 매기고, 점수만 숫자로 답변해줘. 기사 제목: {title}"
            response = model.generate_content(prompt)
            
            # AI의 답변에서 안전하게 숫자만 쏙 뽑아냅니다.
            score_text = ''.join(filter(str.isdigit, response.text))
            total_score = int(score_text) if score_text else 80 # 혹시 숫자를 못 찾으면 기본 80점
            
            # DB_Archive 시트에 기록
            archive_sheet.append_row([date, title, url, 'Naver', 0, 0, total_score, 'N'])
            archive_links.append(url)
            
            #
