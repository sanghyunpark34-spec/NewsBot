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
        
        # 커트라인 계산 (판다스 datetime과 비교하기 위해 타임존 제거)
        now = datetime.now(KST)
        cutoff_time = get_previous_working_day_cutoff(now).replace(tzinfo=None)
        
        # 💡 핵심 필터링 3단계
        # 1. 만료(E) 기사 완전 제외
        df = df[df['Sent'] != 'E']
        # 2. 발행일이 1영업일(24시간) 이내인 신선한 기사만 생존 (시간 변색 방지)
        df = df[df['Date'] >= cutoff_time]
        # 3. 오직 총점 내림차순 정렬
        df = df.sort_values(by='Total_Score', ascending=False).reset_index(drop=True)
        
        # 대시보드용으로 넉넉하게 상위 40개 노출
        return df.head(40)
    except Exception as e:
        st.warning(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
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
            status.update(label=f"❌ 서버 호출에 실패했습니다. 에러 코드: {res.status_code}", state="error")


# ==========================================
# 🖥️ 2. 사이드바 제어 패널 (압축됨)
# ==========================================
st.sidebar.title("통합 제어판 ⚙️")

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
            diff_hours, diff_mins = int(diff.total_seconds() // 3600), int((diff.total_seconds() % 3600) // 60)
            
            latest_article_str = latest_date_obj.strftime("%y.%m.%d %H:%M")
            time_diff_str = f"({diff_mins}분 전)" if diff_hours == 0 else f"({diff_hours}시간 {diff_mins}분 전)"
except Exception:
    pass

st.sidebar.markdown(
    f"""
    <div style="background-color: #E8F1FF; padding: 14px; border-radius: 8px; text-align: center; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
        <div style="font-size: 11px; color: #6B7280; margin-bottom: 3px;">🟢 가장 최근 보관된 뉴스 발행일</div>
        <div style="font-size: 14px; font-weight: bold; color: #374151;">{latest_article_str} <span style="color:#EF4444; font-size:12px; font-weight:600;">{time_diff_str}</span></div>
    </div>
    """, unsafe_allow_html=True
)

st.sidebar.subheader("🚀 파이프라인 제어")

if st.sidebar.button("▶️ 지금 기사 서치 가동", type="primary", use_container_width=True):
    trigger_github_workflow("full", "🚀 깃허브 서버 가동 준비 중입니다.", "🔄 현재 신규 기사 분석 파이프라인이 작동 중입니다.", "✅ 작동이 완료되었습니다. 텔레그램을 확인해주세요.")

if st.sidebar.button("🔄 최근 기사 바뀐 룰로 재채점", use_container_width=True):
    trigger_github_workflow("score_only", "🔄 기준 변경에 따른 재채점을 준비 중입니다.", "🔄 변경된 룰로 기사 재채점 분석이 작동 중입니다.", "✅ 새로운 룰로 재채점 및 리포트 발송이 완료되었습니다.")

if st.sidebar.button("📤 AI 평가 완료 기사 즉시 발송", use_container_width=True):
    trigger_github_workflow("report_only", "📤 텔레그램 발송 서버를 호출 중입니다...", "🚀 발송 대기 중인 리포트를 전송하고 있습니다.", "✅ 텔레그램 리포트 발송이 완료되었습니다!")

st.sidebar.markdown("---")


# ==========================================
# 📺 3. 메인 화면 세부 메뉴 라우팅
# ==========================================
menu = st.sidebar.radio(
    "세부 메뉴를 선택하세요",
    ["📊 종합 상황판", "🔑 포함/제외 단어 제어", "📡 타깃 매체 제어", "📱 알림 및 수신처 설정", "🤖 AI 통합 설정", "🎯 Project B: 피드백 수집판"]
)

if menu == "📊 종합 상황판":
    st.title("📊 기사 서치 종합 상황판")
    st.markdown("---")
    st.markdown("#### 🔥 현재 기준 가장 뜨거운 딜 인텔리전스 Top 40")
    st.markdown("<span style='font-size:14px; color:#4B5563;'>* 1영업일(24시간)이 지나거나 폐기(E)된 기사는 자동으로 차트에서 사라집니다.</span>", unsafe_allow_html=True)
    
    # 공통 함수를 사용하여 깨끗하고 완벽한 데이터 로드
    hot_df = get_hot_articles(spreadsheet)
    
    if not hot_df.empty:
        # 화면 출력을 위해 불필요한 시스템 열 숨김 처리
        display_df = hot_df.drop(columns=['Execution_Time'], errors='ignore')
        st.dataframe(display_df, use_container_width=True, hide_index=True, height=750)
    else:
        st.info("현재 대시보드에 노출할 유효한 신규 기사가 없습니다.")

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
                if not kw: continue
                c1, c2 = st.columns([3, 1.5])
                with c1: st.markdown(f"<div style='padding-top: 8px; font-weight: 600; font-size: 16px; color: #1E3A8A;'>{kw}</div>", unsafe_allow_html=True)
                with c2:
                    current_w = float(row.get('Score', row.get('Weight', 1.0)))
                    new_w = st.number_input("점수 입력", min_value=0.0, max_value=10.0, value=current_w, step=1.0, key=f"kw_{idx}", label_visibility="collapsed")
                updated_kws.append([kw, new_w])
                
            st.markdown("---")
            with st.expander("➕ 새로운 타깃 키워드 추가하기"):
                new_kw = st.text_input("새로 추가할 키워드를 입력하세요.")
                new_w = st.number_input("새 키워드 점수를 입력하세요.", min_value=0.0, max_value=10.0, value=1.0, step=1.0)
            if st.button("💾 타깃 키워드 모두 저장", type="primary", use_container_width=True):
                if new_kw.strip(): updated_kws.append([new_kw.strip(), new_w])
                kw_sheet.clear()
                kw_sheet.update([["Keyword", "Score"]] + updated_kws)
                st.success("타깃 키워드가 성공적으로 저장되었습니다.")
        except Exception as e: 
            st.error(f"키워드 시트 오류가 발생했습니다. 내용은 {e} 입니다.")

    with col2:
        st.subheader("🚫 제외 단어 감점 설정")
        try:
            try: neg_sheet = spreadsheet.worksheet("Config_Negative")
            except: 
                neg_sheet = spreadsheet.add_worksheet(title="Config_Negative", rows="100", cols="2")
                neg_sheet.append_row(["Keyword", "Coefficient"])
                
            neg_data = neg_sheet.get_all_records()
            updated_negs = []
            for idx, row in enumerate(neg_data):
                kw = str(row.get('Keyword', '')).strip()
                if not kw: continue
                c1, c2 = st.columns([3, 1.5])
                with c1: st.markdown(f"<div style='padding-top: 8px; font-weight: 600; font-size: 16px; color: #991B1B;'>{kw}</div>", unsafe_allow_html=True)
                with c2:
                    current_w = float(row.get('Coefficient', 20.0))
                    new_w = st.number_input("감점 폭 입력", min_value=0.0, max_value=100.0, value=current_w, step=1.0, key=f"neg_{idx}", label_visibility="collapsed")
                updated_negs.append([kw, new_w])
                
            st.markdown("---")
            with st.expander("➕ 새로운 제외 단어 추가하기"):
                new_neg = st.text_input("새로 추가할 제외 단어를 입력하세요.")
                new_nw = st.number_input("새 단어 감점 폭을 입력하세요.", min_value=0.0, max_value=100.0, value=20.0, step=1.0)
            if st.button("💾 제외 단어 모두 저장", type="primary", use_container_width=True):
                if new_neg.strip(): updated_negs.append([new_neg.strip(), new_nw])
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
            if not domain: continue
            c1, c2 = st.columns([3, 1])
            with c1: st.markdown(f"<div style='padding-top: 8px; font-weight: 600; font-size: 16px; color: #065F46;'>{domain}</div>", unsafe_allow_html=True)
            with c2:
                current_w = float(row.get('Weight', row.get('Coefficient', 0.0)))
                new_w = st.number_input("점수 입력", min_value=0.0, max_value=5.0, value=current_w, step=1.0, key=f"media_{idx}", label_visibility="collapsed")
            updated_media.append([domain, new_w])
            
        st.markdown("---")
        with st.expander("➕ 새로운 언론사 도메인 추가하기"):
            new_domain = st.text_input("새 언론사 이름 도메인을 입력하세요.")
            new_mw = st.number_input("새 언론사 점수를 입력하세요.", min_value=0.0, max_value=5.0, value=1.0, step=1.0)
        if st.button("💾 언론사 매체 모두 저장", type="primary"):
            if new_domain.strip(): updated_media.append([new_domain.strip(), new_mw])
            media_sheet.clear()
            media_sheet.update([["Domain", "Weight"]] + updated_media)
            st.success("매체 가중치가 성공적으로 저장되었습니다.")
    except Exception as e: 
        st.error(f"매체 시트 오류가 발생했습니다. 내용은 {e} 입니다.")

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
                except Exception: sys_sheet.append_row([key, value])
            update_setting("TELEGRAM_GROUP_SEND", "ON" if tg_group_toggle else "OFF")
            update_setting("TELEGRAM_AUTHOR_SEND", "ON" if tg_author_toggle else "OFF")
            update_setting("EXTRA_TELEGRAM_IDS", extra_ids_input)
            st.success("수신처 설정이 데이터베이스에 기록되었습니다.")
    except Exception as e: 
        st.error(f"오류가 발생했습니다: {e}")

elif menu == "🤖 AI 통합 설정":
    st.title("🤖 AI 엔진 및 평가 매커니즘 통합 설정")
    st.markdown("---")
    try:
        sys_sheet = spreadsheet.worksheet("Config_System")
        config = {str(r.get("Key")): str(r.get("Value")) for r in sys_sheet.get_all_records()}
        
        current_engine = config.get("AI_ENGINE", "유료 Claude")
        current_persona = config.get("ACTIVE_PERSONA", "옵션 1 (기본 금융 전문가)")
        current_delay = int(config.get("AI_DELAY_SECONDS", 5))
        current_ai_weight = int(config.get("AI_WEIGHT_PERCENT", 55))
        
        col_sys1, col_sys2 = st.columns([1, 1])
        with col_sys1:
            st.subheader("⚙️ AI 구동 코어 설정")
            st.markdown("<div style='padding: 15px; border: 1px solid #E5E7EB; border-radius: 8px; background-color: #F9FAFB;'>", unsafe_allow_html=True)
            opts_engine = ["AI 사용 안 함", "무료 Gemini", "무료 Groq", "유료 Claude", "전체"]
            selected_engine = st.selectbox("엔진 종류를 선택하세요.", opts_engine, index=opts_engine.index(current_engine) if current_engine in opts_engine else 3)
            opts_persona = ["옵션 1 (기본 금융 전문가)", "옵션 2 (신규 커스텀)"]
            selected_persona = st.selectbox("적용할 AI 페르소나를 선택하세요.", opts_persona, index=opts_persona.index(current_persona) if current_persona in opts_persona else 0)
            selected_delay = st.slider("⏱️ AI API 호출 대기 시간 (초)", min_value=1, max_value=20, value=current_delay)
            st.markdown("</div>", unsafe_allow_html=True)
            
        with col_sys2:
            st.subheader("🧠 최종 점수 반영 가중치 배분")
            st.markdown("<div style='padding: 15px; border: 1px solid #E5E7EB; border-radius: 8px; background-color: #F3F4F6;'>", unsafe_allow_html=True)
            selected_ai_weight = st.slider("🎯 최종 총점 내 AI 평가 점수 반영 비중 (%)", min_value=0, max_value=100, value=current_ai_weight)
            st.info(f"📊 **종합 가중치 룰 반영 예시**\n* **AI 주관적 평가 반영:** `{selected_ai_weight}%` \n* **키워드/매체 기초점수 반영:** `{100 - selected_ai_weight}%` ")
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("💾 AI 엔진 및 가중치 설정 저장", type="primary", use_container_width=True):
            def update_setting(key, value):
                try: 
                    cell = sys_sheet.find(key)
                    sys_sheet.update_cell(cell.row, cell.col + 1, value)
                except Exception: sys_sheet.append_row([key, value])
            update_setting("AI_ENGINE", selected_engine)
            update_setting("ACTIVE_PERSONA", selected_persona)
            update_setting("AI_DELAY_SECONDS", str(selected_delay))
            update_setting("AI_WEIGHT_PERCENT", str(selected_ai_weight))
            st.success("AI 핵심 구성 설정 및 점수 배분 가중치가 성공적으로 동기화되었습니다.")

        st.markdown("<br><hr>", unsafe_allow_html=True)
        st.subheader("📜 1. AI 페르소나 지시문 프롬프트 커스텀")
        col_p1, col_p2 = st.columns(2)
        with col_p1: p1_text = st.text_area("옵션 1 프롬프트 지시문 (기본 금융 전문가)", value=config.get("PERSONA_1", "당신은 냉철한 금융 전문가입니다."), height=150)
        with col_p2: p2_text = st.text_area("옵션 2 프롬프트 지시문 (신규 커스텀)", value=config.get("PERSONA_2", "당신은 트렌드에 민감한 기술 전문 투자자입니다."), height=150)
            
        if st.button("💾 각 페르소나 지시문 개별 저장"):
            def update_sys(key, val):
                try: 
                    cell = sys_sheet.find(key)
                    sys_sheet.update_cell(cell.row, cell.col + 1, val)
                except Exception: sys_sheet.append_row([key, val])
            update_sys("PERSONA_1", p1_text)
            update_sys("PERSONA_2", p2_text)
            st.success("페르소나 프롬프트가 안전하게 업데이트되었습니다.")
            
        st.markdown("<br><hr>", unsafe_allow_html=True)
        st.subheader("📊 2. AI 세부 채점 매커니즘 (Rubric) 고도화")
        rubric_sheet = spreadsheet.worksheet("Config_Rubric")
        edited_df = st.data_editor(pd.DataFrame(rubric_sheet.get_all_records()), num_rows="dynamic", use_container_width=True, height=350)
        if st.button("💾 세부 채점 기준(Rubric) 영구 저장", use_container_width=True):
            rubric_sheet.clear()
            rubric_sheet.update([edited_df.columns.values.tolist()] + edited_df.values.tolist())
            st.success("인공지능 채점용 루브릭이 성공적으로 반영되었습니다.")
            
    except Exception as e: 
        st.error(f"AI 설정 로드 중 오류가 발생했습니다: {e}")

elif menu == "🎯 Project B: 피드백 수집판":
    st.title("🎯 Project B: 뉴스 리포트 피드백 수집판")
    st.markdown("---")
    st.markdown("##### 🚀 가장 가치 있는 Hot 기사들을 검토하고 취향 피드백을 남겨주세요. 이 데이터는 자동 강화학습 엔진의 핵심 데이터셋으로 영구 누적됩니다.")
    
    # 공통 함수를 사용하여 깨끗하고 완벽한 데이터 로드
    hot_df = get_hot_articles(spreadsheet)
    
    if not hot_df.empty:
        with st.form("feedback_form"):
            feedback_results = []
            for idx, row in hot_df.iterrows():
                # 'Sent' 컬럼 데이터를 활용하여 화면에 상태 표시
                status_badge = "✅ 텔레그램 발송 완료" if row.get('Sent') == 'Y' else "⏳ 발송 대기 중"
                
                st.markdown(f"<div style='font-size: 16px; font-weight: bold; color: #1E3A8A; margin-top: 10px;'>[{idx+1}] {row['Title']}</div>", unsafe_allow_html=True)
                st.markdown(f"🔗 [기사 원문 열기]({row['Link']}) | 📡 매체: **{row['Media']}** | ⭐ 최종 총점: **{row['Total_Score']}점** | {status_badge}")
                st.markdown(f"🏷️ 연관 추출 키워드: `{row['Matched_Keywords']}`")
                
                fb = st.radio(
                    "이 기사에 대한 품질 평가를 선택하세요.",
                    ["평가 보류", "👍 좋아요 (이런 기사 추천 가중치 상승)", "👎 싫어요 (이런 기사 필터링 감점 강화)"],
                    key=f"fb_select_{idx}",
                    horizontal=True
                )
                st.markdown("<hr style='margin: 12px 0; border: 0; border-top: 1px dashed #E5E7EB;'>", unsafe_allow_html=True)
                
                feedback_results.append({
                    "Date": row['Date'].strftime("%Y-%m-%d %H:%M:%S") if isinstance(row['Date'], pd.Timestamp) else row['Date'],
                    "Title": row['Title'],
                    "Link": row['Link'],
                    "Media": row['Media'],
                    "Matched_Keywords": row['Matched_Keywords'],
                    "Total_Score": row['Total_Score'],
                    "Feedback": fb
                })
                
            submit_btn = st.form_submit_button("💾 피드백 데이터 수집 저장소에 동기화", use_container_width=True)
            
            if submit_btn:
                try:
                    try:
                        fb_sheet = spreadsheet.worksheet("DB_Feedback")
                    except Exception:
                        fb_sheet = spreadsheet.add_worksheet(title="DB_Feedback", rows="5000", cols="8")
                        fb_sheet.append_row(["Feedback_Time", "Article_Date", "Title", "Link", "Media", "Matched_Keywords", "Total_Score", "Feedback_Result"])
                    
                    now_str = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
                    rows_to_append = []
                    for f_item in feedback_results:
                        if f_item["Feedback"] != "평가 보류":
                            rows_to_append.append([now_str, f_item["Date"], f_item["Title"], f_item["Link"], f_item["Media"], f_item["Matched_Keywords"], f_item["Total_Score"], f_item["Feedback"]])
                            
                    if rows_to_append:
                        fb_sheet.append_rows(rows_to_append)
                        st.success(f"✅ 총 {len(rows_to_append)}개의 고품질 취향 피드백이 DB_Feedback 시트에 안전하게 영구 저장되었습니다.")
                    else:
                        st.warning("⚠️ 좋아요 또는 싫어요 마킹을 한 기사가 한 개도 발견되지 않았습니다.")
                except Exception as e:
                    st.error(f"데이터베이스 기록에 실패했습니다. 에러 내용은 {e} 입니다.")
    else:
        st.info("피드백을 남길 수 있는 유효한 신규 기사가 존재하지 않습니다.")
