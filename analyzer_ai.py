import os, json, gspread, time
import google.generativeai as genai
from groq import Groq
from oauth2client.service_account import ServiceAccountCredentials

creds = ServiceAccountCredentials.from_json_keyfile_dict(
    json.loads(os.environ["GOOGLE_SHEETS_CREDENTIALS"]),
    ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
)
spreadsheet = gspread.authorize(creds).open("News_Management_DB")

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
gemini_model = genai.GenerativeModel('gemini-3.5-flash') 

# [수정] 그록 클라이언트에 15초 타임아웃 강제 부여
groq_client = Groq(api_key=os.environ["GROQ_API_KEY"], timeout=15.0)

def get_rubric_text():
    try:
        rubric_sheet = spreadsheet.worksheet("Config_Rubric")
        records = rubric_sheet.get_all_records()
        rubric_text = "다음은 기사 제목을 평가할 50점 만점의 상세 채점 기준입니다.\n\n"
        for row in records:
            criteria = row.get('평가 기준', row.get('Criteria', ''))
            desc = row.get('상세 설명', row.get('Description', ''))
            score = row.get('배점', row.get('Score', 0))
            if criteria:
                rubric_text += f"- {criteria} (최대 {score}점) {desc}\n"
        return rubric_text
    except Exception as e:
        print(f"평가 기준표 로드 실패: {e}", flush=True)
        return "자본 시장 동향 및 금융업 인수합병 관련성을 기준으로 50점 만점으로 평가해 주세요."

def evaluate_with_gemini(prompt):
    try:
        # [수정] 제미나이 요청에 15초 타임아웃 강제 부여
        response = gemini_model.generate_content(prompt, request_options={"timeout": 15.0})
        score_text = ''.join(filter(str.isdigit, response.text))
        return int(score_text) if score_text else None
    except Exception as e:
        print(f"  -> 제미나이 응답 실패/지연: {e}", flush=True)
        return None

def evaluate_with_groq(prompt):
    try:
        response = groq_client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0.1
        )
        score_text = ''.join(filter(str.isdigit, response.choices[0].message.content))
        return int(score_text) if score_text else None
    except Exception as e:
        print(f"  -> 그록 응답 실패/지연: {e}", flush=True)
        return None

def process_ai_score():
    stage_sheet = spreadsheet.worksheet("DB_Stage")
    archive_sheet = spreadsheet.worksheet("DB_Archive")
    
    rows = stage_sheet.get_all_values()
    if len(rows) <= 1:
        print("인공지능 분석을 진행할 대기 기사가 없습니다.", flush=True)
        return

    rubric_prompt = get_rubric_text()
    archive_rows = []
    
    for i, row in enumerate(rows[1:]):
        if len(row) < 5:
            continue
            
        date, title, url, matched_media = row[0], row[1], row[2], row[3]
        
        try:
            base_score = float(row[4])
        except Exception:
            base_score = 0
            
        if i < 20: 
            # [수정] 어느 기사를 평가하고 있는지 실시간(flush=True)으로 깃허브에 출력
            print(f"\n[{i+1}/20] 평가 시작: {title[:20]}...", flush=True)
            
            evaluation_prompt = f"{rubric_prompt}\n\n위 기준을 바탕으로 다음 뉴스 기사 제목의 점수를 계산해 주세요. 부연 설명은 절대 하지 말고 오직 최종 합산된 숫자(50점 만점)만 답변해 주세요. 기사 제목 {title}"
            
            gemini_score = evaluate_with_gemini(evaluation_prompt)
            groq_score = evaluate_with_groq(evaluation_prompt)
            
            if gemini_score is not None and groq_score is not None:
                ai_score = round((gemini_score + groq_score) / 2)
                print(f"  ✅ 듀얼 완료 (제미나이 {gemini_score}점 / 그록 {groq_score}점) -> 최종 {ai_score}점", flush=True)
            elif gemini_score is not None:
                ai_score = gemini_score
                print(f"  ⚠ 제미나이 단독 완료 -> 최종 {ai_score}점", flush=True)
            elif groq_score is not None:
                ai_score = groq_score
                print(f"  ⚠ 그록 단독 완료 -> 최종 {ai_score}점", flush=True)
            else:
                ai_score = 0
                print(f"  ❌ 두 AI 모두 실패 -> 기본 0점", flush=True)
            
            time.sleep(1) 
        else: 
            ai_score = 0
            
        total_score = round((base_score * 0.5) + ai_score, 2)
        archive_rows.append([date, title, url, matched_media, base_score, ai_score, total_score, 'N'])

    if archive_rows:
        archive_sheet.append_rows(archive_rows)
        
    stage_sheet.resize(rows=1)
    print("\n🎉 인공지능 분석 및 아카이브 영구 저장이 성공적으로 완료되었습니다.", flush=True)

if __name__ == "__main__":
    process_ai_score()
