import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import pandas as pd

# 1. 페이지 기본 설정
st.set_page_config(page_title="뉴스 자동화 대시보드", page_icon="📰", layout="wide")

# 2. 구글 시트 연결
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

# 3. 사이드바 메뉴 구성
st.sidebar.title("통합 제어판 ⚙️")
menu = st.sidebar.radio(
    "메뉴를 선택하세요",
    ["📊 종합 상황판", "🔑 키워드 & 매체 제어", "🤖 AI 페르소나 설정", "🚀 파이프라인 제어"]
)

# 4. 메뉴별 화면 구현
if menu == "📊 종합 상황판":
    st.title("📊 뉴스 자동화 종합 상황판")
    st.markdown("---")
    st.subheader("최근 분석 완료된 탑 기사 목록")
    
    try:
        top20_sheet = spreadsheet.worksheet("DB_Top20")
        data = top20_sheet.get_all_records()
        if data:
            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("아직 누적된 데이터가 없습니다.")
    except Exception as e:
        st.warning("DB_Top20 시트를 찾을 수 없습니다. 파이프라인이 한 번 실행된 후 생성됩니다.")

elif menu == "🔑 키워드 & 매체 제어":
    st.title("🔑 키워드 & 매체 가중치 제어")
    st.markdown("---")
    st.info("표의 빈칸을 클릭하여 값을 수정하거나, 맨 아래 행을 클릭해 새로운 항목을 추가할 수 있습니다.")
    
    col1, col2 = st.columns(2)
    
    # [왼쪽 단] 키워드 제어
    with col1:
        st.subheader("📌 키워드 설정 (Config_Keywords)")
        try:
            kw_sheet = spreadsheet.worksheet("Config_Keywords")
            kw_data = kw_sheet.get_all_records()
            df_kw = pd.DataFrame(kw_data)
            
            # 화면에서 직접 표를 수정할 수 있는 에디터 생성
            edited_df_kw = st.data_editor(df_kw, num_rows="dynamic", use_container_width=True, key="kw_editor")
            
            if st.button("💾 키워드 저장", type="primary"):
                with st.spinner('구글 시트에 저장 중...'):
                    kw_sheet.clear()
                    kw_sheet.update([edited_df_kw.columns.values.tolist()] + edited_df_kw.values.tolist())
                st.success("키워드 설정이 성공적으로 저장되었습니다!")
        except Exception as e:
            st.error(f"키워드 시트를 불러오지 못했습니다: {e}")

    # [오른쪽 단] 매체 제어
    with col2:
        st.subheader("📡 타깃 매체 설정 (Config_Media)")
        try:
            try: media_sheet = spreadsheet.worksheet("Config_Media")
            except: media_sheet = spreadsheet.worksheet("Config_Media_Sites")
            
            media_data = media_sheet.get_all_records()
            df_media = pd.DataFrame(media_data)
            
            # 화면에서 직접 표를 수정할 수 있는 에디터 생성
            edited_df_media = st.data_editor(df_media, num_rows="dynamic", use_container_width=True, key="media_editor")
            
            if st.button("💾 매체 저장", type="primary"):
                with st.spinner('구글 시트에 저장 중...'):
                    media_sheet.clear()
                    media_sheet.update([edited_df_media.columns.values.tolist()] + edited_df_media.values.tolist())
                st.success("매체 설정이 성공적으로 저장되었습니다!")
        except Exception as e:
            st.error(f"매체 시트를 불러오지 못했습니다: {e}")

elif menu == "🤖 AI 페르소나 설정":
    st.title("🤖 AI 페르소나 및 평가 기준 설정")
    st.markdown("---")
    st.write("곧 이곳에 텍스트를 바로 수정하고 시트에 반영하는 기능이 추가될 예정입니다.")

elif menu == "🚀 파이프라인 제어":
    st.title("🚀 수동 파이프라인 가동")
    st.markdown("---")
    st.write("곧 이곳에 깃허브 원격 실행 버튼과 진행 상태 모니터링이 추가될 예정입니다.")
