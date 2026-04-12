import re
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

from modules.french.french_logic import get_french_bot_result
from modules.psychology.llm_handler import get_psychology_bot_result
from modules.semiconductor.logic import get_semiconductor_bot_result

# 1. 페이지 설정
st.set_page_config(
    page_title="NewLearn",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 2. 과목 데이터 정의
SUBJECTS = [
    {
        "name": "한국사",
        "icon": "🏺",
        "desc": "시대별 사건, 사료 해석, 비교사 관점까지 핵심만 빠르게 정리합니다.",
        "welcome": "안녕하세요! <b>한국사</b> 학습봇입니다.<br>시대 흐름 정리, 사건 비교, 사료 해석까지 함께 공부해요.",
    },
    {
        "name": "일본어",
        "icon": "🗾",
        "desc": "문법, 독해, 회화 표현을 단계별로 연습하고 실전 예문을 제공합니다.",
        "welcome": "안녕하세요! <b>일본어</b> 학습봇입니다.<br>문법 설명, 회화 표현, JLPT 스타일 문제까지 도와드릴게요.",
    },
    {
        "name": "프랑스어",
        "icon": "🥖",
        "desc": "기초 문법부터 작문 첨삭까지 학습 수준에 맞춘 설명을 제공합니다.",
        "welcome": "안녕하세요! <b>프랑스어</b> 학습봇입니다.<br>기초 문법, 발음 포인트, 작문 첨삭까지 단계별로 안내합니다.",
    },
    {
        "name": "심리학",
        "icon": "🧠",
        "desc": "주요 이론, 실험 설계, 논문 읽기 포인트를 쉽게 연결해 줍니다.",
        "welcome": "안녕하세요! <b>심리학</b> 학습봇입니다.<br>핵심 이론, 고전 실험, 연구 설계 포인트를 쉽게 정리해 드려요.",
    },
    {
        "name": "반도체",
        "icon": "🧩",
        "desc": "소자 물리, 공정 흐름, 회로 기본 개념을 사례 중심으로 학습합니다.",
        "welcome": "안녕하세요! <b>반도체</b> 학습봇입니다.<br>소자 물리, 공정 단계, 회로 기초를 실제 사례 중심으로 설명해 드립니다.",
    },
]

SUBJECT_INFO = {subject["name"]: subject for subject in SUBJECTS}
SUBJECT_NAMES = list(SUBJECT_INFO.keys())

# --- 헬퍼 함수 정의 ---

def now():
    d = datetime.now()
    return f"{d.hour}:{d.minute:02d}"

def get_history(subject):
    if subject not in st.session_state.histories:
        st.session_state.histories[subject] = [
            {
                "role": "bot",
                "content": SUBJECT_INFO[subject]["welcome"],
                "time": now(),
                "image": None
            }
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
        # 랜딩에서 과목을 눌러 진입하면 해당 과목 대화를 새로 시작한다.
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
.stDeployButton,[data-testid="stToolbar"],header[data-testid="stHeader"]{{display:none}}
:root{{
    --nl-bg:#eef3fb;
    --nl-surface:#ffffff;
    --nl-surface-soft:#f8fbff;
    --nl-line:#dce6f2;
    --nl-primary:#185fa5;
    --nl-primary-strong:#0f4d87;
    --nl-text:#17212f;
    --nl-muted:#62748a;
    --nl-shadow:0 20px 50px rgba(17,44,79,.13);
}}
.stApp{{
    background:
        radial-gradient(circle at 8% 8%, rgba(24,95,165,.12), transparent 32%),
        radial-gradient(circle at 88% 16%, rgba(66,153,225,.10), transparent 35%),
        linear-gradient(180deg,#f6f9ff 0%, var(--nl-bg) 55%, #edf2fa 100%);
    font-family:'Noto Sans KR',sans-serif;
}}
.main .block-container{{padding:1.5rem 2rem!important;max-width:100%!important}}
.tts-btn {{ cursor: pointer; border: 1px solid #dce6f2; background: #f8fbff; color: #185fa5; border-radius: 20px; padding: 6px 12px; font-size: 13px; font-weight: 600; display: inline-flex; align-items: center; }}
[data-testid="stSidebar"]{{{sidebar_visibility}background:#f8f9fa!important;border-right:1px solid #e9ecef;min-width:220px!important;max-width:220px!important}}
[data-testid="stSidebar"]>div:first-child{{padding:0!important}}
[data-testid="stSidebar"] .stButton>button{{display:flex!important;align-items:center!important;gap:10px!important;padding:8px 10px!important;border-radius:8px!important;font-size:13px!important;color:#495057!important;margin-bottom:2px!important;border:none!important;background:none!important;width:100%!important;text-align:left!important;box-shadow:none!important;font-family:'Noto Sans KR',sans-serif!important;font-weight:400!important;justify-content:flex-start!important}}
[data-testid="stSidebar"] .stButton>button:hover{{background:#e9ecef!important}}
[data-testid="stSidebar"] .stButton>button[kind="primary"]{{background:#e8f0fb!important;color:#185FA5!important;font-weight:500!important}}

.landing-shell{{
    border-radius:22px;
    overflow:hidden;
    box-shadow:var(--nl-shadow);
    background:var(--nl-surface);
    border:1px solid var(--nl-line);
}}
.landing-nav{{
    padding:14px 22px;
    border-bottom:1px solid #e6edf6;
    display:flex;
    justify-content:space-between;
    align-items:center;
    gap:10px;
    background:rgba(255,255,255,.95);
}}
.landing-brand{{font-size:20px;font-weight:800;color:var(--nl-primary);letter-spacing:-.4px}}
.landing-pill{{font-size:11px;color:#34567a;background:#e9f2ff;border:1px solid #d6e7ff;border-radius:999px;padding:4px 11px;white-space:nowrap}}
.hero{{
    padding:42px 26px 30px;
    background:
        radial-gradient(circle at 86% 20%, rgba(24,95,165,.14), transparent 34%),
        linear-gradient(135deg,#ffffff 0%, #f5faff 58%, #edf5ff 100%);
    text-align:center;
}}
.badge-pill{{display:inline-block;background:#deecff;color:#174f87;font-size:11px;font-weight:700;padding:5px 13px;border-radius:999px}}
.hero h1{{margin:14px 0 10px;font-size:36px;line-height:1.23;letter-spacing:-.6px;color:var(--nl-text)}}
.hero p{{margin:0 auto;color:var(--nl-muted);font-size:14px;line-height:1.85;max-width:760px}}
.hero-btn-note{{margin-top:10px;color:#6d7f93;font-size:12px}}
.btn-row{{display:flex;justify-content:center;gap:12px;flex-wrap:wrap;margin-top:20px}}

.section-cards{{padding:18px 2px 4px}}
.section-cards h2{{font-size:25px;text-align:center;margin:0 0 5px;letter-spacing:-.35px;color:var(--nl-text)}}
.section-cards .sub{{text-align:center;color:#6d7f93;font-size:13px;margin-bottom:16px}}
.edu-card{{
    background:linear-gradient(180deg,#ffffff 0%, #f8fbff 100%);
    border:1px solid #deebf7;
    border-radius:14px;
    padding:14px;
    min-height:136px;
    transition:.16s ease;
}}
.edu-card:hover{{transform:translateY(-2px);box-shadow:0 11px 24px rgba(19,68,114,.11)}}
.icon-wrap{{width:40px;height:40px;border-radius:11px;display:flex;align-items:center;justify-content:center;font-size:20px;margin-bottom:8px;background:#e7f1ff}}
.edu-card h5{{margin:0 0 6px;font-size:16px;color:#17385e}}
.edu-card p{{margin:0;color:#5c7288;font-size:12.5px;line-height:1.72}}
.landing-footer{{
    margin-top:12px;
    border-top:1px solid #dbe8f7;
    padding:12px 16px;
    font-size:12px;
    color:#667f96;
    display:flex;
    justify-content:space-between;
    gap:8px;
    flex-wrap:wrap;
    background:#fbfdff;
    border-radius:12px;
}}

.stButton button[kind="primary"]{{
    background:var(--nl-primary)!important;
    color:#fff!important;
    border-radius:10px!important;
    border:1px solid var(--nl-primary)!important;
    font-weight:600!important;
}}
.stButton button[kind="primary"]:hover{{background:var(--nl-primary-strong)!important}}

.stButton button.btn-detail-ghost{{
    background:#fff!important;
    color:#37536c!important;
    border-radius:10px!important;
    border:1px solid #d7e2ee!important;
}}

.app-wrapper{{display:flex;width:100%;height:78vh;border-radius:16px;overflow:hidden;box-shadow:0 8px 32px rgba(0,0,0,.1);background:#fff}}
.chat-area{{flex:1;display:flex;flex-direction:column;min-width:0;background:#fff}}
.chat-header{{padding:14px 20px;border-bottom:1px solid #e9ecef;display:flex;align-items:center;gap:10px;flex-shrink:0}}
.badge-subject{{background:#e8f0fb;color:#185fa5;font-size:11px;font-weight:500;padding:3px 10px;border-radius:20px}}
.chat-messages{{flex:1;overflow-y:auto;padding:20px;display:flex;flex-direction:column;gap:16px}}
.msg-row{{display:flex;gap:10px;align-items:flex-end}}
.msg-row.user{{flex-direction:row-reverse}}
.avatar{{width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;flex-shrink:0}}
.avatar-bot{{background:#e8f0fb;color:#185fa5}}
.avatar-user{{background:#e8f5e9;color:#2e7d32}}
.bubble{{max-width:72%;padding:10px 14px;font-size:13px;line-height:1.65;color:#212529}}
.bubble-bot{{background:#f8f9fa;border-radius:4px 14px 14px 14px;max-width:200%}}
.bubble-user{{background:#185fa5;color:#fff;border-radius:14px 4px 14px 14px;max-width:200%}}
.msg-time{{font-size:10px;color:#adb5bd;margin:2px 4px 0}}
[data-testid="stChatInput"] textarea{{border-radius:12px!important;border:1px solid #dee2e6!important;font-family:'Noto Sans KR',sans-serif!important;font-size:13px!important}}
[data-testid="stChatInput"] textarea:focus{{border-color:#185fa5!important;box-shadow:0 0 0 2px rgba(24,95,165,.12)!important}}
[data-testid="stChatInput"] button{{background:#185fa5!important;border-radius:10px!important}}
[data-testid="stChatInput"]{{padding:8px 16px!important}}
[data-testid="stBottomBlockContainer"]{{padding:0!important;background:transparent!important}}

@media (max-width: 900px){{
  .hero h1{{font-size:28px}}
}}
@media (max-width: 640px){{
  .hero{{padding:28px 16px 20px}}
  .hero h1{{font-size:22px}}
    .section-cards{{padding:14px 0 2px}}
    .landing-footer{{flex-direction:column;align-items:flex-start}}
}}
</style>
    """,
        unsafe_allow_html=True,
    )


def render_messages(history):
    rows = []
    for msg in history:
        t = msg.get("time", "")
        c = msg["content"]
        img = msg.get("image")
        
        # 1. 프랑스어 챗봇 파일의 텍스트 전처리 로직 이식
        c_display = c.strip()
        c_display = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', c_display)
        c_display = re.sub(r'\n+', '\n', c_display).replace('\n[', '\n\n[')
        c_display = c_display.replace('프랑스어 문장:', '<b>프랑스어 문장:</b>')

        if msg["role"] == "bot":
            # 2. 프랑스어 챗봇 파일의 TTS 및 이미지 처리 로직 이식
            tts_html = ""
            if "프랑스어 문장:" in c:
                try:
                    parts = c.split("프랑스어 문장:")
                    fr_text = parts[1].split('\n')[0].strip().replace('"', '&quot;')
                    tts_html = f'<div style="margin-top:10px;"><button class="tts-btn" data-text="{fr_text}" data-lang="fr-FR">🇫🇷 발음 듣기</button></div>'
                except Exception:
                    pass
            
            img_html = f'<img src="{img}" style="margin-top:8px; max-width:250px; border-radius:10px; display:block;">' if img else ""
            
            # 3. 심리 챗봇 파일의 예쁜 HTML 디자인 껍데기로 감싸기
            rows.append(
                f'<div class="msg-row">'
                f'<div class="avatar avatar-bot">봇</div>'
                f'<div><div class="bubble bubble-bot">{c_display}{tts_html}{img_html}</div>'
                f'<div class="msg-time">{t}</div></div></div>'
            )
        else:
            # 유저 메시지 처리 (심리 챗봇 파일 디자인 유지)
            rows.append(
                f'<div class="msg-row user">'
                f'<div class="avatar avatar-user">나</div>'
                f'<div><div class="bubble bubble-user">{c_display}</div>'
                f'<div class="msg-time" style="text-align:right">{t}</div></div></div>'
            )
    return "\n".join(rows)


# --- 메인 로직 ---
def call_llm(subject, history):
    prompt = history[-1]["content"]
    
    if subject == "프랑스어":
        return get_french_bot_result(prompt)
    elif subject == "심리학":
        return get_psychology_bot_result(prompt, history)
    elif subject == "반도체":
        return get_semiconductor_bot_result(history)
    return f"현재 {subject} 학습봇은 준비 중입니다.", None

def render_landing():
    st.markdown(
        """
<div class="landing-shell">
    <div class="landing-nav">
        <div class="landing-brand">NewLearn</div>
        <div class="landing-pill">2026 학습 파트너</div>
    </div>
    <section class="hero">
        <span class="badge-pill">AI 기반 전공 학습 플랫폼</span>
        <h1>5개의 전공 전문 AI 챗봇</h1>
        <p>전공별 AI 튜터와 함께 더 스마트하게 공부하세요.<br>역사부터 반도체까지, 24시간 전문 도우미가 즉시 답합니다.</p>
    </section>
</div>
""",
        unsafe_allow_html=True,
    )

    cta_col1, cta_col2 = st.columns([1, 1])
    with cta_col1:
        if st.button("챗봇 시작하기", key="landing_chat_start", type="primary", use_container_width=True):
            st.session_state.page = "chat"
            st.session_state.histories.pop(st.session_state.subject, None)
            sync_query_params()
            st.rerun()
    with cta_col2:
        if st.button("자세히 보기", key="landing_detail", use_container_width=True, type="secondary"):
            st.info("아래 과목을 선택하면 해당 과목 챗봇으로 바로 시작됩니다.")

    st.markdown('<p class="hero-btn-note">원하는 전공 카드를 선택하면 해당 챗봇으로 즉시 이동합니다.</p>', unsafe_allow_html=True)

    st.markdown(
        """
<div class="section-cards">
    <h2>전공별 챗봇 선택</h2>
    <p class="sub">원하는 전공을 선택하여 AI 전문가와 대화를 시작하세요</p>
</div>
""",
        unsafe_allow_html=True,
    )

    cols = st.columns(3)
    for idx, subject in enumerate(SUBJECTS):
        with cols[idx % 3]:
            st.markdown(
                f"""
<div class="edu-card">
    <div class="icon-wrap">{subject['icon']}</div>
    <h5>{subject['name']}</h5>
    <p>{subject['desc']}</p>
</div>
""",
                unsafe_allow_html=True,
            )
            if st.button(f"{subject['name']} 시작", key=f"start_{subject['name']}", use_container_width=True):
                st.session_state.subject = subject["name"]
                st.session_state.page = "chat"
                st.session_state.histories.pop(subject["name"], None)
                sync_query_params()
                st.rerun()

    st.markdown(
        """
<div class="landing-footer">
    <span>© 2026 NewLearn. 모든 권리 보유.</span>
    <span>AI 기반 전공 학습 플랫폼</span>
</div>
""",
        unsafe_allow_html=True,
    )


def render_chat():
    with st.sidebar:
        st.markdown(
            """
<div style="padding:20px 16px 14px;border-bottom:1px solid #e9ecef;margin-bottom:4px;">
  <div style="font-size:15px;font-weight:700;color:#185FA5;letter-spacing:-0.3px;">NewLearn</div>
  <div style="font-size:11px;color:#868e96;margin-top:3px;">과목을 선택해 학습을 시작하세요</div>
</div>
""",
            unsafe_allow_html=True,
        )

        if st.button("← 메인으로", key="btn_go_landing", use_container_width=True):
            st.session_state.page = "landing"
            sync_query_params()
            st.rerun()

        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

        for subject in SUBJECTS:
            name = subject["name"]
            is_active = st.session_state.subject == name
            if st.button(
                f"{'▶' if is_active else '○'}  {name}",
                key=f"btn_{name}",
                type="primary" if is_active else "secondary",
                use_container_width=True,
            ):
                st.session_state.subject = name
                sync_query_params()
                st.rerun()

    subject = st.session_state.subject
    history = get_history(subject)

    # 심리 챗봇 파일의 예쁜 채팅창 렌더링
    st.markdown(
        f"""
<div class="app-wrapper">
  <div class="chat-area">
    <div class="chat-header">
      <span class="badge-subject">{subject}</span>
    </div>
    <div class="chat-messages">{render_messages(history)}</div>
  </div>
</div>
    """,
        unsafe_allow_html=True,
    )
    
    # === 프랑스어 챗봇 파일에서 가져온 필수 Javascript 삽입 부분 ===
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
    setInterval(attachEvents, 500); // 렌더링 갱신 시 이벤트 재바인딩
    </script>
    """, width=0, height=0)

    # 채팅 입력 부분 유지
    if prompt := st.chat_input(f"{subject}에 대해 질문하세요..."):
        history.append({"role": "user", "content": prompt, "time": now()})
        with st.spinner("생각 중...💭"):
            response, ans_image = call_llm(subject, history)
        history.append({"role": "bot", "content": response, "image": ans_image, "time": now()})
        st.rerun()

# --- 앱 실행 ---
init_state()
sync_query_params()
inject_styles(st.session_state.page)

if st.session_state.page == "chat":
    render_chat()
else:
    render_landing()