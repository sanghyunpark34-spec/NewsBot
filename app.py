import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import pandas as pd
import requests
import time
from datetime import datetime
import pytz
import streamlit.components.v1 as components

# 1. 페이지 기본 설정
st.set_page_config(page_title="뉴스 자동화 대시보드", page_icon="📰", layout="wide")

KST = pytz.timezone('Asia/Seoul')

# 2. 데이터베이스 연결
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
    st.error(f"구글 시트 연결에 실패했습니다. 발생한 오류: {e}")
    st.stop()

# 3. 사이드바 및 타이머 UI
st.sidebar.title("통합 제어판 ⚙️")

# 💡 [데이터 신선도] DB_Archive 시트에서 가장 최신 기사의 발행 시점과 경과 시간 계산
latest_article_str = "수집된 기사 없음"
time_diff_str = ""
try:
    archive_dates = spreadsheet.worksheet("DB_Archive").col_values(1)[1:]
    if archive_dates:
        date_objects = [datetime.strptime(d.strip(), "%Y-%m-%d %H:%M:%S") for d in archive_dates if d.strip()]
        if date_objects:
            latest_date_obj = max(date_objects)
            now_kst_naive = datetime.now(KST).replace(tzinfo=None)
            diff = now_kst_naive - latest_date_obj
            diff_hours = int(diff.total_seconds() // 3600)
            diff_mins = int((diff.total_seconds() % 3600) // 60)
            
            latest_article_str = latest_date_obj.strftime("%y.%m.%d %H:%M")
            if diff_hours == 0:
                time_diff_str = f"({diff_mins}분 전)"
            else:
                time_diff_str = f"({diff_hours}시간 {diff_mins}분 전)"
except:
    pass

# f-string을 제거하고 replace로 변수를 넣어주어 에러를 원천 차단합니다.
timer_html = """
<div style="background-color: #E8F1FF; padding: 12px; border-radius: 8px; text-align: center; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
    <div style="font-size: 13px; color: #4F8BF9; font-weight: bold; margin-bottom: 4px;">⏱️ 다음 자동 기사 서치(오전 7시 48분)까지</div>
    <div id="countdown" style="font-size: 24px; font-weight: 900; color: #1E3A8A; letter-spacing: 1px;"></div>
    <hr style="margin: 8px 0; border: 0; border-top: 0.5px solid #C6D8FF;">
    <div style="font-size: 11px; color: #6B7280; margin-bottom: 2px;">🟢 가장 최근 수집된 기사 발행일</div>
    <div style="font-size: 13px; font-weight: bold; color: #374151;">VAR_LATEST <span style="color:#EF4444; font-size:11px; font-weight:600;">VAR_DIFF</span></div>
</div>
<script>
    function updateTimer() {
        var now = new Date();
        var utc = now.getTime() + (now.getTimezoneOffset() * 60000);
        var kst = new Date(utc + (3600000 * 9));
        var target = new Date(kst);
        target.setHours(7, 48, 0, 0);
        if (kst.getHours() > 7 || (kst.getHours() == 7 && kst.getMinutes() >= 48)) {
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
""".replace("VAR_LATEST", latest_article_str).replace("VAR_DIFF", time_diff_str)

with st.sidebar:
    components.html(timer_html, height=145)

# 4. 퀵 기사 서치 실행 버튼 (실시간 상태 연동)
st.sidebar.subheader("🚀 퀵 기사 서치 실행")
if st.sidebar.button("▶️ 지금 기사 서치 가동", type="primary", use_container_width=True):
    github_repo = "sanghyunpark34-spec/NewsBot"
    workflow_file = "news_pipeline.yml"
    
    if "GITHUB_TOKEN" not in st.secrets:
        st.sidebar.error("스트림릿 Secrets 금고에 깃허브 토큰이 없습니다.")
    else:
        url = f"https://api.github.com/repos/{github_repo}/actions/workflows/{workflow_file}/dispatches"
        runs_url = f"https://api.github.com/repos/{github_repo}/actions/workflows/{workflow_file}/runs"
        headers = {"Authorization": f"token {st.secrets['GITHUB_TOKEN']}", "Accept": "application/vnd.github.v3+json"}
        
        with st.status("🚀 깃허브 서버 가동 준비 중...", expanded=True) as status:
            st.write("명령을 전송하는 중입니다...")
            res = requests.post(url, headers=headers, json={"ref": "main"})
            
            if res.status_code == 204: 
                status.update(label="🔄 현재 프로그램이 작동 중입니다...", state="running")
                st.write("✅ 깃허브 연결 성공! AI 평가가 완료될 때까지 대기합니다 (최대 6분).")
                time.sleep(5)
                finished = False
                for _ in range(72):
                    try:
                        r = requests.get(runs_url, headers=headers).json()
                        runs = r.get("workflow_runs", [])
                        if runs and runs[0]["status"] == "completed":
                            finished = True
                            break
                    except: pass
                    time.sleep(5)
                    
                if finished:
                    status.update(label="✅ 작동이 완전히 종료되었습니다! 텔레그램을 확인해주세요.", state="complete", expanded=False)
                else:
                    status.update(label="⏳ 분석량이 많아 지연되고 있습니다. 곧 전송됩니다.", state="complete", expanded=False)
            else: 
                status.update(label=f"❌ 가동 실패 (에러 코드: {res.status_code})", state="error")

st.sidebar.markdown("---")

# 5. 메인 화면 메뉴 라우팅
menu = st.sidebar.radio(
    "세부 메뉴를 선택하세요",
    ["📊 종합 상황판", "🔑 포함/제외 단어 제어", "📡 타깃 매체 제어", "🤖 시스템 및 알림 설정", "📜 AI 페르소나 및 평가 기준"]
)

# [메뉴 1] 종합 상황판
if menu == "📊 종합 상황판":
    st.title("📊 기사 서치 종합 상황판")
    st.markdown("---")
    st.markdown("#### 최근 분석 완료된 탑 20 기사 목록")
    try:
        top20_sheet = spreadsheet.worksheet("DB_Top20")
        data = top20_sheet.get_all_records()
        if data:
            df = pd.DataFrame(data)
            latest_time = df['Execution_Time'].max()
            df_latest = df[df['Execution_Time'] == latest_time].drop(columns=['Execution_Time', 'Sent'], errors='ignore')
            st.dataframe(df_latest, use_container_width=True, hide_index=True, height=750)
        else:
            st.info("아직 누적된 데이터가 없습니다.")
    except Exception:
        st.warning("DB_Top20 시트를 찾을 수 없습니다.")

# [메뉴 2] 키워드 제어
elif menu == "🔑 포함/제외 단어 제어":
    st.title("🔑 키워드 점수 조절 및 제외 설정")
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📌 타깃 키워드 점수 설정 (Max 10)")
        try:
            kw_sheet = spreadsheet.worksheet("Config_Keywords")
            kw_data = kw_sheet.get_all_records()
            updated_kws = []
            for idx, row in enumerate(kw_data):
                kw = str(row.get('Keyword', '')).strip()
                if not kw
