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

if "subject" not in st.session_state:
    st.session_state.subject = "역사"  # HTML active 버튼

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

# ── CSS 주입 (styles.min.css 핵심 규칙 + Streamlit 오버라이드) ──
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap" rel="stylesheet">
<style>
#MainMenu,footer{visibility:hidden}
[data-testid="collapsedControl"]{display:none!important}
[data-testid="stSidebar"][aria-expanded="false"]{transform:none!important;width:220px!important;min-width:220px!important}
[data-testid="collapsedControl"]{display:none!important}
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

# ── 메시지 HTML 변환 ──
def render_messages(history):
    rows = []
    for m in history:
        t, c = m.get("time", ""), m["content"]
        if m["role"] == "bot":
            rows.append(f'<div class="msg-row"><div class="avatar avatar-bot">봇</div><div><div class="bubble bubble-bot">{c}</div><div class="msg-time">{t}</div></div></div>')
        else:
            rows.append(f'<div class="msg-row user"><div class="avatar avatar-user">나</div><div><div class="bubble bubble-user">{c}</div><div class="msg-time" style="text-align:right">{t}</div></div></div>')
    return "\n".join(rows)

# ── LLM 호출 (← 여기를 실제 API로 교체) ──
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

# ── 메인 영역 ──
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
