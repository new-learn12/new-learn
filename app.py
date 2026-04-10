"""
NewLearn 전공 학습봇 - Streamlit 버전
chatbot.html + styles.min.css 기반으로 변환

실행: streamlit run app.py
설치: pip install streamlit openai
"""

import streamlit as st
from datetime import datetime

st.set_page_config(
    page_title="NewLearn",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ← 과목 목록: chatbot.html의 버튼 순서 그대로
SUBJECTS = [
    ("역사",     "dot-blue"),
    ("일본어",   "dot-purple"),
    ("프랑스어", "dot-amber"),
    ("심리학",   "dot-green"),
    ("반도체",   "dot-red"),
]

# 랜딩 페이지 카드용 아이콘·설명·색상 (SUBJECTS와 순서 동기화)
SUBJECT_INFO = {
    "역사":     ("📚", "한국사, 세계사, 근현대사 등 역사 전 분야 학습"),
    "일본어":   ("🈳", "히라가나, 가타카나, JLPT 등 일본어 전반 학습"),
    "프랑스어": ("🗼", "알파벳부터 회화, DELF까지 프랑스어 전반 학습"),
    "심리학":   ("🧠", "발달, 임상, 사회, 인지 등 심리학 전 분야 학습"),
    "반도체":   ("💻", "소자, 공정, 회로, 메모리 등 반도체 전 분야 학습"),
}
SUBJECT_COLORS = [
    ("#e8f0fb", "#185fa5"),
    ("#f3e8fd", "#9C27B0"),
    ("#fff8e1", "#FF9800"),
    ("#e8f5e9", "#4CAF50"),
    ("#fde8e8", "#F44336"),
]

# ── 세션 초기화 ──
if "page" not in st.session_state:
    st.session_state.page = "landing"

if "subject" not in st.session_state:
    st.session_state.subject = "역사"

if "histories" not in st.session_state:
    st.session_state.histories = {}


def get_history(subject):
    if subject not in st.session_state.histories:
        st.session_state.histories[subject] = [
            {"role": "bot", "content": f"안녕하세요! <b>{subject}</b> 학습봇입니다.<br>개념 질문, 예시 설명, 퀴즈 생성 등 무엇이든 물어보세요.", "time": ""}
        ]
    return st.session_state.histories[subject]


def now():
    d = datetime.now()
    return f"{d.hour}:{d.minute:02d}"


def render_messages(history):
    rows = []
    for m in history:
        t, c = m.get("time", ""), m["content"]
        if m["role"] == "bot":
            rows.append(f'<div class="msg-row"><div class="avatar avatar-bot">봇</div><div><div class="bubble bubble-bot">{c}</div><div class="msg-time">{t}</div></div></div>')
        else:
            rows.append(f'<div class="msg-row user"><div class="avatar avatar-user">나</div><div><div class="bubble bubble-user">{c}</div><div class="msg-time" style="text-align:right">{t}</div></div></div>')
    return "\n".join(rows)


def call_llm(subject, history):
    """
    OpenAI 연동:
        from openai import OpenAI
        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        msgs = [{"role":"system","content":f"{subject} 전문 튜터입니다."}]
        for h in history:
            msgs.append({"role":"assistant" if h["role"]=="bot" else "user","content":h["content"]})
        res = client.chat.completions.create(model="gpt-4o-mini",temperature=0.7,messages=msgs)
        return res.choices[0].message.content
    """
    last = history[-1]["content"]
    return f'"{last[:40]}{"..." if len(last)>40 else ""}"에 대한 답변입니다.<br>{subject} 맥락에 맞춰 LLM이 응답합니다.'


# ═══════════════════════════════════════════════════════
# LANDING PAGE
# ═══════════════════════════════════════════════════════
if st.session_state.page == "landing":

    st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
#MainMenu, footer { visibility: hidden; }
[data-testid="collapsedControl"] { display: none !important; }
[data-testid="stSidebar"] { display: none !important; }
.stDeployButton, [data-testid="stToolbar"], header[data-testid="stHeader"] { display: none; }
.stApp { background: #f8f9fa; font-family: 'Noto Sans KR', sans-serif; }
.main .block-container { padding: 0 !important; max-width: 100% !important; }

/* ── Header ── */
.lp-header {
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 48px;
  height: 64px;
  box-shadow: 0 1px 3px rgba(0,0,0,.08);
}
.lp-logo { font-size: 20px; font-weight: 700; color: #185FA5; letter-spacing: -0.3px; }
.lp-nav { display: flex; gap: 32px; }
.lp-nav a { text-decoration: none; color: #495057; font-size: 14px; font-weight: 500; }
.lp-nav a:hover { color: #5B4FCF; }
.lp-header-cta {
  background: #5B4FCF; color: #fff; border: none;
  padding: 10px 22px; border-radius: 8px;
  font-size: 14px; font-weight: 600;
  font-family: 'Noto Sans KR', sans-serif; cursor: default;
}

/* ── Hero ── */
.lp-hero {
  text-align: center;
  padding: 80px 24px 48px;
  background: #f8f9fa;
}
.lp-badge {
  display: inline-block;
  background: #eceaff; color: #5B4FCF;
  font-size: 13px; font-weight: 500;
  padding: 6px 18px; border-radius: 20px;
  margin-bottom: 28px;
}
.lp-title {
  font-size: 52px; font-weight: 800;
  color: #1a1a2e; margin: 0 0 20px;
  line-height: 1.15; letter-spacing: -1.5px;
}
.lp-subtitle {
  font-size: 16px; color: #6c757d;
  line-height: 1.8; margin-bottom: 0;
}

/* ── CTA 버튼 (Streamlit 버튼 오버라이드) ── */
.stApp .main .stButton > button {
  background: #5B4FCF !important;
  color: #fff !important;
  border: none !important;
  padding: 14px 0 !important;
  border-radius: 12px !important;
  font-size: 15px !important;
  font-weight: 600 !important;
  font-family: 'Noto Sans KR', sans-serif !important;
  width: 100% !important;
  box-shadow: 0 4px 14px rgba(91,79,207,.3) !important;
  letter-spacing: -0.3px !important;
  transition: all .15s !important;
}
.stApp .main .stButton > button:hover {
  background: #4a3eb8 !important;
  box-shadow: 0 6px 20px rgba(91,79,207,.4) !important;
  transform: translateY(-1px) !important;
}

/* ── Subject Cards ── */
.lp-cards-section {
  padding: 64px 48px;
  background: #fff;
}
.lp-section-title {
  text-align: center; font-size: 28px;
  font-weight: 700; color: #1a1a2e; margin-bottom: 10px;
}
.lp-section-sub {
  text-align: center; font-size: 14px;
  color: #5B4FCF; margin-bottom: 40px;
}
.lp-cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 24px;
  max-width: 1100px;
  margin: 0 auto;
}
.lp-card {
  background: #fff;
  border: 1.5px solid #e9ecef;
  border-radius: 16px;
  padding: 28px 24px;
  transition: box-shadow .2s, border-color .2s;
}
.lp-card:hover { box-shadow: 0 8px 24px rgba(0,0,0,.09); border-color: #ccc; }
.lp-card-icon {
  width: 52px; height: 52px;
  border-radius: 14px;
  display: flex; align-items: center; justify-content: center;
  font-size: 26px; margin-bottom: 16px;
}
.lp-card-title { font-size: 17px; font-weight: 700; color: #1a1a2e; margin-bottom: 8px; }
.lp-card-desc  { font-size: 13px; color: #868e96; line-height: 1.6; }

/* ── Footer ── */
.lp-footer {
  background: #1a1a2e; color: #adb5bd;
  padding: 24px 48px;
  display: flex; justify-content: space-between; align-items: center;
  font-size: 13px;
}
</style>
""", unsafe_allow_html=True)

    # ── Header ──
    st.markdown("""
<div class="lp-header">
  <div class="lp-logo">NewLearn</div>
  <nav class="lp-nav">
    <a href="#">홈</a>
    <a href="#">챗봇</a>
    <a href="#">소개</a>
    <a href="#">문의</a>
  </nav>
  <button class="lp-header-cta">무료로 시작하기</button>
</div>
""", unsafe_allow_html=True)

    # ── Hero ──
    st.markdown(f"""
<div class="lp-hero">
  <div class="lp-badge">AI 기반 전공 학습 플랫폼</div>
  <div class="lp-title">{len(SUBJECTS)}개의 전공 전문 AI 챗봇</div>
  <div class="lp-subtitle">
    전공별 AI 튜터와 함께 더 스마트하게 공부하세요.<br>
    역사부터 반도체까지, 24시간 전문 도우미가 즉시 답합니다.
  </div>
</div>
""", unsafe_allow_html=True)

    # ── CTA 버튼 (기능 있음) ──
    _, col_cta, _ = st.columns([3, 2, 3])
    with col_cta:
        if st.button("챗봇 시작하기", key="hero_cta"):
            st.session_state.page = "chat"
            st.rerun()

    # ── 전공별 챗봇 카드 (SUBJECTS에서 동적 생성) ──
    cards_html = ""
    for i, (name, _) in enumerate(SUBJECTS):
        icon, desc = SUBJECT_INFO[name]
        bg, tc = SUBJECT_COLORS[i]
        cards_html += f"""
    <div class="lp-card">
      <div class="lp-card-icon" style="background:{bg};color:{tc}">{icon}</div>
      <div class="lp-card-title">{name}</div>
      <div class="lp-card-desc">{desc}</div>
    </div>"""

    st.markdown(f"""
<div class="lp-cards-section">
  <div class="lp-section-title">전공별 챗봇 선택</div>
  <div class="lp-section-sub">원하는 전공을 선택하여 AI 전문가와 대화를 시작하세요</div>
  <div class="lp-cards-grid">{cards_html}
  </div>
</div>
""", unsafe_allow_html=True)

    # ── Footer ──
    st.markdown("""
<div class="lp-footer">
  <span>© 2025 NewLearn. 모든 권리 보유.</span>
  <span>AI 기반 전공 학습 플랫폼</span>
</div>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════
# CHAT PAGE
# ═══════════════════════════════════════════════════════
else:
    # ── CSS 주입 (styles.min.css 핵심 규칙 + Streamlit 오버라이드) ──
    st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap" rel="stylesheet">
<style>
#MainMenu,footer{visibility:hidden}
[data-testid="collapsedControl"]{display:none!important}
[data-testid="stSidebar"]{display:flex!important}
[data-testid="stSidebar"][aria-expanded="false"]{transform:none!important;width:220px!important;min-width:220px!important}
button[kind="header"]{display:none!important}
.stDeployButton,[data-testid="stToolbar"],header[data-testid="stHeader"]{display:none}
.stApp{background:#f0f2f5;font-family:'Noto Sans KR',sans-serif}
[data-testid="stSidebar"]{background:#f8f9fa!important;border-right:1px solid #e9ecef;min-width:220px!important;max-width:220px!important}
[data-testid="stSidebar"]>div:first-child{padding:0!important}
[data-testid="stSidebar"] .stButton>button{display:flex!important;align-items:center!important;gap:10px!important;padding:8px 10px!important;border-radius:8px!important;font-size:13px!important;color:#495057!important;margin-bottom:2px!important;border:none!important;background:none!important;width:100%!important;text-align:left!important;box-shadow:none!important;font-family:'Noto Sans KR',sans-serif!important;font-weight:400!important;justify-content:flex-start!important}
[data-testid="stSidebar"] .stButton>button:hover{background:#e9ecef!important}
[data-testid="stSidebar"] .stButton>button[kind="primary"]{background:#e8f0fb!important;color:#185FA5!important;font-weight:500!important}
.main .block-container{padding:1.5rem 2rem!important;max-width:100%!important}
.app-wrapper{display:flex;width:100%;height:78vh;border-radius:16px;overflow:hidden;box-shadow:0 8px 32px rgba(0,0,0,.1);background:#fff}
.chat-area{flex:1;display:flex;flex-direction:column;min-width:0;background:#fff}
.chat-header{padding:14px 20px;border-bottom:1px solid #e9ecef;display:flex;align-items:center;gap:10px;flex-shrink:0}
.badge-subject{background:#e8f0fb;color:#185fa5;font-size:11px;font-weight:500;padding:3px 10px;border-radius:20px}
.chat-header .title{font-size:13px;color:#868e96}
.chat-messages{flex:1;overflow-y:auto;padding:20px;display:flex;flex-direction:column;gap:16px}
.msg-row{display:flex;gap:10px;align-items:flex-end}
.msg-row.user{flex-direction:row-reverse}
.avatar{width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;flex-shrink:0}
.avatar-bot{background:#e8f0fb;color:#185fa5}
.avatar-user{background:#e8f5e9;color:#2e7d32}
.bubble{max-width:72%;padding:10px 14px;font-size:13px;line-height:1.65;color:#212529}
.bubble-bot{background:#f8f9fa;border-radius:4px 14px 14px 14px;max-width:200%}
.bubble-user{background:#185fa5;color:#fff;border-radius:14px 4px 14px 14px;max-width:200%}
.msg-time{font-size:10px;color:#adb5bd;margin:2px 4px 0}
[data-testid="stChatInput"] textarea{border-radius:12px!important;border:1px solid #dee2e6!important;font-family:'Noto Sans KR',sans-serif!important;font-size:13px!important}
[data-testid="stChatInput"] textarea:focus{border-color:#185fa5!important;box-shadow:0 0 0 2px rgba(24,95,165,.12)!important}
[data-testid="stChatInput"] button{background:#185fa5!important;border-radius:10px!important}
[data-testid="stChatInput"]{padding:8px 16px!important}
[data-testid="stBottomBlockContainer"]{padding:0!important;background:transparent!important}
</style>
""", unsafe_allow_html=True)

    # ── 사이드바 ──
    with st.sidebar:
        st.markdown("""
    <div style="padding:20px 16px 14px;border-bottom:1px solid #e9ecef;margin-bottom:4px;">
      <div style="font-size:15px;font-weight:700;color:#185FA5;letter-spacing:-0.3px;">NewLearn</div>
      <div style="font-size:11px;color:#868e96;margin-top:3px;">과목을 선택해 학습을 시작하세요</div>
    </div>
    """, unsafe_allow_html=True)

        for name, _ in SUBJECTS:
            is_active = st.session_state.subject == name
            if st.button(
                f"{'▶' if is_active else '○'}  {name}",
                key=f"btn_{name}",
                type="primary" if is_active else "secondary",
                use_container_width=True
            ):
                st.session_state.subject = name
                st.rerun()

        st.markdown("<hr style='margin:12px 0 8px;border:none;border-top:1px solid #e9ecef'>", unsafe_allow_html=True)

        if st.button("← 홈으로", key="back_home", use_container_width=True):
            st.session_state.page = "landing"
            st.rerun()

    # ── 메인 채팅 영역 ──
    subject = st.session_state.subject
    history = get_history(subject)

    st.markdown(f"""
<div class="app-wrapper">
  <div class="chat-area">
    <div class="chat-header">
      <span class="badge-subject">{subject}</span>
    </div>
    <div class="chat-messages">{render_messages(history)}</div>
  </div>
</div>
""", unsafe_allow_html=True)

    if prompt := st.chat_input(f"{subject}에 대해 질문하세요..."):
        history.append({"role": "user", "content": prompt, "time": now()})
        with st.spinner("답변 생성 중..."):
            response = call_llm(subject, history)
        history.append({"role": "bot", "content": response, "time": now()})
        st.rerun()
