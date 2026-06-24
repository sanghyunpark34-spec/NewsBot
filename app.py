import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
import pytz
import holidays

st.set_page_config(page_title="뉴스 자동화 대시보드", page_icon="📰", layout="wide")

KST = pytz.timezone('Asia/Seoul')

# 💡 사장님의 실제 구글 스프레드시트 링크 적용 완료!
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1Q7Qc3HBnuSxUs5FOlS0uCnSqny5usLVbPig6Go8wIPo/edit?gid=2079355572#gid=2079355572"

# ==========================================
# 🛠️ 1. 핵심 공통 시스템 함수 (리팩토링 구역)
# ==========================================

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
    st.error(f"구글 시트 연결에 실패했습니다. 발생한 오류는 {e} 입니다.")
    st.stop()

def get_previous_working_day_cutoff(current_time):
    """현재 시간 기준으로 1영업일 전의 커트라인 시간을 계산합니다."""
    kr_holidays = holidays.KR()
    days_to_subtract = 1
    while True:
        target_date = current_time - timedelta(days=days_to_subtract)
        if target_date.weekday() < 5 and target_date.date() not in kr_holidays:
            return target_date
        days_to_subtract += 1

def get_hot_articles(spreadsheet):
    """E를 제외하고, 1영업일 이내의 Y(발송완료)와 N(대기중) 기사를 점수순으로 정렬하여 반환합니다."""
    try:
        ai_report_sheet = spreadsheet.worksheet("DB_AI_Report")
        data = ai_report_sheet.get_all_records()
        if not data:
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        df['Total_Score'] = pd.to_numeric(df['Total_Score'], errors='coerce').fillna(0)
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        
        now = datetime.now(KST)
        cutoff_time = get_previous_working_day_cutoff(now).replace(tzinfo=None)
        
        df = df[df['Sent'] != 'E']
        df = df[df['Date'] >= cutoff_time]
        df = df.sort_values(by='Total_Score', ascending=False).reset_index(drop=True)
        
        return df.head(40)
    except Exception as e:
        st.warning(f"데이터를 불러오는 중 오류가 발생했습니다. 발생한 오류는 {e} 입니다.")
        return pd.DataFrame()

def trigger_github_workflow(run_type, init_msg, running_msg, success_msg):
    """길고 복잡한 깃허브 API 호출 코드를 하나로 압축한 공통 함수입니다."""
    if "GITHUB_TOKEN" not in st.secrets:
        st.sidebar.error("스트림릿 비밀 금고에 깃허브 토큰이 없습니다.")
        return
        
    github_repo = "sanghyunpark34-spec/NewsBot"
    workflow_file = "news_pipeline.yml"
    headers = {"Authorization": f"token {st.secrets.get('GITHUB_TOKEN', '')}", "Accept": "application/vnd.github.v3+json"}
    url = f"https://api.github.com/repos/{github_repo}/actions/workflows/{workflow_file}/dispatches"
    runs_url = f"https://api.github.com/repos/{github_repo}/actions/workflows/{workflow_file}/runs"
    
    with st.status(init_msg, expanded=True) as status:
        res = requests.post(url, headers=headers, json={"ref": "main", "inputs": {"run_type": run_type}})
        if res.status_code == 204: 
            status.update(label=running_msg, state="running")
            time.sleep(5)
            finished = False
            for _ in range(72):
                try:
                    r = requests.get(runs_url, headers=headers).json()
                    runs = r.get("workflow_runs", [])
                    if runs and runs[0]["status"] == "completed":
                        finished = True
                        break
                except Exception: pass
                time.sleep(5)
            if finished:
                status.update(label=success_msg, state="complete", expanded=False)
                st.rerun()
            else:
                status.update(label="⏳ 작업량이 많아 지연되고 있습니다. 곧 완료됩니다.", state="complete", expanded=False)
        else: 
            status.update(label=f"❌ 서버 호출에 실패했습니다. 에러 코드는 {res.status_code} 입니다.", state="error")


# ==========================================
# 🖥️ 2. 사이드
