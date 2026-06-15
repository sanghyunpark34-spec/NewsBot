# ... (상단 설정 부분은 동일합니다)

def process_ai_score():
    print("🤖 프롬프트 고도화 및 본문 요약문 분석 가동...")
    stage_sheet = spreadsheet.worksheet("DB_Stage")
    archive_sheet = spreadsheet.worksheet("DB_Archive")
    ai_report_sheet = spreadsheet.worksheet("DB_AI_Report")
    
    rows = stage_sheet.get_all_values()
    if len(rows) <= 1: return

    # 시스템 설정 및 프롬프트 로드
    sys_sheet = spreadsheet.worksheet("Config_System")
    config = {str(r.get("Key")): str(r.get("Value")) for r in sys_sheet.get_all_records()}
    ai_weight = float(config.get("AI_WEIGHT_PERCENT", 55)) / 100.0
    base_weight = 1.0 - ai_weight
    
    base_persona, rubric_prompt = get_persona_and_rubric()
    # 💡 강화된 스크리닝 지시문 결합
    combined_system_prompt = f"{base_persona}\n\n[핵심 스크리닝 명세]\n{EXECUTIVE_SCREENING_MANDATE}"
    
    target_rows = rows[1:31]
    remaining_rows = rows[31:]
    
    # 💡 [핵심 변경] AI에게 '요약문'까지 넘겨주도록 프롬프트 구조 변경
    batch_prompt = f"{rubric_prompt}\n\n다음 {len(target_rows)}개 기사의 제목과 요약 내용을 분석하여 0~100점 사이로 채점해줘.\n형식은 JSON: {{'1': 점수, '2': 점수, ...}}\n\n기사 데이터:\n"
    for i, row in enumerate(target_rows):
        # row[1]은 제목, row[6]은 analyzer_base에서 넘어온 요약문(desc)입니다.
        batch_prompt += f"{i+1}. 제목: {row[1]} | 요약: {row[6]}\n"

    # ... (엔진 호출 및 JSON 파싱 로직은 동일)

    # 💡 데이터 저장 시 요약문(row[6]) 유지 및 정규화
    archive_rows = []
    ai_report_rows = []
    now_str = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    
    for i, row in enumerate(target_rows):
        idx_str = str(i+1)
        base_score = float(row[5])
        details = scores_map.get(idx_str, [])
        # 가중치 연산... (동일)
        
        # 💡 [필수] 아카이브와 AI 리포트에 요약문을 포함하여 저장
        archive_rows.append([now_str, row[1], row[2], row[3], row[4], base_score, detail_str, total, 'N'])
        ai_report_rows.append([now_str, row[0], row[1], row[2], row[3], row[4], base_score, detail_str, total, 'N'])

    # 나머지 코드도 동일하게 유지...
