import os, json, gspread, time
import google.generativeai as genai
from oauth2client.service_account import ServiceAccountCredentials

creds = ServiceAccountCredentials.from_json_keyfile_dict(
    json.loads(os.environ["GOOGLE_SHEETS_CREDENTIALS"]),
    ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
)
spreadsheet = gspread.authorize(creds).open("News_Management_DB")

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-3.5-flash') 

def process_ai_score():
    stage_sheet = spreadsheet.worksheet("DB_Stage")
    archive_sheet = spreadsheet.worksheet("DB_Archive")
    
    rows = stage_sheet.get_all_values()
    if len(rows) <= 1:
        print("인공지능 분석을 진행할 대기 기사가 없습니다.")
        return

    archive_rows = []
    
    for i, row in enumerate(rows[1:]):
        if len(row) < 5:
            continue
        date, title, url, matched_media = row[0], row[1], row[2], row[3]
        try:
            base_score = float(row[4])
        except:
            base_score = 0
            
        if i < 20 and base_score > 0: 
            try:
                prompt = f"다음 뉴스 기사 제목을 분석해서 100점 만점으로 점수를 매기고 점수만 숫자로 답변해줘 기사 제목 {title}"
                response = model.generate_content(prompt)
                score_text = ''.join(filter(str.isdigit, response.text))
                ai_score = int(score_text) if score_text else 80
            except Exception as e:
                print(f"인공지능 연산 오류 발생 {e}")
                ai_score = 0 
            
            total_score = round((base_score * 0.4) + (ai_score * 0.6), 2)
            time.sleep(2) 
        else: 
            ai_score = 0
            total_score = round(base_score * 0.4, 2)
            
        archive_rows.append([date, title, url, matched_media, base_score, ai_score, total_score, 'N'])

    if archive_rows:
        archive_sheet.append_rows(archive_rows)
        
    stage_sheet.resize(rows=1)
    print("인공지능 분석 및 아카이브 영구 저장이 완료되었습니다.")

if __name__ == "__main__":
    process_ai_score()
