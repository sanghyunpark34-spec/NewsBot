import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import pandas as pd
import requests

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
    
    with col1:
        st.subheader("📌 키워드 설정 (Config_Keywords)")
        try:
            kw_sheet = spreadsheet.worksheet("Config_Keywords")
            kw_data = kw_sheet.get_all_records()
            df_kw = pd.DataFrame(kw_data)
            edited_df_kw = st.data_editor(df_kw, num_rows="dynamic", use_container_width=True, key="kw_editor")
            
            if st.button("💾 키워드 저장", type="primary"):
                with st.spinner('구글 시트에 저장 중...'):
                    kw_sheet.clear()
                    kw_sheet.update([edited_df_kw.columns.values.tolist()] + edited_df_kw.values.tolist())
                st.success("키워드 설정이 성공적으로 저장되었습니다!")
        except Exception as e:
            st.error(f"키워드 시트를 불러오지 못했습니다: {e}")

    with col2:
        st.subheader("📡 타깃 매체 설정 (Config_Media)")
        try:
            try: media_sheet = spreadsheet.worksheet("Config_Media")
            except: media_sheet = spreadsheet.worksheet("Config_Media_Sites")
            
            media_data = media_sheet.get_all_records()
            df_media = pd.DataFrame(media_data)
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
    st.info("💡 1번 행(Base)의 Persona 열을 수정하여 AI의 역할을 변경하거나, 하단 행들의 평가 기준(Criteria)과 배점(Score)을 조정하세요.")
    
    try:
        rubric_sheet = spreadsheet.worksheet("Config_Rubric")
        rubric_data = rubric_sheet.get_all_records()
        df_rubric = pd.DataFrame(rubric_data)
        edited_df_rubric = st.data_editor(df_rubric, num_rows="dynamic", use_container_width=True, key="rubric_editor")
        
        if st.button("💾 페르소나 및 기준 저장", type="primary"):
            with st.spinner('구글 시트에 저장 중...'):
                rubric_sheet.clear()
                rubric_sheet.update([edited_df_rubric.columns.values.tolist()] + edited_df_rubric.values.tolist())
            st.success("AI 설정이 성공적으로 저장되었습니다!")
    except Exception as e:
        st.error(f"Config_Rubric 시트를 불러오지 못했습니다: {e}")

elif menu == "🚀 파이프라인 제어":
    st.title("🚀 수동 파이프라인 가동")
    st.markdown("---")
    st.write("깃허브(GitHub)에 접속하지 않고도, 아래 버튼을 눌러 뉴스 수집 및 분석을 즉시 시작할 수 있습니다.")
    
    # 깃허브 제어를 위한 정보 기입창 생성
    st.subheader("🔗 연동 정보 확인")
    github_repo = st.text_input("깃허브 저장소 주소 (형식: 계정명/저장소명)", placeholder="예: MyName/NewsBot")
    workflow_file = st.text_input("워크플로우 파일명", value="news_pipeline.yml")
    
    if st.button("▶️ 지금 뉴스 파이프라인 가동 시작", type="primary"):
        if not github_repo:
            st.warning("깃허브 저장소 주소를 입력해주세요.")
        elif "GITHUB_TOKEN" not in st.secrets:
            st.error("스트림릿 Secrets 금고에 GITHUB_TOKEN이 등록되어 있지 않습니다.")
        else:
            # 깃허브 API를 사용해 원격으로 Workflow 실행 명령 전송
            token = st.secrets["GITHUB_TOKEN"]
            url = f"https://api.github.com/repos/{github_repo}/actions/workflows/{workflow_file}/dispatches"
            headers = {
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json"
            }
            # 트리거할 타깃 브랜치 지정
            data = {"ref": "main"} 
            
            with st.spinner('깃허브에 원격 기동 명령 송신 중...'):
                response = requests.post(url, headers=headers, json=data)
                
            if response.status_code == 204:
                st.author = True
                st.success(f"🚀 성공! 깃허브 서버에서 뉴스 파이프라인 연산이 즉시 시작되었습니다. 잠시 후 텔레그램을 확인하세요!")
            else:
                st.error(f"가동 실패 (에러 코드: {response.status_code})")
                st.text(response.text)
