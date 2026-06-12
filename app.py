import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import pandas as pd
import requests

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
    st.error(f"구글 시트 연결에 실패했습니다: {e}")
    st.stop()

st.sidebar.title("통합 제어판 ⚙️")
menu = st.sidebar.radio(
    "메뉴를 선택하세요",
    ["📊 종합 상황판", "🔑 키워드 & 매체 제어", "🤖 AI 및 시스템 설정", "🚀 파이프라인 제어"]
)

if menu == "📊 종합 상황판":
    st.title("📊 뉴스 자동화 종합 상황판")
    st.markdown("---")
    st.subheader("최근 분석 완료된 탑 기사 목록")
    try:
        top20_sheet = spreadsheet.worksheet("DB_Top20")
        data = top20_sheet.get_all_records()
        if data:
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
        else:
            st.info("아직 누적된 데이터가 없습니다.")
    except Exception:
        st.warning("DB_Top20 시트를 찾을 수 없습니다.")

elif menu == "🔑 키워드 & 매체 제어":
    st.title("🔑 키워드 & 매체 가중치 제어")
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📌 타깃 키워드 (Config_Keywords)")
        try:
            kw_sheet = spreadsheet.worksheet("Config_Keywords")
            edited_df_kw = st.data_editor(pd.DataFrame(kw_sheet.get_all_records()), num_rows="dynamic", use_container_width=True)
            if st.button("💾 타깃 키워드 저장", type="primary"):
                with st.spinner('저장 중...'):
                    kw_sheet.clear()
                    kw_sheet.update([edited_df_kw.columns.values.tolist()] + edited_df_kw.values.tolist())
                st.success("저장 완료!")
        except Exception: st.error("키워드 시트를 찾을 수 없습니다.")

        st.subheader("🚫 제외 키워드 (Config_Negative)")
        st.info("여기에 등록된 단어가 기사 제목에 포함되면 즉시 0점 처리됩니다. (예: Keyword 열에 '부동산' 입력)")
        try:
            try: neg_sheet = spreadsheet.worksheet("Config_Negative")
            except: 
                neg_sheet = spreadsheet.add_worksheet(title="Config_Negative", rows="100", cols="2")
                neg_sheet.append_row(["Keyword", "Memo"])
            edited_df_neg = st.data_editor(pd.DataFrame(neg_sheet.get_all_records()), num_rows="dynamic", use_container_width=True)
            if st.button("💾 제외 키워드 저장", type="primary"):
                with st.spinner('저장 중...'):
                    neg_sheet.clear()
                    neg_sheet.update([edited_df_neg.columns.values.tolist()] + edited_df_neg.values.tolist())
                st.success("제외 키워드 저장 완료!")
        except Exception: st.error("제외 키워드 시트 생성 실패.")

    with col2:
        st.subheader("📡 타깃 매체 설정 (Config_Media)")
        try:
            media_sheet = spreadsheet.worksheet("Config_Media")
            edited_df_media = st.data_editor(pd.DataFrame(media_sheet.get_all_records()), num_rows="dynamic", use_container_width=True)
            if st.button("💾 매체 저장", type="primary"):
                with st.spinner('저장 중...'):
                    media_sheet.clear()
                    media_sheet.update([edited_df_media.columns.values.tolist()] + edited_df_media.values.tolist())
                st.success("저장 완료!")
        except Exception: st.error("매체 시트를 찾을 수 없습니다.")

elif menu == "🤖 AI 및 시스템 설정":
    st.title("🤖 AI 엔진 및 페르소나 설정")
    st.markdown("---")
    
    st.subheader("⚙️ 구동할 AI 엔진 선택")
    try:
        try: sys_sheet = spreadsheet.worksheet("Config_System")
        except:
            sys_sheet = spreadsheet.add_worksheet(title="Config_System", rows="10", cols="2")
            sys_sheet.append_row(["Key", "Value"])
            sys_sheet.append_row(["AI_ENGINE", "AI 사용 안 함"])
            
        sys_data = sys_sheet.get_all_records()
        current_engine = "AI 사용 안 함"
        for row in sys_data:
            if row.get("Key") == "AI_ENGINE": current_engine = row.get("Value")
            
        engine_options = ["AI 사용 안 함", "무료 Gemini", "무료 Groq", "유료 Claude (예정)"]
        selected_engine = st.selectbox("파이프라인에서 사용할 인공지능을 선택하세요.", engine_options, index=engine_options.index(current_engine) if current_engine in engine_options else 0)
        
        if st.button("💾 엔진 설정 저장", type="primary"):
            cell = sys_sheet.find("AI_ENGINE")
            sys_sheet.update_cell(cell.row, cell.col + 1, selected_engine)
            st.success(f"[{selected_engine}] 모드로 성공적으로 전환되었습니다.")
    except Exception as e: st.error(f"시스템 설정 오류: {e}")

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

elif menu == "🚀 파이프라인 제어":
    st.title("🚀 수동 파이프라인 가동")
    st.markdown("---")
    github_repo = st.text_input("깃허브 저장소 주소", placeholder="예: MyName/NewsBot")
    workflow_file = st.text_input("워크플로우 파일명", value="news_pipeline.yml")
    
    if st.button("▶️ 지금 파이프라인 가동", type="primary"):
        if not github_repo or "GITHUB_TOKEN" not in st.secrets:
            st.error("저장소 주소 또는 깃허브 토큰이 누락되었습니다.")
        else:
            url = f"https://api.github.com/repos/{github_repo}/actions/workflows/{workflow_file}/dispatches"
            headers = {"Authorization": f"token {st.secrets['GITHUB_TOKEN']}", "Accept": "application/vnd.github.v3+json"}
            res = requests.post(url, headers=headers, json={"ref": "main"})
            if res.status_code == 204: st.success("🚀 파이프라인 연산이 시작되었습니다!")
            else: st.error("가동 실패를 확인해주세요.")
