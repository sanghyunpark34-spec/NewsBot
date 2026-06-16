import os, json, gspread
from datetime import datetime
import pytz
from oauth2client.service_account import ServiceAccountCredentials

KST = pytz.timezone('Asia/Seoul')

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
GROQ_KEY = os.environ.get("GROQ_API_KEY", "")
CLAUDE_KEY = os.environ.get("CLAUDE_API_KEY", "")

try:
    from google import genai
except ImportError:
    genai = None

try:
    from groq import Groq
    groq_client = Groq(api_key=GROQ_KEY) if GROQ_KEY else None
except ImportError:
    groq_client = None

try:
    import anthropic
    claude_client = anthropic.Anthropic(api_key=CLAUDE_KEY) if CLAUDE_KEY else None
except ImportError:
    claude_client = None

creds = ServiceAccountCredentials.from_json_keyfile_dict(
    json.loads(os.environ["GOOGLE_SHEETS_CREDENTIALS"]),
    ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
)
spreadsheet = gspread.authorize(creds).open("News_Management_DB")

EXECUTIVE_SCREENING_MANDATE = """
당신은 대한민국 최고 금융그룹의 경영전략실 수석 투자 분석가이자 M&A 총괄 책임자입니다.
단순히 토픽 단어가 포함되었다고 점수를 주는 것이 아니라, "같은 토픽이라도 실무진 및 경영진의 의사결정에 직결되는 기사"인지를 철저히 역분석된 하단 기준에 따라 엄격하게 0~100점 사이로 채점해야 합니다.

0. 한 줄 판단 기준 (모든 판단의 출발점)
- 해당 기사가 한화 금융의 ①딜 의사결정, ②자본/규제 대응, ③경쟁 포지셔닝 중 하나에 직접적인 실질적 입력값이 되는가?
- 입력값 충족 신호: 가격, 지분율, 구조, 구체적 일정, 당국 스탠스 등 행동 가능한 '팩트'와 '숫자'가 명시됨. (예: "IB 업계에 따르면", "[단독]", 구체적인 거래 금액, K-ICS 변동 수치 포함)
- 탈락 신호:순수 현상 묘사, 업계 일반론, 단순 보도자료 재가공 기사는 아무리 관련 키워드가 많아도 최하점 부여. 동일 사건이면 숫자와 거래 구조가 가장 구체적인 기사에 최고점 부여.

1. 라이브 딜 추적 가중치 (최우선순위)
- 단발성 뉴스가 아닌, 진행 중인 주요 매물의 '단계 변화' 및 인프라 업데이트에 초고점 부여:
  [매물화/티저발송 -> 예비입찰 -> 실사착수 -> 본입찰 -> 우선협상대상자 -> SPA/텀싯 -> 당국심사 -> 클로징/무산/재매각]
- 대상 타깃 예시: MG손보, 롯데카드, 롯데손보, 동양/ABL생명, 이지스자산운용, 한양증권, 테일러메이드, 교보생명 분쟁, KDB생명, 아워홈, 굿리치, 더피플라이프, 카카오페이손보, SBI/페퍼/상상인저축은행, 두나무 등.
- 유찰, 무산, 일정 지연, 당국 제동(심사 중단 등) 역시 진전과 동급의 중대한 뉴스 가치로 취급하여 고점 부여.

2. 카테고리별 세부 선별 전략 패턴
- A. 한화 관련: 실적 해설기사보다 숫자+컨센 대비 공시 팩트 중심 평가. 신용등급 변동, 금감원 제재/소송, 밸류업 계획 필수 포함. 오너가/승계/지분 이동/계열사 분할합병은 비금융 계열사라도 중대 사항으로 취급.
- B. 경쟁사 동향: 상품 출시보다 '인수 의지 및 M&A 검토 보도', '자본 거래', '채널 전략', '자본배분 철학 분석'에 집중 가점.
- C. PEF 생태계: 보험 상품 뉴스보다 압도적인 우선순위 부여. PEF의 금융사 소유 구조 문제, GP-LP 다이내믹스, 딜 인프라를 심도 있게 다룬 기사 선호.
- D. 규제/감독 인텔리전스: 금융당국 인사 정보, K-ICS 규제, 상법 개정, 당국 심사 동향은 상시 최상위 순위로 평가.
- E. 해외 및 디지털자산: 일본 생/손보사의 크로스보더 M&A 등 글로벌 벤치마크 딜 고점 부여. STO/가상자산은 대형 금융그룹의 지분 취득 및 제휴 딜 관점에서만 가점. 지배구조 분쟁의 지분 구조와 법적 논리 해설 선호.

3. 기사 품질 신호 기반 필터링
- 가점 매체 및 표현: [단독], "투자은행(IB) 업계에 따르면", 주요 IB 전문매체의 심층 구조 분석 기사.
- 감점 및 필터링 대상: 상품 광고, CSR, 스포츠/행사, 단순 시황성 주가 등락, 단순 전망 일반론 기사는 배제.
"""

def get_persona_and_rubric():
    sys_sheet = spreadsheet.worksheet("Config_System")
    config = {str(r.get("Key")): str(r.get("Value")) for r in sys_sheet.get_all_records()}
    active_opt = config.get("ACTIVE_PERSONA", "옵션 1 (기본 금융 전문가)")
    default_persona = config.get("PERSONA_1", "당신은 냉철한 금융 전문가입니다.") if "옵션 1" in active_opt else config.get("PERSONA_2", "당신은 트렌드에 민감한 기술 전문 투자자입니다.")
    
    rubric_text = "기본 채점 가이드라인:\n"
    try:
        for row in spreadsheet.worksheet("Config_Rubric").get_all_records():
            rubric_text += f"- {row.get('Criteria', '')} (최대 {row.get('Score', 0)}점): {row.get('Description', '')}\n"
    except: pass
    return default_persona, rubric_text

def process_ai_score():
    print("🤖 프롬프트 고도화 및 본문 요약문 분석 가동...")
    try:
        stage_sheet = spreadsheet.worksheet("DB_Stage")
        archive_sheet = spreadsheet.worksheet("DB_Archive")
        
        try:
            ai_report_sheet = spreadsheet.worksheet("DB_AI_Report")
        except:
            ai_report_sheet = spreadsheet.add_worksheet(title="DB_AI_Report", rows="1000", cols="10")
            ai_report_sheet.append_row(["Execution_Time", "Date", "Title", "Link", "Media", "Matched_Keywords", "Base_Score", "AI_Score", "Total_Score", "Sent"])
        
        rows = stage_sheet.get_all_values()
        if len(rows) <= 1: 
            print("⚠️ DB_Stage에 분석할 기사가 없습니다.")
            return

        sys_sheet = spreadsheet.worksheet("Config_System")
        config = {str(r.get("Key")): str(r.get("Value")) for r in sys_sheet.get_all_records()}
        
        engine_choice = config.get("AI_ENGINE", "유료 Claude")
        try:
            ai_weight_pct = float(config.get("AI_WEIGHT_PERCENT", 55))
        except:
            ai_weight_pct = 55.0
            
        ai_weight = ai_weight_pct / 100.0
        base_weight = 1.0 - ai_weight
        
        base_persona, rubric_prompt = get_persona_and_rubric()
        combined_system_prompt = f"{base_persona}\n\n[핵심 스크리닝 명세]\n{EXECUTIVE_SCREENING_MANDATE}"
        
        data_rows = rows[1:]
        count_over_50 = 0
        
        for r in data_rows:
            try:
                # 💡 50점 '초과'로 조건 변경 완료
                if float(r[5]) > 50.0: 
                    count_over_50 += 1
            except: 
                pass

        limit = 30
        if count_over_50 > 30:
            limit = min(count_over_50, 50)
            
        print(f"📊 기초 점수 50점 초과 기사: {count_over_50}개 ➡️ 이번 회차 AI 심층 평가 대상: {limit}개로 자동 조정됨.")

        target_rows = data_rows[:limit]
        remaining_rows = data_rows[limit:]
        
        batch_prompt = f"{rubric_prompt}\n\n다음 {len(target_rows)}개 기사의 제목과 요약 내용을 분석하여 0~100점 사이로 채점해줘.\n형식은 JSON: {{'1': 점수, '2': 점수, ...}}\n\n기사 데이터:\n"
        for i, row in enumerate(target_rows):
            desc = row[6] if len(row) > 6 else ""
            batch_prompt += f"{i+1}. 제목: {row[1]} | 요약: {desc}\n"

        scores_map = {}
        engines_to_run = []
        
        if "Gemini" in engine_choice or "전체" in engine_choice: engines_to_run.append("Gemini")
        if "Groq" in engine_choice or "전체" in engine_choice: engines_to_run.append("Groq")
        if "Claude" in engine_choice or "전체" in engine_choice: engines_to_run.append("Claude")

        if not engines_to_run or engine_choice == "AI 사용 안 함":
            print("⚠️ AI 엔진이 선택되지 않았습니다.")
        else:
            for model_name in engines_to_run:
                print(f"🚀 {model_name} 핵심 스크리닝 연산 요청 중...")
                try:
                    res_json = ""
                    # 💡 최신 google.genai 문법 적용 완료
                    if model_name == "Gemini" and genai:
                        client = genai.Client(api_key=GEMINI_KEY)
                        res_json = client.models.generate_content(
                            model='gemini-1.5-flash', 
                            contents=f"{combined_system_prompt}\n\n{batch_prompt}"
                        ).text
                    elif model_name == "Groq" and groq_client:
                        res = groq_client.chat.completions.create(
                            model="llama3-70b-8192", 
                            messages=[{"role": "system", "content": combined_system_prompt}, {"role": "user", "content": batch_prompt}]
                        )
                        res_json = res.choices[0].message.content
                    elif model_name == "Claude" and claude_client:
                        msg = claude_client.messages.create(
                            model="claude-haiku-4-5-20251001", 
                            max_tokens=2500, 
                            system=combined_system_prompt, 
                            messages=[{"role": "user", "content": batch_prompt}]
                        )
                        res_json = msg.content[0].text
                    
                    if res_json:
                        start, end = res_json.find('{'), res_json.rfind('}')
                        if start != -1 and end != -1:
                            data = json.loads(res_json[start:end+1])
                            for k, v in data.items():
                                if k not in scores_map: scores_map[k] = []
                                scores_map[k].append((model_name, int(v)))
                            print(f"✅ {model_name} 핵심 스크리닝 연산 성공!")
                except Exception as e:
                    print(f"❌ {model_name} 엔진 분석 지연 스킵: {e}")

        archive_rows = []
        ai_report_rows = []
        now_str = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
        
        for i, row in enumerate(target_rows):
            idx_str = str(i+1)
            base_score = float(row[5])
            details = scores_map.get(idx_str, [])
            if details:
                avg = sum([d[1] for d in details]) / len(details)
                detail_str = f"{round(avg, 1)} ({', '.join([f'{d[0]} {d[1]}' for d in details])})"
                total = round((base_score * base_weight) + (avg * ai_weight), 2)
            else:
                detail_str, total = "0", base_score
            
            archive_rows.append([now_str, row[1], row[2], row[3], row[4], base_score, detail_str, total, 'N'])
            ai_report_rows.append([now_str, row[0], row[1], row[2], row[3], row[4], base_score, detail_str, total, 'N'])

        for row in remaining_rows:
            base_score = float(row[5])
            archive_rows.append([now_str, row[1], row[2], row[3], row[4], base_score, "AI 미평가 (순위 밖)", base_score, 'N'])

        if archive_rows:
            archive_sheet.append_rows(archive_rows)
            
        if ai_report_rows:
            ai_report_rows.sort(key=lambda x: float(x[8]), reverse=True) 
            ai_report_sheet.append_rows(ai_report_rows)
            print(f"🎯 누적 공유 자산이 적용된 최상위 {len(ai_report_rows)}개 기사가 DB_AI_Report에 이관되었습니다.")
        
        stage_sheet.resize(rows=1)
        
    except Exception as e:
        print(f"❌ 프로세스 실행 중 치명적 에러 발생: {e}")

if __name__ == "__main__":
    process_ai_score()
