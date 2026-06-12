# app.py 의 '🤖 시스템 및 알림 설정' 메뉴 부분만 아래 내용으로 교체하시면 됩니다.
elif menu == "🤖 시스템 및 알림 설정":
    st.title("🤖 시스템 및 텔레그램 설정")
    st.markdown("---")
    
    col_sys1, col_sys2 = st.columns([1, 1])
    try:
        try: sys_sheet = spreadsheet.worksheet("Config_System")
        except: sys_sheet = spreadsheet.add_worksheet("Config_System", 10, 2); sys_sheet.append_row(["Key", "Value"]); sys_sheet.append_row(["AI_ENGINE", "AI 사용 안 함"])
        
        config = {str(r.get("Key")): str(r.get("Value")) for r in sys_sheet.get_all_records()}
        current_engine = config.get("AI_ENGINE", "AI 사용 안 함")
        current_tg_group = config.get("TELEGRAM_GROUP_SEND", "OFF")
        current_tg_author = config.get("TELEGRAM_AUTHOR_SEND", "OFF")
        current_extra_ids = config.get("EXTRA_TELEGRAM_IDS", "")
        
        with col_sys1:
            st.subheader("⚙️ 구동할 AI 엔진 선택")
            opts = ["AI 사용 안 함", "무료 Gemini", "무료 Groq", "전체"]
            selected_engine = st.selectbox("엔진 종류", opts, index=opts.index(current_engine) if current_engine in opts else 0, label_visibility="collapsed")
            
        with col_sys2:
            st.subheader("📱 텔레그램 발송 제어")
            st.markdown("<div style='padding: 10px; border: 1px solid #E5E7EB; border-radius: 8px;'>", unsafe_allow_html=True)
            tg_group_toggle = st.toggle("📢 부서 단톡방 전송", value=(current_tg_group == "ON"))
            st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
            tg_author_toggle = st.toggle("👤 작성자 개인 수신 (MY_CHAT_ID)", value=(current_tg_author == "ON"))
            
            # 추가 수신자 입력란 복구
            extra_ids_input = st.text_input("➕ 추가 수신자 아이디 (쉼표로 구분)", value=current_extra_ids, placeholder="예: 1234567, 7654321")
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("💾 시스템 및 알림 설정 모두 저장", type="primary", use_container_width=True):
            def update_setting(key, value):
                try: cell = sys_sheet.find(key); sys_sheet.update_cell(cell.row, cell.col + 1, value)
                except: sys_sheet.append_row([key, value])
            update_setting("AI_ENGINE", selected_engine)
            update_setting("TELEGRAM_GROUP_SEND", "ON" if tg_group_toggle else "OFF")
            update_setting("TELEGRAM_AUTHOR_SEND", "ON" if tg_author_toggle else "OFF")
            update_setting("EXTRA_TELEGRAM_IDS", extra_ids_input)
            st.success("설정이 데이터베이스에 성공적으로 기록되었습니다!")
    except Exception as e: st.error(f"오류: {e}")
