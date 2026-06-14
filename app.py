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
                    except Exception:
                        pass
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
                
                # 💡 에러 원천 차단: 여러 줄로 확실하게 분리
                if not kw:
                    continue
                    
                c1, c2 = st.columns([3, 1.5])
                with c1: 
                    st.markdown(f"<div style='padding-top: 8px; font-weight: 600; font-size: 16px; color: #1E3A8A;'>{kw}</div>", unsafe_allow_html=True)
                with c2:
                    current_w = float(row.get('Weight', row.get('Coefficient', 1.0)))
                    new_w = st.number_input("점수", min_value=0.0, max_value=10.0, value=current_w, step=1.0, key=f"kw_{idx}", label_visibility="collapsed")
                updated_kws.append([kw, new_w])
                
            st.markdown("---")
            with st.expander("➕ 새로운 타깃 키워드 추가하기"):
                new_kw = st.text_input("새로 추가할 키워드 입력")
                new_w = st.number_input("새 키워드 점수", min_value=0.0, max_value=10.0, value=1.0, step=1.0)
            if st.button("💾 타깃 키워드 모두 저장", type="primary", use_container_width=True):
                if new_kw.strip(): 
                    updated_kws.append([new_kw.strip(), new_w])
                kw_sheet.clear()
                kw_sheet.update([["Keyword", "Weight"]] + updated_kws)
                st.success("타깃 키워드가 성공적으로 저장되었습니다.")
        except Exception as e: 
            st.error(f"키워드 시트 오류: {e}")

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
                
                # 💡 에러 원천 차단: 여러 줄로 확실하게 분리
                if not kw:
                    continue
                    
                c1, c2 = st.columns([3, 1.5])
                with c1: 
                    st.markdown(f"<div style='padding-top: 8px; font-weight: 600; font-size: 16px; color: #991B1B;'>{kw}</div>", unsafe_allow_html=True)
                with c2:
                    current_w = float(row.get('Coefficient', 20.0))
                    new_w = st.number_input("감점", min_value=0.0, max_value=100.0, value=current_w, step=1.0, key=f"neg_{idx}", label_visibility="collapsed")
                updated_negs.append([kw, new_w])
                
            st.markdown("---")
            with st.expander("➕ 새로운 제외 단어 추가하기"):
                new_neg = st.text_input("새로 추가할 제외 단어 입력")
                new_nw = st.number_input("새 단어 감점 폭", min_value=0.0, max_value=100.0, value=20.0, step=1.0)
            if st.button("💾 제외 단어 모두 저장", type="primary", use_container_width=True):
                if new_neg.strip(): 
                    updated_negs.append([new_neg.strip(), new_nw])
                neg_sheet.clear()
                neg_sheet.update([["Keyword", "Coefficient"]] + updated_negs)
                st.success("제외 단어 설정이 성공적으로 저장되었습니다.")
        except Exception as e: 
            st.error(f"제외 키워드 시트 오류: {e}")

# [메뉴 3] 매체 제어
elif menu == "📡 타깃 매체 제어":
    st.title("📡 타깃 매체 가중치 제어")
    st.markdown("---")
    try:
        media_sheet = spreadsheet.worksheet("Config_Media")
        media_data = media_sheet.get_all_records()
        updated_media = []
        for idx, row in enumerate(media_data):
            domain = str(row.get('Domain', '')).strip()
            
            # 💡 에러 원천 차단: 여러 줄로 확실하게 분리
            if not domain:
                continue
                
            c1, c2 = st.columns([3, 1])
            with c1: 
                st.markdown(f"<div style='padding-top: 8px; font-weight: 600; font-size: 16px; color: #065F46;'>{domain}</div>", unsafe_allow_html=True)
            with c2:
                current_w = float(row.get('Weight', row.get('Coefficient', 0.0)))
                new_w = st.number_input("점수", min_value=0.0, max_value=5.0, value=current_w, step=1.0, key=f"media_{idx}", label_visibility="collapsed")
            updated_media.append([domain, new_w])
            
        st.markdown("---")
        with st.expander("➕ 새로운 언론사 도메인 추가하기"):
            new_domain = st.text_input("새 언론사 이름 도메인 입력")
            new_mw = st.number_input("새 언론사 점수", min_value=0.0, max_value=5.0, value=1.0, step=1.0)
        if st.button("💾 언론사 매체 모두 저장", type="primary"):
            if new_domain.strip(): 
                updated_media.append([new_domain.strip(), new_mw])
            media_sheet.clear()
            media_sheet.update([["Domain", "Weight"]] + updated_media)
            st.success("매체 가중치가 성공적으로 저장되었습니다.")
    except Exception as e: 
        st.error(f"매체 시트 오류: {e}")

# [메뉴 4] 시스템 및 알림 설정
elif menu == "🤖 시스템 및 알림 설정":
    st.title("🤖 시스템 및 텔레그램 설정")
    st.markdown("---")
    try:
        try: 
            sys_sheet = spreadsheet.worksheet("Config_System")
        except Exception: 
            sys_sheet = spreadsheet.add_worksheet(title="Config_System", rows="10", cols="2")
            sys_sheet.append_row(["Key", "Value"])
            sys_sheet.append_row(["AI_ENGINE", "AI 사용 안 함"])
        
        config = {str(r.get("Key")): str(r.get("Value")) for r in sys_sheet.get_all_records()}
        current_engine = config.get("AI_ENGINE", "AI 사용 안 함")
        
        col_sys1, col_sys2 = st.columns([1, 1])
        with col_sys1:
            st.subheader("⚙️ 구동할 AI 엔진 선택")
            opts = ["AI 사용 안 함", "무료 Gemini", "무료 Groq", "전체"]
            selected_engine = st.selectbox("엔진 종류", opts, index=opts.index(current_engine) if current_engine in opts else 0, label_visibility="collapsed")
            
        with col_sys2:
            st.subheader("📱 텔레그램 발송 제어")
            st.markdown("<div style='padding: 10px; border: 1px solid #E5E7EB; border-radius: 8px;'>", unsafe_allow_html=True)
            tg_group_toggle = st.toggle("📢 부서 단톡방 전송 허용", value=(config.get("TELEGRAM_GROUP_SEND") == "ON"))
            st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
            tg_author_toggle = st.toggle("👤 작성자 개인 수신 허용", value=(config.get("TELEGRAM_AUTHOR_SEND") == "ON"))
            extra_ids_input = st.text_input("➕ 추가 수신자 ID (쉼표로 구분)", value=config.get("EXTRA_TELEGRAM_IDS", ""), placeholder="예: 1234567, 7654321")
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("💾 시스템 및 알림 설정 모두 저장", type="primary", use_container_width=True):
            def update_setting(key, value):
                try: 
                    cell = sys_sheet.find(key)
                    sys_sheet.update_cell(cell.row, cell.col + 1, value)
                except Exception: 
                    sys_sheet.append_row([key, value])
            update_setting("AI_ENGINE", selected_engine)
            update_setting("TELEGRAM_GROUP_SEND", "ON" if tg_group_toggle else "OFF")
            update_setting("TELEGRAM_AUTHOR_SEND", "ON" if tg_author_toggle else "OFF")
            update_setting("EXTRA_TELEGRAM_IDS", extra_ids_input)
            st.success("설정이 데이터베이스에 성공적으로 기록되었습니다!")
    except Exception as e: 
        st.error(f"오류: {e}")

# [메뉴 5] AI 페르소나 및 평가 기준
elif menu == "📜 AI 페르소나 및 평가 기준":
    st.title("📜 AI 페르소나 및 평가 기준")
    st.markdown("---")
    try:
        rubric_sheet = spreadsheet.worksheet("Config_Rubric")
        edited_df = st.data_editor(pd.DataFrame(rubric_sheet.get_all_records()), num_rows="dynamic", use_container_width=True, height=400)
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("💾 평가 기준 저장", type="primary", use_container_width=True):
            rubric_sheet.clear()
            rubric_sheet.update([edited_df.columns.values.tolist()] + edited_df.values.tolist())
            st.success("저장 완료!")
    except Exception: 
        st.error("Config_Rubric 시트 오류")
