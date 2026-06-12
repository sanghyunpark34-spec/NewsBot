import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import pandas as pd

# 1. 페이지 기본 설정 (가장 위에 와야 합니다)
st.set_page_config(page_title="뉴스 자동화 대시보드", page_icon="📰", layout="wide")

# 2. 구글 시트 연결 함수 (Streamlit의 캐싱 기능을 사용해 속도 최적화)
@st.cache_resource
def init_connection():
    # Streamlit Cloud의 Secrets에 저장된 환경변수를 불러옵니다.
    creds_dict = json.loads(st.secrets["GOOGLE_SHEETS_CREDENTIALS"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        creds_dict,
        ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    )
    return gspread.authorize(creds).open("News_Management_DB")

# 연결 시도
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
            # 데이터를 보기 좋은 표 형태로 출력합니다.
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("아직 누적된 데이터가 없습니다.")
    except Exception as e:
        st.warning("DB_Top20 시트를 찾을 수 없습니다. 파이프라인이 한 번 실행된 후 생성됩니다.")

elif menu == "🔑 키워드 & 매체 제어":
    st.title("🔑 키워드 & 매체 가중치 제어")
    st.markdown("---")
    st.write("곧 이곳에 직관적인 슬라이더와 제어 버튼이 추가될 예정입니다.")

elif menu == "🤖 AI 페르소나 설정":
    st.title("🤖 AI 페르소나 및 평가 기준 설정")
    st.markdown("---")
    st.write("곧 이곳에 텍스트를 바로 수정하고 시트에 반영하는 기능이 추가될 예정입니다.")

elif menu == "🚀 파이프라인 제어":
    st.title("🚀 수동 파이프라인 가동")
    st.markdown("---")
    st.write("곧 이곳에 깃허브 원격 실행 버튼과 진행 상태 모니터링이 추가될 예정입니다.")
