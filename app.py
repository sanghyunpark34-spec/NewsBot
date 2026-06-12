import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import pandas as pd
import requests
import time
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

try: spreadsheet = init_connection()
except Exception as e: st.error(f"구글 시트 연결 실패: {e}"); st.stop()

st.sidebar.title("통합 제어판 ⚙️")

# 타이머 HTML
timer_html = """
<div style="background-color: #E8F1FF; padding: 12px; border-radius: 8px; text-align: center; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
    <div style="font-size: 13px; color: #4F8BF9; font-weight: bold; margin-bottom: 4px;">⏱️ 다음 자동 기사 서치까지</div>
    <div id="countdown" style="font-size: 24px; font-weight: 900; color: #1E3A8A;"></div>
</div>
<script>
    function updateTimer() {
        var now = new Date();
        var utc = now.getTime() + (now.getTimezoneOffset() * 60000);
        var kst = new Date(utc + (3600000 * 9));
        var target = new Date(kst);
        target.setHours(15, 17, 0, 0);
        if (kst.getHours() > 15 || (kst.getHours() == 15 && kst.getMinutes() >= 17)) target.setDate(target.getDate() + 1);
        var diff = target - kst;
        document.getElementById("countdown").innerText = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60)) + "시간 " + Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60)) + "분 " + Math.floor((diff % (1000 * 60)) / 1000) + "초";
    }
    setInterval(updateTimer, 1000); updateTimer();
</script>
"""
with st.sidebar: components.html(timer_html, height=90)

# 가동 버튼
st.sidebar.subheader("🚀 퀵 기사 서치 실행")
if st.sidebar.button("▶️ 지금 기사 서치 가동", type="primary", use_container_width=True):
    github_repo = "sanghyunpark34-spec/NewsBot"
    workflow_file = "news_pipeline.yml"
    url = f"https://api.github.com/repos/{github_repo}/actions/workflows/{workflow_file}/dispatches"
    runs_url = f"https://api.github.com/repos/{github_repo}/actions/workflows/{workflow_file}/runs"
    headers = {"Authorization": f"token {st.secrets['GITHUB_TOKEN']}", "Accept": "application/vnd.github.v3+json"}
    
    with st.status("🚀 가동 중...", expanded=True) as status:
        res = requests.post(url, headers=headers, json={"ref": "main"})
        if res.status_code == 204: 
            status.update(label="🔄 작동 중...", state="running")
            time.sleep(5)
            finished = False
            for _ in range(72):
                try:
                    r = requests.get(runs_url, headers=headers).json()
                    if r.get("workflow_runs") and r["workflow_runs"][0]["status"] == "completed":
                        finished = True; break
                except: pass
                time.sleep(5)
            status.update(label="✅ 완료!" if finished else "⏳ 시간이 길어지고 있습니다.", state="complete", expanded=False)
        else: status.update(label=f"❌ 실패 ({res.status_code})", state="error")

st.sidebar.markdown("---")
menu = st.sidebar.radio("세부 메뉴", ["📊 종합 상황판", "🔑 포함/제외 단어 제어", "📡 타깃 매체 제어", "🤖 시스템 및 알림 설정", "📜 AI 페르소나 및 평가 기준"])

# 메뉴 라우팅
if menu == "📊 종합 상황판":
    st.title("📊 기사 서치 종합 상황판")
    try:
        data = spreadsheet.worksheet("DB_Top20").get_all_records()
        if data:
            df = pd.DataFrame(data)
            df_latest = df[df['Execution_Time'] == df['Execution_Time'].max()].drop(columns=['Execution_Time', 'Sent'], errors='ignore')
            st.dataframe(df_latest, use_container_width=True, hide_index=True)
    except: st.warning("데이터 로드 실패")

elif menu == "🔑 포함/제외 단어 제어":
    st.title("🔑 키워드 점수 조절 및 제외 설정")
    # (이하 키워드 로직 동일)
    st.info("키워드 설정 영역")

elif menu == "📡 타깃 매체 제어":
    st.title("📡 타깃 매체 가중치 제어")
    st.info("매체 설정 영역")

elif menu == "🤖 시스템 및 알림 설정":
    st.title("🤖 시스템 및 텔레그램 설정")
    # 시스템 설정 탭 복구
    sys_sheet = spreadsheet.worksheet("Config_System")
    config = {str(r.get("Key")): str(r.get("Value")) for r in sys_sheet.get_all_records()}
    
    col_sys1, col_sys2 = st.columns([1, 1])
    with col_sys1:
        selected_engine = st.selectbox("AI 엔진", ["AI 사용 안 함", "무료 Gemini", "무료 Groq", "전체"], index=0)
    with col_sys2:
        tg_group_toggle = st.toggle("📢 부서
