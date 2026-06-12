# app.py의 106행 부근 (🤖 시스템 및 알림 설정 부분 전체 교체)
elif menu == "🤖 시스템 및 알림 설정":
    st.title("🤖 시스템 및 텔레그램 설정")
    st.markdown("---")
    
    col_sys1, col_sys2 = st.columns([1, 1])
    try:
        sys_sheet = spreadsheet.worksheet("Config_System")
        config = {str(r.get("Key")): str(r.get("Value")) for r in sys_sheet.get_all_records()}
        current_engine = config.get("AI_ENGINE", "AI 사용 안 함")
        
        with col_sys1:
            st.subheader("⚙️ 구동할 AI 엔진 선택")
            selected_engine = st.selectbox("엔진 종류", ["AI 사용 안 함", "무료 Gemini", "무료 Groq", "전체"], index=["AI 사용 안 함", "무료 Gemini", "무료 Groq", "전체"].index(current_engine) if current_engine in ["AI 사용 안 함", "무료 Gemini", "무료 Groq", "전체"] else 0)
            
        with col_sys2:
            st.subheader("📱 텔레그램 발송 제어")
            st.markdown("<div style='padding: 10px; border: 1px solid #E5E7EB; border-radius: 8px;'>", unsafe_allow_html=True)
            tg_group_toggle = st.toggle("📢 부서 단톡방 전송 허용", value=(config.get("TELEGRAM_GROUP_SEND") == "ON"))
            st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
            tg_author_toggle = st.toggle("👤 작성자 개인 수신 허용", value=(config.get("TELEGRAM_AUTHOR_SEND") == "ON"))
            extra_ids_input = st.text_input("➕ 추가 수신자 ID (쉼표 구분)", value=config.get("EXTRA_TELEGRAM_IDS", ""))
            st.markdown("</div>", unsafe_allow_html=True)

        if st.button("💾 시스템 및 알림 설정 모두 저장", type="primary", use_container_width=True):
            def update(k, v):
                try: cell = sys_sheet.find(k); sys_sheet.update_cell(cell.row, cell.col + 1, v)
                except: sys_sheet.append_row([k, v])
            update("AI_ENGINE", selected_engine)
            update("TELEGRAM_GROUP_SEND", "ON" if tg_group_toggle else "OFF")
            update("TELEGRAM_AUTHOR_SEND", "ON" if tg_author_toggle else "OFF")
            update("EXTRA_TELEGRAM_IDS", extra_ids_input)
            st.success("저장 완료!")
    except Exception as e: st.error(f"오류: {e}")
