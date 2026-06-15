import os, json, gspread
import time
from datetime import datetime
import pytz
from oauth2client.service_account import ServiceAccountCredentials

KST = pytz.timezone('Asia/Seoul')

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
GROQ_KEY = os.environ.get("GROQ_API_KEY", "")
CLAUDE_KEY = os.environ.get("CLAUDE_API_KEY", "")

# 클라이언트 초기화
try:
    import google.generativeai as genai
    if GEMINI_KEY: genai.configure(api_key=GEMINI_KEY)
except ImportError: genai = None

try:
    from groq import Groq
    groq_client = Groq(api_key=GROQ_KEY) if GROQ_KEY else None
except ImportError: groq_client = None

try:
    import anthropic
    claude_client = anthropic.Anthropic(api_key=CLAUDE_KEY) if CLAUDE_KEY else None
except ImportError: claude_client = None

creds = ServiceAccountCredentials.from_json_keyfile_dict(
    json.loads(os.environ["GOOGLE_SHEETS_CREDENTIALS"]),
    ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
)
spreadsheet = gspread.authorize(creds).open("News_Management_DB")

# 사내 800건 공유 사례를 역분석한 핵심 스크리닝 명세
EXECUTIVE_SCREENING_MANDATE = """
당신은 금융그룹 경영전략실 수석 투자 분석가입니다. 
다음 스크리닝 명세에 따라 기사를 분석하여 0~100점의 점수를 부여하십시오.
1. 핵심 입력값 확인: 가격, 지분율, 구조, 일정 등 '행동 가능한 팩트'가 포함된 기사를 우대합니다.
2. 라이브 딜 추적: 매물화 -> 입찰 -> 실사 -> SPA -> 당국 심사 등 딜의 진행 단계 변화를 다루는 기사에 가점합니다.
3. 우선순위: 한화생명 전략, 경쟁사 자본 거래, PEF 구조 분석, 규제/감독 인텔리전스, 해외 벤치마크 딜을 최상위로 평가합니다.
4. 필터링: 단순 보도자료, 광고, 행사, 전망 일반론은 하위권으로 배제하십시오.
"""

def get_persona_and_rubric():
    sys_sheet = spreadsheet.worksheet("Config_System")
    config = {str(r.get("Key")): str(r.get("Value")) for r in sys_sheet.get_all_records()}
    active_opt = config.get("ACTIVE_PERSONA", "옵션 1 (기본 금융 전문가)")
    default_persona = config.get("PERSONA_1", "당신은 냉철한 금융 전문가입니다.") if "옵션 1" in active_opt else config.get("PERSONA_2", "당신은 트렌드에 민감한 기술 전문 투자자입니다.")
    
    rubric_text = "채점 기준:\n"
    try:
        for row in spreadsheet.worksheet("Config_Rubric").get_all_records():
            rubric_text += f"- {row.get('Criteria', '')} (최대 {row.get('Score', 0)}점): {row.get('Description', '')}\n"
    except: pass
    return default_persona, rubric_text

def process_ai_score():
    print("🤖 AI 심층 분석(30개 배치)을 시작합니다...")
    stage_sheet = spreadsheet.worksheet("DB_Stage")
    archive_sheet = spreadsheet.worksheet("DB_Archive")
    
    try:
        ai_report_sheet = spreadsheet.worksheet("DB_AI_Report")
    except:
        ai_report_sheet = spreadsheet.add_worksheet(title="DB_AI_Report", rows="1000", cols="10")
        ai_report_sheet.append_row(["Execution_Time", "Date", "Title", "Link", "Media", "Matched_Keywords", "Base_Score", "AI_Score", "Total_Score", "Sent"])
    
    rows = stage_sheet.get_all_values()
    if len(rows) <= 1: return

    # 설정값 로드
    sys_sheet = spreadsheet.worksheet("Config_System")
    config = {str(r.get("Key")): str(r.get("Value")) for r in sys_sheet.get_all_records()}
    engine = config.get("AI_ENGINE", "유료 Claude
