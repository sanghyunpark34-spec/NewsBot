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
        # 문자열로 된 날짜를 datetime 객체로 변환하여 가장 최신 타임스탬프를 찾습니다.
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

# f-string 문자열이므로 내부 자바스크립트 중괄호 {}는 {{}}로 이중 처리합니다.
timer_html = f"""
<div style="background-color: #E8F1FF; padding: 12px; border-radius: 8px; text-align: center; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
    <div style="font-size: 13px; color: #4F8BF9; font-weight: bold; margin-bottom: 4px;">⏱️ 다음 자동 기사 서치(오전 7시 48분)까지</div>
    <div id="countdown" style="font-size: 24px; font-weight: 900; color: #1E3A8A; letter-spacing: 1px;"></div>
    <hr style="margin: 8px 0; border: 0; border-top: 0.5px solid #C6D8FF;">
    <div style="font-size: 11px; color: #6B7280; margin-bottom: 2px;">🟢 가장 최근 수집된 기사 발행일</div>
    <div style="font-size: 13px; font-weight: bold; color: #374151;">{latest_article_str} <span style="color:#EF4444; font-size:11px; font-weight:600;">{time_diff_str}</span></div>
</div>
<script>
    function updateTimer() {{
        var now = new Date();
        var utc = now.getTime() + (now.getTimezoneOffset() * 60000);
        var kst = new Date(utc + (3600000 * 9));
        var target = new Date(kst);
        target.setHours(7, 48, 0, 0);
        if (kst.getHours() > 7 || (kst.getHours() == 7 && kst.getMinutes() >= 48))
