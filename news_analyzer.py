import os, json, gspread, time
import google.generativeai as genai
from oauth2client.service_account import ServiceAccountCredentials

creds = ServiceAccountCredentials.from_json_keyfile_dict(
    json.loads(os.environ["GOOGLE_SHEETS_CREDENTIALS"]),
    ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
)
spreadsheet = gspread.authorize(creds).open("News_Management_DB")

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-3.0-flash') 

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
        date = row_data[0]
        title = row_data[1]
        url = row_data[2]
        
        if url in archive_links:
            inbox_sheet.delete_rows(i + 1)
            continue
            
        try:
            prompt = f"다음 뉴스 기사 제목을 분석해서 100점 만점으로 점수를 매기고 점수만 숫자로 답변해줘 기사 제목 {title}"
            response = model.generate_content(prompt)
            score_text = ''.join(filter(str.isdigit, response.text))
            total_score = int(score_text) if score_text else 80
            
            archive_sheet.append_row([date, title, url, 'Naver', 0, 0, total_score, 'N'])
            archive_links.append(url)
            
            inbox_sheet.delete_rows(i + 1)
            print(f"분석 완료 및 이동 완료 기사 제목 {title} 배점 {total_score}점")
            
        except Exception as e:
            print(f"분석 과정에서 에러가 발생했습니다 에러 내용 {e}")
            
        time.sleep(2)

if __name__ == "__main__":
    process_inbox()
