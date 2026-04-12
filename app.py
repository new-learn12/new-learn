import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime
import re
from modules.french.french_logic import get_french_bot_result

# 1. 페이지 설정 (가장 위에 단 한 번만 와야 합니다)
st.set_page_config(
    page_title="NewLearn",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 2. 과목 데이터 정의
SUBJECTS = [
    {"name": "역사", "icon": "🏺", "desc": "시대별 사건, 사료 해석, 비교사 관점까지 핵심만 빠르게 정리합니다.", "welcome": "안녕하세요! <b>역사</b> 학습봇입니다.<br>시대 흐름 정리, 사건 비교, 사료 해석까지 함께 공부해요."},
    {"name": "일본어", "icon": "🗾", "desc": "문법, 독해, 회화 표현을 단계별로 연습하고 실전 예문을 제공합니다.", "welcome": "안녕하세요! <b>일본어</b> 학습봇입니다.<br>문법 설명, 회화 표현, JLPT 스타일 문제까지 도와드릴게요."},
    {"name": "프랑스어", "icon": "🥖", "desc": "기초 문법부터 작문 첨삭까지 학습 수준에 맞춘 설명을 제공합니다.", "welcome": "안녕하세요! <b>프랑스어</b> 학습봇입니다.<br>기초 문법, 발음 포인트, 작문 첨삭까지 단계별로 안내합니다."},
    {"name": "심리학", "icon": "🧠", "desc": "주요 이론, 실험 설계, 논문 읽기 포인트를 쉽게 연결해 줍니다.", "welcome": "안녕하세요! <b>심리학</b> 학습봇입니다.<br>핵심 이론, 고전 실험, 연구 설계 포인트를 쉽게 정리해 드려요."},
    {"name": "반도체", "icon": "🧩", "desc": "소자 물리, 공정 흐름, 회로 기본 개념을 사례 중심으로 학습합니다.", "welcome": "안녕하세요! <b>반도체</b> 학습봇입니다.<br>소자 물리, 공정 단계, 회로 기초를 실제 사례 중심으로 설명해 드립니다."},
]

SUBJECT_INFO = {subject["name"]: subject for subject in SUBJECTS}
SUBJECT_NAMES = list(SUBJECT_INFO.keys())

# --- 헬퍼 함수 정의 ---

def now():
    d = datetime.now()
    return f"{d.hour}:{d.minute:02d}"

def get_history(subject):
    if subject not in st.session_state.histories:
        welcome = next((s["welcome"] for s in SUBJECTS if s["name"] == subject), "")
        st.session_state.histories[subject] = [
            {"role": "bot", "content": welcome, "time": now(), "image": None}
        ]
    return st.session_state.histories[subject]

def sync_query_params():
    st.query_params["view"] = st.session_state.page
    st.query_params["subject"] = st.session_state.subject

def init_state():
    if "subject" not in st.session_state:
        st.session_state.subject = SUBJECTS[0]["name"]
    if "histories" not in st.session_state:
        st.session_state.histories = {}
    if "page" not in st.session_state:
        st.session_state.page = "landing"

    query_view = st.query_params.get("view")
    query_subject = st.query_params.get("subject")
    query_start = st.query_params.get("start")

    if query_view in ["landing", "chat"]:
        st.session_state.page = query_view
    if query_subject in SUBJECT_NAMES:
        st.session_state.subject = query_subject
    if query_start == "1" and st.session_state.subject in st.session_state.histories:
        st.session_state.histories.pop(st.session_state.subject, None)
        try:
            del st.query_params["start"]
        except Exception:
            pass

def inject_styles(current_page):
    sidebar_visibility = "display:none!important;" if current_page == "landing" else ""
    st.markdown(
        f"""
<style>
#MainMenu,footer{{visibility:hidden}}
[data-testid="collapsedControl"]{{display:none!important}}
[data-testid="stSidebar"][aria-expanded="false"]{{transform:none!important;width:220px!important;min-width:220px!important}}
button[kind="header"]{{display:none!important}}
.stApp{{
    background: radial-gradient(circle at 8% 8%, rgba(24,95,165,.12), transparent 32%), linear-gradient(180deg,#f6f9ff 0%, #eef3fb 55%, #edf2fa 100%);
    font-family:'Noto Sans KR',sans-serif;
}}
.bubble{{max-width:75%;padding:14px 18px;font-size:15.5px;line-height:1.6;color:#212529; white-space: pre-wrap; word-break: break-word;}}
.bubble-bot{{background:#f8f9fa;border-radius:4px 14px 14px 14px;}}
.bubble-user{{background:#185fa5;color:#fff;border-radius:14px 4px 14px 14px;}}
.tts-btn {{ cursor: pointer; border: 1px solid #dce6f2; background: #f8fbff; color: #185fa5; border-radius: 20px; padding: 6px 12px; font-size: 13px; font-weight: 600; display: inline-flex; align-items: center; }}
[data-testid="stSidebar"]{{{sidebar_visibility}}}
</style>
""", unsafe_allow_html=True)

def render_messages(history):
    rows = []
    for msg in history:
        c = msg["content"]
        img = msg.get("image")
        c_display = c.strip()
        c_display = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', c_display)
        c_display = re.sub(r'\n+', '\n', c_display).replace('\n[', '\n\n[')
        c_display = c_display.replace('프랑스어 문장:', '<b>프랑스어 문장:</b>')

        if msg["role"] == "bot":
            tts_html = ""
            if "프랑스어 문장:" in c:
                try:
                    parts = c.split("프랑스어 문장:")
                    fr_text = parts[1].split('\n')[0].strip().replace('"', '&quot;')
                    tts_html = f'<div style="margin-top:10px;"><button class="tts-btn" data-text="{fr_text}" data-lang="fr-FR">🇫🇷 발음 듣기</button></div>'
                except Exception:
                    pass
            img_html = f'<img src="{img}" style="margin-top:8px; max-width:250px; border-radius:10px; display:block;">' if img else ""
            rows.append(f'<div style="display:flex; gap:10px; margin-bottom:16px;"><div class="bubble bubble-bot">{c_display}{tts_html}{img_html}</div></div>')
        else:
            rows.append(f'<div style="display:flex; justify-content:flex-end; margin-bottom:16px;"><div class="bubble bubble-user">{c_display}</div></div>')
    return "\n".join(rows)

# --- 메인 로직 ---

def call_llm(subject, history):
    prompt = history[-1]["content"]
    if subject == "프랑스어":
        return get_french_bot_result(prompt)
    # 오류가 났던 지점 수정 완료 (None 반환)
    return f"현재 {subject} 학습봇은 준비 중입니다.", None

def render_landing():
    st.markdown('<h1 style="text-align:center;">NewLearn 파트너</h1>', unsafe_allow_html=True)
    cols = st.columns(3)
    for idx, subject in enumerate(SUBJECTS):
        with cols[idx % 3]:
            if st.button(f"{subject['icon']} {subject['name']} 시작", key=f"btn_{subject['name']}", use_container_width=True):
                st.session_state.subject = subject["name"]
                st.session_state.page = "chat"
                st.rerun()

def render_chat():
    with st.sidebar:
        if st.button("← 메인으로", use_container_width=True):
            st.session_state.page = "landing"
            st.rerun()
    
    subject = st.session_state.subject
    history = get_history(subject)
    st.markdown(f"### {subject} 학습 세션")
    st.markdown(render_messages(history), unsafe_allow_html=True)

    components.html("""
    <script>
    function attachEvents() {
        try {
            const parentDoc = window.parent.document;
            const buttons = parentDoc.querySelectorAll('.tts-btn:not(.bound)');

            buttons.forEach(btn => {
                btn.classList.add('bound'); 

                btn.addEventListener('click', function() {
                    const text = this.getAttribute('data-text');
                    const lang = this.getAttribute('data-lang');
                    
                    if(text) {
                        window.parent.speechSynthesis.cancel();
                        const utterance = new window.parent.SpeechSynthesisUtterance(text);
                        utterance.lang = lang; 
                        utterance.rate = 0.9;
                        utterance.volume = 1.0;
                        window.parent.speechSynthesis.speak(utterance);
                    }
                });
            });
        } catch (e) {}
    }

    attachEvents();
    setInterval(attachEvents, 500);
    </script>
    """, width=0, height=0)

    if prompt := st.chat_input(f"{subject}에 대해 질문하세요..."):
        history.append({"role": "user", "content": prompt, "time": now()})
        with st.spinner("생각 중..."):
            response, ans_image = call_llm(subject, history)
        history.append({"role": "bot", "content": response, "image": ans_image, "time": now()})
        st.rerun()

# --- 앱 실행 ---
init_state()
inject_styles(st.session_state.page)

if st.session_state.page == "chat":
    render_chat()
else:
    render_landing()