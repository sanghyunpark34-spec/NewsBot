import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import pandas as pd
import requests
import time
import streamlit.components.v1 as components

# 1. 페이지 기본 설정
st.set_page_config(page_title="뉴스 자동화 대시보드", page_icon="📰", layout="wide")

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

timer_html = """
<div style="background-color: #E8F1FF; padding: 12px; border-radius: 8px; text-align: center; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
    <div style="font-size: 13px; color: #4F8BF9; font-weight: bold; margin-bottom: 4px;">⏱️ 다음 자동 기사 서치(오후 3시 17분)까지</div>
    <div id="countdown" style="font-size: 24px; font-weight: 900; color: #1E3A8A; letter-spacing: 1px;"></div>
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
    components.html(timer_html, height=90)

# 4. 퀵 기사 서치 실행 버튼 (실시간 상태 연동)
st.sidebar.subheader("🚀 퀵 기사 서치 실행")
if st.sidebar.button("▶️ 지금 기사 서치 가동", type="primary", use_container_width=True):
    github_repo = "sanghyunpark34-spec/NewsBot"
    workflow_file = "news_pipeline.yml"
    
    if "GITHUB_TOKEN" not in st.secrets:
        st
