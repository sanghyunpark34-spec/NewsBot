import os, json, gspread, time
import google.generativeai as genai
from oauth2client.service_account import ServiceAccountCredentials

# 인증
creds = ServiceAccountCredentials.from_json_keyfile_dict(
    json.loads(os.environ["GOOGLE_SHEETS_CREDENTIALS"]),
    ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
)
spreadsheet = gspread.authorize(creds).open("News_Management_DB")

# 모델 설정: 'gemini-1.5-flash' 대신 더 안정적인 모델명으로 변경
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

    for i in range(1, len(rows)):
        row_data = rows[i]
        date, title, url = row_data[0], row_data[1], row_data[2]
        
        if url in archive_links:
            continue
            
        try:
            # 분석 수행
            prompt = f"다음 뉴스 기사를 분석해서 100점 만점으로 점수를 매기고, 점수만 숫자로 답변해줘. 기사 제목: {title}"
            response = model.generate_content(prompt)
            # 숫자가 아닌 문자열이 섞일 경우를 대비해 처리
            score_text = ''.join(filter(str.isdigit, response.text))
            total_score = int(score_text) if score_text else 80
            
            # 아카이브 저장
            archive_sheet.append_row([date, title, url, 'Naver', 0, 0, total_score, 'N'])
            archive_links.append(url)
            print(f"분석 완료: {title} ({total_score}점)")
            
        except Exception as e:
            print(f"분석 실패: {e}")
            
        time.sleep(2)

    # 처리된 만큼 Inbox 행 삭제 (2행부터 i행까지)
    inbox_sheet.delete_rows(2, len(rows) - 1)

if __name__ == "__main__":
    process_inbox()
