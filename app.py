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
        date_objects = []
        for d in archive_dates:
            if d.strip():
                date_objects.append(datetime.strptime(d.strip(), "%Y-%m-%d %H:%M:%S"))
                
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
except Exception as e:
    pass

timer_html = """
<div style="background-color: #E8F1FF; padding: 12px; border-radius: 8px; text-align: center; margin-bottom: 10
