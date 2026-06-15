import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
import pytz

st.set_page_config(page_title="뉴스 자동화 대시보드", page_icon="📰", layout="wide")

KST = pytz.timezone('Asia/Seoul')

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

st.sidebar.title("통합 제어판 ⚙️")

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
except Exception:
    pass

st.sidebar.markdown(
    f"""
    <div style="background-color: #E8F1FF; padding: 14px; border-radius: 8px; text-align: center; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
        <div style="font-size: 11px; color: #6B7280; margin-bottom: 3px;">🟢 가장 최근 보관된 뉴스 발행일</div>
        <div style="font-size: 14px; font-weight: bold; color: #374151;">{latest_article_str} <span style="color:#EF4444; font-size:12px; font-weight:600;">{time_diff_str}</span></div>
    </div>
    """,
    unsafe_allow_html=True
)

st.sidebar.subheader("🚀 파이프라인 제어")
github_repo = "sanghyunpark34-spec/NewsBot"
workflow_file = "news_pipeline.yml"
headers = {"Authorization": f"token {st.secrets.get('GITHUB_TOKEN', '')}", "Accept": "application/vnd.github.v3+json"}
url = f"https://api.github.com/repos/{github_repo}/actions/workflows/{workflow_file}/dispatches"
runs_url = f"https://api.github.com/repos/{github_repo}/actions/workflows/{workflow_file}/runs"

# [버튼 1] 전체 가동
if st.sidebar.button("▶️ 지금 기사 서치 가동", type="primary", use_container_width=True):
    if "GITHUB_TOKEN" not in st.secrets:
        st.sidebar.error("스트림릿 비밀 금고에 깃허브 토큰이 없습니다.")
    else:
        with st.status("🚀 깃허브 서버 가동 준비 중입니다.", expanded=True) as status:
            res = requests.post(url, headers=headers, json={"ref": "main", "inputs": {"run_type": "full"}})
            if res.status_code == 204: 
                status.update(label="🔄 현재 신규 기사 분석 파이프라인이 작동 중입니다.", state="running")
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
                    status.update(label="✅ 작동이 완료되었습니다. 텔레그램을 확인해주세요.", state="complete", expanded=False)
                    st.rerun()
                else:
                    status.update(label="⏳ 분석량이 많아 지연되고 있습니다. 곧 전송됩니다.", state="complete", expanded=False)
            else: 
                status.update(label=f"❌ 가동에 실패했습니다. 에러 코드는 {res.status_code} 입니다.", state="error")

# [버튼 2] 재채점
if st.sidebar.button("🔄 최근 기사 바뀐 룰로 재채점하기", use_container_width=True):
    if "GITHUB_TOKEN" not in st.secrets:
        st.sidebar.error("스트림릿 비밀 금고에 깃허브 토큰이 없습니다.")
    else:
        with st.status("🔄 기준 변경에 따른 데이터 재배치 및 재채점을 준비 중입니다.", expanded=True) as status:
            try:
                now_kst = datetime.now(KST)
                lookback_days = 3.5 if now_kst.weekday() in [0, 5, 6] else 1.5
                cutoff_date = now_kst - timedelta(days=lookback_days)
                
                archive_sheet = spreadsheet.worksheet("DB_Archive")
                archive_rows = archive_sheet.get_all_values()
                
                keep_rows = [archive_rows[0]]
                reprocess_rows = []
                
                for row in archive_rows[1:]:
                    if len(row) < 3: 
                        continue
                    try:
                        pub_date = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
                        if pub_date >= cutoff_date.replace(tzinfo=None):
                            reprocess_rows.append(row)
                        else:
                            keep_rows.append(row)
                    except Exception:
                        keep_rows.append(row)
                
                if reprocess_rows:
                    st.write(f"📊 최근 설정된 기간 기준 대상 기사 {len(reprocess_rows)}개를 대기실로 이동합니다.")
                    archive_sheet.clear()
                    archive_sheet.update(keep_rows)
                    
                    inbox_sheet = spreadsheet.worksheet("DB_Inbox")
                    inbox_to_append = []
                    for r in reprocess_rows:
                        inbox_to_append.append([r[0], r[1], r[2]])
                    
                    if inbox_to_append:
                        inbox_sheet.append_rows(inbox_to_append)
                    
                    st.write("🚀 기사 수집을 건너뛰고 변경된 배점 방식으로 초고속 재채점을 시작합니다.")
                    res = requests.post(url, headers=headers, json={"ref": "main", "inputs": {"run_type": "score_only"}})
                    
                    if res.status_code == 204:
                        status.update(label="🔄 변경된 룰로 기사 재채점 분석이 작동 중입니다.", state="running")
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
                            status.update(label="✅ 새로운 룰로 재채점 및 리포트 발송이 완료되었습니다.", state="complete", expanded=False)
                            st.rerun()
                        else:
                            status.update(label="⏳ 재채점 분석이 길어지고 있습니다. 잠시 후 완료됩니다.", state="complete", expanded=False)
                    else:
                        status.update(label=f"❌ 원격 서버 가동에 실패했습니다. 에러 코드는 {res.status_code} 입니다.", state="error")
                else:
                    status.update(label="⚠️ 재채점 범위 내에 보관된 기사가 존재하지 않습니다.", state="complete", expanded=False)
            except Exception as e:
                status.update(label=f"❌ 오류가 발생했습니다. 내용은 {e} 입니다.", state="error")

# [버튼 3] 미발송 리포트 즉시 발송
if st.sidebar.button("📤 AI 평가 완료 기사 즉시 발송", use_container_width=True):
    if "GITHUB_TOKEN" not in st.secrets:
        st.sidebar.error("스트림릿 비밀 금고에 깃허브 토큰이 없습니다.")
    else:
        with st.status("📤 텔레그램 발송 서버를 호출 중입니다...", expanded=True) as status:
            res = requests.post(url, headers=headers, json={"ref": "main", "inputs": {"run_type": "report_only"}})
            if res.status_code == 204:
                status.update(label="🚀 발송 대기 중인 AI 평가 리포트를 전송하고 있습니다.", state="running")
                time.sleep(5)
                finished = False
                for _ in range(24): 
                    try:
                        r = requests.get(runs_url, headers=headers).json()
                        runs = r.get("workflow_runs", [])
                        if runs and runs[0]["status"] == "completed":
                            finished = True
                            break
                    except Exception: pass
                    time.sleep(5)
                if finished:
                    status.update(label="✅ 텔레그램 리포트 발송이 완료되었습니다!", state="complete", expanded=False)
                else:
                    status.update(label="⏳ 발송이 길어지고 있습니다. 잠시 후 텔레그램을 확인해주세요.", state="complete", expanded=False)
            else:
                status.update(label=f"❌ 서버 호출에 실패했습니다. 에러 코드는 {res.status_code} 입니다.", state="error")

st.sidebar.markdown("---")

# 💡 메뉴 구조 개편 및 통합 완료
menu = st.sidebar.radio(
    "세부 메뉴를 선택하세요",
    ["📊 종합 상황판", "🔑 포함/제외 단어 제어", "📡 타깃 매체 제어", "📱 알림 및 수신처 설정", "🤖 AI 통합 설정", "🎯 Project B: 피드백 수집판"]
)

if menu == "📊 종합 상황판":
    st.title("📊 기사 서치 종합 상황판")
    st.markdown("---")
    st.markdown("#### 최근 AI 평가가 완료된 기사 목록")
    try:
        ai_report_sheet = spreadsheet.worksheet("DB_AI_Report")
        data = ai_report_sheet.get_all_records()
        if data:
            df = pd.DataFrame(data)
            latest_time = df['Execution_Time'].max()
            df_latest = df[df['Execution_Time'] == latest_time].drop(columns=['Execution_Time', 'Sent'], errors='ignore')
            st.dataframe(df_latest, use_container_width=True, hide_index=True, height=750)
        else:
            st.info("아직 누적된 AI 평가 데이터가 없습니다.")
    except Exception:
        st.warning("DB_AI_Report 시트를 찾을 수 없습니다. 시트 이름이 올바른지 확인해주세요.")

elif menu == "🔑 포함/제외 단어 제어":
    st.title("🔑 키워드 점수 조절 및 제외 설정")
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📌 타깃 키워드 점수 설정 (최대 10)")
        try:
            kw_sheet = spreadsheet.worksheet("Config_Keywords")
            kw_data = kw_sheet.get_all_records()
            updated_kws = []
            for idx, row in enumerate(kw_data):
                kw = str(row.get('Keyword', '')).strip()
                if not kw:
                    continue
                c1, c2 = st.columns([3, 1.5])
                with c1: 
                    st.markdown(f"<div style='padding-top: 8px; font-weight: 600; font-size: 16px; color: #1E3A8A;'>{kw}</div>", unsafe_allow_html=True)
                with c2:
                    current_w = float(row.get('Score', row.get('Weight', 1.0)))
                    new_w = st.number_input("점수 입력", min_value=0.0, max_value=10.0, value=current_w, step=1.0, key=f"kw_{idx}", label_visibility="collapsed")
                updated_kws.append([kw, new_w])
                
            st.markdown("---")
            with st.expander("➕ 새로운 타깃 키워드 추가하기"):
                new_kw = st.text_input("새로 추가할 키워드를 입력하세요.")
                new_w = st.number_input("새 키워드 점수를 입력하세요.", min_value=0.0, max_value=10.0, value=1.0, step=1.0)
            if st.button("💾 타깃 키워드 모두 저장", type="primary", use_container_width=True):
                if new_kw.strip(): 
                    updated_kws.append([new_kw.strip(), new_w])
                kw_sheet.clear()
                kw_sheet.update([["Keyword", "Score"]] + updated_kws)
                st.success("타깃 키워드가 성공적으로 저장되었습니다.")
        except Exception as e: 
            st.error(f"키워드 시트 오류가 발생했습니다. 내용은 {e} 입니다.")

    with col2:
        st.subheader("🚫 제외 단어 감점 설정")
        try:
            try: 
                neg_sheet = spreadsheet.worksheet("Config_Negative")
            except Exception: 
                neg_sheet = spreadsheet.add_worksheet(title="Config_Negative", rows="100", cols="2")
                neg_sheet.append_row(["Keyword", "Coefficient"])
                
            neg_data = neg_sheet.get_all_records()
            updated_negs = []
            for idx, row in enumerate(neg_data):
                kw = str(row.get('Keyword', '')).strip()
                if not kw:
                    continue
                c1, c2 = st.columns([3, 1.5])
                with c1: 
                    st.markdown(f"<div style='padding-top: 8px; font-weight: 600; font-size: 16px; color: #991B1B;'>{kw}</div>", unsafe_allow_html=True)
                with c2:
                    current_w = float(row.get('Coefficient', 20.0))
                    new_w = st.number_input("감점 폭 입력", min_value=0.0, max_value=100.0, value=current_w, step=1.0, key=f"neg_{idx}", label_visibility="collapsed")
                updated_negs.append([kw, new_w])
                
            st.markdown("---")
            with st.expander("➕ 새로운 제외 단어 추가하기"):
                new_neg = st.text_input("새로 추가할 제외 단어를 입력하세요.")
                new_nw = st.number_input("새 단어 감점 폭을 입력하세요.", min_value=0.0, max_value=100.0, value=20.0, step=1.0)
            if st.button("💾 제외 단어 모두 저장", type="primary", use_container_width=True):
                if new_neg.strip(): 
                    updated_negs.append([new_neg.strip(), new_nw])
                neg_sheet.clear()
                neg_sheet.update([["Keyword", "Coefficient"]] + updated_negs)
                st.success("제외 단어 설정이 성공적으로 저장되었습니다.")
        except Exception as e: 
            st.error(f"제외 키워드 시트 오류가 발생했습니다. 내용은 {e} 입니다.")

elif menu == "📡 타깃 매체 제어":
    st.title("📡 타깃 매체 가중치 제어")
    st.markdown("---")
    try:
        media_sheet = spreadsheet.worksheet("Config_Media")
        media_data = media_sheet.get_all_records()
        updated_media = []
        for idx, row in enumerate(media_data):
            domain = str(row.get('Domain', '')).strip()
            if not domain:
                continue
            c1, c2 = st.columns([3, 1])
            with c1: 
                st.markdown(f"<div style='padding-top: 8px; font-weight: 600; font-size: 16px; color: #065F46;'>{domain}</div>", unsafe_allow_html=True)
            with c2:
                current_w = float(row.get('Weight', row.get('Coefficient', 0.0)))
                new_w = st.number_input("점수 입력", min_value=0.0, max_value=5.0, value=current_w, step=1.0, key=f"media_{idx}", label_visibility="collapsed")
            updated_media.append([domain, new_w])
            
        st.markdown("---")
        with st.expander("➕ 새로운 언론사 도메인 추가하기"):
            new_domain = st.text_input("새 언론사 이름 도메인을 입력하세요.")
            new_mw = st.number_input("새 언론사 점수를 입력하세요.", min_value=0.0, max_value=5.0, value=1.0, step=1.0)
        if st.button("💾 언론사 매체 모두 저장", type="primary"):
            if new_domain.strip(): 
                updated_media.append([new_domain.strip(), new_mw])
            media_sheet.clear()
            media_sheet.update([["Domain", "Weight"]] + updated_media)
            st.success("매체 가중치가 성공적으로 저장되었습니다.")
    except Exception as e: 
        st.error(f"매체 시트 오류가 발생했습니다. 내용은 {e} 입니다.")

# 💡 [명칭 개편 완료] 알림 및 수신처만 단독 분리
elif menu == "📱 알림 및 수신처 설정":
    st.title("📱 알림 및 수신처 제어 센터")
    st.markdown("---")
    try:
        sys_sheet = spreadsheet.worksheet("Config_System")
        config = {str(r.get("Key")): str(r.get("Value")) for r in sys_sheet.get_all_records()}
        
        st.subheader("📱 텔레그램 발송 제어")
        st.markdown("<div style='padding: 15px; border: 1px solid #E5E7EB; border-radius: 8px; background-color: #F9FAFB;'>", unsafe_allow_html=True)
        tg_group_toggle = st.toggle("📢 부서 단톡방 전송 허용", value=(config.get("TELEGRAM_GROUP_SEND") == "ON"))
        st.markdown("<hr style='margin: 15px 0;'>", unsafe_allow_html=True)
        tg_author_toggle = st.toggle("👤 작성자 개인 수신 허용", value=(config.get("TELEGRAM_AUTHOR_SEND") == "ON"))
        extra_ids_input = st.text_input("➕ 추가 수신자 아이디를 쉼표로 구분하여 입력하세요.", value=config.get("EXTRA_TELEGRAM_IDS", ""), placeholder="1234567, 7654321 처럼 입력하세요.")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("💾 알림 및 수신처 설정 저장", type="primary", use_container_width=True):
            def update_setting(key, value):
                try: 
                    cell = sys_sheet.find(key)
                    sys_sheet.update_cell(cell.row, cell.col + 1, value)
                except Exception: 
                    sys_sheet.append_row([key, value])
            update_setting("TELEGRAM_GROUP_SEND", "ON" if tg_group_toggle else "OFF")
            update_setting("TELEGRAM_AUTHOR_SEND", "ON" if tg_author_toggle else "OFF")
            update_setting("EXTRA_TELEGRAM_IDS", extra_ids_input)
            st.success("수신처 설정이 데이터베이스에 기록되었습니다.")
    except Exception as e: 
        st.error(f"오류가 발생했습니다: {e}")

# 💡 [신규 메뉴 통합] 모든 AI 엔진, 대기시간, 점수 가중치, 프롬프트, 루브릭을 통합 제어
elif menu == "🤖 AI 통합 설정":
    st.title("🤖 AI 엔진 및 평가 매커니즘 통합 설정")
    st.markdown("---")
    try:
        sys_sheet = spreadsheet.worksheet("Config_System")
        config = {str(r.get("Key")): str(r.get("Value")) for r in sys_sheet.get_all_records()}
        
        current_engine = config.get("AI_ENGINE", "유료 Claude")
        current_persona = config.get("ACTIVE_PERSONA", "옵션 1 (기본 금융 전문가)")
        current_delay = int(config.get("AI_DELAY_SECONDS", 5))
        # 💡 신규 가중치 파라미터 로드 (기본값 55%)
        current_ai_weight = int(config.get("AI_WEIGHT_PERCENT", 55))
        
        col_sys1, col_sys2 = st.columns([1, 1])
        with col_sys1:
            st.subheader("⚙️ AI 구동 코어 설정")
            st.markdown("<div style='padding: 15px; border: 1px solid #E5E7EB; border-radius: 8px; background-color: #F9FAFB;'>", unsafe_allow_html=True)
            opts_engine = ["AI 사용 안 함", "무료 Gemini", "무료 Groq", "유료 Claude", "전체"]
            selected_engine = st.selectbox("엔진 종류를 선택하세요.", opts_engine, index=opts_engine.index(current_engine) if current_engine in opts_engine else 3)
            
            opts_persona = ["옵션 1 (기본 금융 전문가)", "옵션 2 (신규 커스텀)"]
            selected_persona = st.selectbox("적용할 AI 페르소나를 선택하세요.", opts_persona, index=opts_persona.index(current_persona) if current_persona in
