import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import pandas as pd
import requests
import streamlit.components.v1 as components

st.set_page_config(page_title="뉴스 자동화 대시보드", page_icon="📰", layout="wide")

@st.cache_resource
def init_connection():
    creds_dict = json.loads(st.secrets["GOOGLE_SHEETS_CREDENTIALS"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        creds_dict,
        ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    )
    return gspread.authorize(creds).open("News_Management_DB")

try:
    spreadsheet = init_connection()
except Exception as e:
    st.error(f"구글 시트 연결에 실패했습니다. {e}")
    st.stop()

st.sidebar.title("통합 제어판 ⚙️")

timer_html = """
<div style="background-color: #E8F1FF; padding: 12px; border-radius: 8px; text-align: center; margin-bottom: 10px;">
    <div style="font-size: 13px; color: #4F8BF9; font-weight: bold; margin-bottom: 4px;">⏱️ 다음 자동 기사 서치(오후 3시 17분)까지</div>
    <div id="countdown" style="font-size: 22px; font-weight: 900; color: #1E3A8A;"></div>
</div>
<script>
    function updateTimer() {
        var now = new Date();
        var utc = now.getTime() + (now.getTimezoneOffset() * 60000);
        var kst = new Date(utc + (3600000 * 9));
        
        var target = new Date(kst);
        target.setHours(15, 17, 0, 0);
        
        if (kst.getHours() > 15 || (kst.getHours() == 15 && kst.getMinutes() >= 17)) {
            target.setDate(target.getDate() + 1);
        }
        
        var diff = target - kst;
        var hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        var minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
        var seconds = Math.floor((diff % (1000 * 60)) / 1000);
        
        document.getElementById("countdown").innerText = hours + "시간 " + minutes + "분 " + seconds + "초";
    }
    setInterval(updateTimer, 1000);
    updateTimer();
</script>
"""
with st.sidebar:
    components.html(timer_html, height=85)

st.sidebar.subheader("🚀 퀵 기사 서치 실행")
if st.sidebar.button("▶️ 지금 기사 서치 가동", type="primary", use_container_width=True):
    github_repo = "sanghyunpark34-spec/NewsBot"
    workflow_file = "news_pipeline.yml"
    
    if "GITHUB_TOKEN" not in st.secrets:
        st.sidebar.error("스트림릿 Secrets 금고에 GITHUB_TOKEN이 등록되지 않았습니다.")
    else:
        url = f"https://api.github.com/repos/{github_repo}/actions/workflows/{workflow_file}/dispatches"
        headers = {"Authorization": f"token {st.secrets['GITHUB_TOKEN']}", "Accept": "application/vnd.github.v3+json"}
        with st.spinner('깃허브 서버 가동 중...'):
            res = requests.post(url, headers=headers, json={"ref": "main"})
        
        if res.status_code == 204: 
            st.sidebar.success("🚀 가동 명령 송신 완료! 잠시 후 파이프라인이 작동합니다.")
        else: 
            st.sidebar.error(f"가동 실패 코드를 확인해주세요. ({res.status_code})")
st.sidebar.markdown("---")

menu = st.sidebar.radio(
    "세부 메뉴를 선택하세요",
    ["📊 종합 상황판", "🔑 포함/제외 단어 제어", "📡 타깃 매체 제어", "🤖 AI 및 시스템 설정"]
)

if menu == "📊 종합 상황판":
    st.title("📊 기사 서치 종합 상황판")
    st.markdown("---")
    st.subheader("최근 분석 완료된 탑 20 기사 목록")
    try:
        top20_sheet = spreadsheet.worksheet("DB_Top20")
        data = top20_sheet.get_all_records()
        if data:
            df = pd.DataFrame(data)
            latest_time = df['Execution_Time'].max()
            df_latest = df[df['Execution_Time'] == latest_time]
            df_display = df_latest.drop(columns=['Execution_Time', 'Sent'], errors='ignore')
            st.dataframe(df_display, use_container_width=True, hide_index=True)
        else:
            st.info("아직 누적된 데이터가 없습니다.")
    except Exception:
        st.warning("DB_Top20 시트를 찾을 수 없습니다.")

elif menu == "🔑 포함/제외 단어 제어":
    st.title("🔑 키워드 점수 조절 및 제외 설정")
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📌 타깃 키워드 점수 설정 (Max 10)")
        st.write("우측의 숫자를 조절하여 긍정 키워드 점수를 조절하세요.")
        try:
            kw_sheet = spreadsheet.worksheet("Config_Keywords")
            kw_data = kw_sheet.get_all_records()
            
            updated_kws = []
            for idx, row in enumerate(kw_data):
                kw = str(row.get('Keyword', '')).strip()
                if not kw: continue
                c1, c2 = st.columns([3, 1.5])
                with c1:
                    st.markdown(f"<div style='padding-top: 8px; font-weight: 600; font-size: 16px;'>{kw}</div>", unsafe_allow_html=True)
                with c2:
                    current_w = float(row.get('Weight', row.get('Coefficient', 1.0)))
                    new_w = st.number_input("점수", min_value=0.0, max_value=10.0, value=current_w, step=1.0, key=f"kw_{idx}", label_visibility="collapsed")
                updated_kws.append([kw, new_w])
                
            st.markdown("---")
            with st.expander("➕ 새로운 타깃 키워드 추가하기"):
                new_kw = st.text_input("새로 추가할 키워드 입력")
                new_w = st.number_input("새 키워드 점수", min_value=0.0, max_value=10.0, value=1.0, step=1.0)
            
            if st.button("💾 타깃 키워드 모두 저장", type="primary"):
                if new_kw.strip() != "":
                    updated_kws.append([new_kw.strip(), new_w])
                with st.spinner('저장 중...'):
                    kw_sheet.clear()
                    kw_sheet.update([["Keyword", "Weight"]] + updated_kws)
                st.success("타깃 키워드가 성공적으로 저장되었습니다!")
        except Exception as e: 
            st.error(f"키워드 시트 오류가 발생했습니다. {e}")

    with col2:
        st.subheader("🚫 제외 단어 감점 설정")
        st.write("우측의 숫자를 조절하여 차감할 감점 폭을 세밀하게 조절하세요.")
        try:
            try: neg_sheet = spreadsheet.worksheet("Config_Negative")
            except: 
                neg_sheet = spreadsheet.add_worksheet(title="Config_Negative", rows="100", cols="2")
                neg_sheet.append_row(["Keyword", "Coefficient"])
            
            neg_data = neg_sheet.get_all_records()
            
            updated_negs = []
            for idx, row in enumerate(neg_data):
                kw = str(row.get('Keyword', '')).strip()
                if not kw: continue
                c1, c2 = st.columns([3, 1.5])
                with c1:
                    st.markdown(f"<div style='padding-top: 8px; font-weight: 600; font-size: 16px;'>{kw}</div>", unsafe_allow_html=True)
                with c2:
                    current_w = float(row.get('Coefficient', 20.0))
                    new_w = st.number_input("감점", min_value=0.0, max_value=100.0, value=current_w, step=1.0, key=f"neg_{idx}", label_visibility="collapsed")
                updated_negs.append([kw, new_w])
                
            st.markdown("---")
            with st.expander("➕ 새로운 제외 단어 추가하기"):
                new_neg = st.text_input("새로 추가할 제외 단어 입력")
                new_nw = st.number_input("새 단어 감점 폭", min_value=0.0, max_value=100.0, value=20.0, step=1.0)
            
            if st.button("💾 제외 단어 모두 저장", type="primary"):
                if new_neg.strip() != "":
                    updated_negs.append([new_neg.strip(), new_nw])
                with st.spinner('저장 중...'):
                    neg_sheet.clear()
                    neg_sheet.update([["Keyword", "Coefficient"]] + updated_negs)
                st.success("제외 단어 설정이 성공적으로 저장되었습니다!")
        except Exception as e: 
            st.error(f"제외 키워드 시트 오류가 발생했습니다. {e}")

elif menu == "📡 타깃 매체 제어":
    st.title("📡 타깃 매체 가중치 제어")
    st.markdown("---")
    st.subheader("뉴스 출처(언론사) 점수 설정 (Max 5)")
    st.write("우측의 숫자를 조절하여 점수를 조절하세요.")
    
    try:
        media_sheet = spreadsheet.worksheet("Config_Media")
        media_data = media_sheet.get_all_records()
        
        updated_media = []
        for idx, row in enumerate(media_data):
            domain = str(row.get('Domain', '')).strip()
            if not domain: continue
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(f"<div style='padding-top: 8px; font-weight: 600; font-size: 16px;'>{domain}</div>", unsafe_allow_html=True)
            with c2:
                current_w = float(row.get('Weight', row.get('Coefficient', 0.0)))
                new_w = st.number_input("점수", min_value=0.0, max_value=5.0, value=current_w, step=1.0, key=f"media_{idx}", label_visibility="collapsed")
            updated_media.append([domain, new_w])
            
        st.markdown("---")
        with st.expander("➕ 새로운 언론사 도메인 추가하기"):
            new_domain = st.text_input("새 언론사 이름(도메인) 입력")
            new_mw = st.number_input("새 언론사 점수", min_value=0.0, max_value=5.0, value=1.0, step=1.0)
            
        if st.button("💾 언론사 매체 모두 저장", type="primary"):
            if new_domain.strip() != "":
                updated_media.append([new_domain.strip(), new_mw])
            with st.spinner('저장 중...'):
                media_sheet.clear()
                media_sheet.update([["Domain", "Weight"]] + updated_media)
            st.success("매체 가중치가 성공적으로 저장되었습니다!")
    except Exception as e: 
        st.error(f"매체 시트 오류가 발생했습니다. {e}")

elif menu == "🤖 AI 및 시스템 설정":
    st.title("🤖 시스템 및 텔레그램 설정")
    st.markdown("---")
    
    st.subheader("⚙️ 구동할 AI 엔진 선택")
    try:
        try: sys_sheet = spreadsheet.worksheet("Config_System")
        except:
            sys_sheet = spreadsheet.add_worksheet(title="Config_System", rows="10", cols="2")
            sys_sheet.append_row(["Key", "Value"])
            sys_sheet.append_row(["AI_ENGINE", "AI 사용 안 함"])
            sys_sheet.append_row(["TELEGRAM_GROUP_SEND", "OFF"])
            sys_sheet.append_row(["TELEGRAM_PERSONAL_ID", ""])
            
        sys_data = sys_sheet.get_all_records()
        current_engine = "AI 사용 안 함"
        current_tg_group = "OFF"
        current_tg_personal = ""
        
        for row in sys_data:
            if row.get("Key") == "AI_ENGINE": current_engine = str(row.get("Value"))
            if row.get("Key") == "TELEGRAM_GROUP_SEND": current_tg_group = str(row.get("Value"))
            if row.get("Key") == "TELEGRAM_PERSONAL_ID": current_tg_personal = str(row.get("Value"))
            
        engine_options = ["AI 사용 안 함", "무료 Gemini", "무료 Groq", "전체"]
        selected_engine = st.selectbox("파이프라인에서 사용할 인공지능을 선택하세요.", engine_options, index=engine_options.index(current_engine) if current_engine in engine_options else 0)
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.subheader("📱 텔레그램 발송 제어")
        st.write("단톡방 전송 여부와 개인 봇 아이디를 설정합니다.")
        
        col_tg1, col_tg2 = st.columns(2)
        with col_tg1:
            tg_group_toggle = st.toggle("📢 단톡방 전송 켜기 (ON/OFF)", value=(current_tg_group == "ON"))
        with col_tg2:
            tg_personal_input = st.text_input("👤 개인 텔레그램 Chat ID", value=current_tg_personal, placeholder="예: 123456789")
        
        if st.button("💾 시스템 설정 모두 저장", type="primary"):
            # 엔진 저장
            try:
                cell_engine = sys_sheet.find("AI_ENGINE")
                sys_sheet.update_cell(cell_engine.row, cell_engine.col + 1, selected_engine)
            except: sys_sheet.append_row(["AI_ENGINE", selected_engine])
            
            # 단톡방 토글 저장
            try:
                cell_group = sys_sheet.find("TELEGRAM_GROUP_SEND")
                sys_sheet.update_cell(cell_group.row, cell_group.col + 1, "ON" if tg_group_toggle else "OFF")
            except: sys_sheet.append_row(["TELEGRAM_GROUP_SEND", "ON" if tg_group_toggle else "OFF"])
            
            # 개인 아이디 저장
            try:
                cell_personal = sys_sheet.find("TELEGRAM_PERSONAL_ID")
                sys_sheet.update_cell(cell_personal.row, cell_personal.col + 1, tg_personal_input)
            except: sys_sheet.append_row(["TELEGRAM_PERSONAL_ID", tg_personal_input])
                
            st.success("시스템 및 텔레그램 설정이 성공적으로 저장되었습니다!")
    except Exception as e: st.error(f"시스템 설정 오류가 발생했습니다. {e}")

    st.markdown("---")
    st.subheader("📜 AI 페르소나 및 평가 기준 (Config_Rubric)")
    try:
        rubric_sheet = spreadsheet.worksheet("Config_Rubric")
        edited_df_rubric = st.data_editor(pd.DataFrame(rubric_sheet.get_all_records()), num_rows="dynamic", use_container_width=True)
        if st.button("💾 평가 기준 저장", type="primary"):
            with st.spinner('저장 중...'):
                rubric_sheet.clear()
                rubric_sheet.update([edited_df_rubric.columns.values.tolist()] + edited_df_rubric.values.tolist())
            st.success("저장 완료!")
    except Exception: st.error("평가 기준 시트를 찾을 수 없습니다.")
