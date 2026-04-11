"""
llm_handler.py
GitHub Models API를 사용하는 LLM 핸들러.
GitHub Models는 OpenAI 호환 엔드포인트를 제공하므로 openai 라이브러리를 사용.

모델 변경 방법:
    아래 _DEFAULT_MODEL 상수 또는 secrets.toml의 MODEL 값만 바꾸면 됨.
"""

import re
import streamlit as st
from openai import OpenAI, AuthenticationError, RateLimitError
from psychology_rag import build_context_block


# ── 모델 설정 ─────────────────────────────────────────────────────────────
# 모델을 바꾸고 싶을 때: 이 값만 수정하거나 secrets.toml에 MODEL 키를 추가하기.
_DEFAULT_MODEL = "gpt-4.1-mini"

GITHUB_MODELS_ENDPOINT = "https://models.inference.ai.azure.com"


def _get_model() -> str:
    try:
        return st.secrets.get("MODEL", _DEFAULT_MODEL)
    except Exception:
        return _DEFAULT_MODEL


# system prompt ──────────────────────────────────────────────────
_BASE_PROMPTS: dict[str, str] = {
    "심리학": (
        "당신은 심리학 전공 교육 튜터입니다. 대화는 한국어로 진행합니다. "
        "일반인도 쉽게 이해할 수 있도록 전문 용어를 풀어 설명하고, "
        "실생활 예시와 연구 사례를 활용하세요. "
        "아래에 관련 교재 내용이 제공될 경우 이를 우선 참고해 답변하세요. "
        "교재 내용을 넘어서는 질문에는 일반 심리학 지식으로 보완하세요."
    )
}

_DEFAULT_PROMPT = (
    "당신은 한국어로 대화하는 친절하고 전문적인 교육 튜터입니다. "
    "질문을 명확하게 이해한 뒤 쉽고 정확한 답변을 제공하세요."
)


def _build_system_prompt(subject: str, last_user_msg: str) -> str:
    base = _BASE_PROMPTS.get(subject, _DEFAULT_PROMPT)
    if subject == "심리학":
        context = build_context_block(last_user_msg)
        if context:
            return f"{base}\n\n{context}"
    return base


def _build_api_messages(history: list[dict]) -> list[dict]:
    """
    app.py history → OpenAI messages 형식 변환.
    - 웰컴 메시지(time이 빈 첫 bot 메시지) 제외
    - HTML 태그 제거
    """
    api_messages = []
    for msg in history:
        if msg["role"] == "bot" and msg.get("time", "") == "":
            continue
        role = "assistant" if msg["role"] == "bot" else "user"
        content = re.sub(r"<[^>]+>", "", msg["content"]).strip()
        if content:
            api_messages.append({"role": role, "content": content})
    return api_messages


def _text_to_html(text: str) -> str:
    return text.replace("\n", "<br>")


def call_llm(subject: str, history: list[dict]) -> str:
    """
    app.py에서 호출하는 메인 함수.
    GitHub Models API를 통해 응답을 생성하고 HTML 문자열로 반환.
    """
    # GitHub Token 로드
    try:
        github_token = st.secrets["GITHUB_TOKEN"]
    except Exception:
        return (
            "GitHub Token이 설정되지 않았습니다.<br>"
            "<code>.streamlit/secrets.toml</code>에 "
            "<code>GITHUB_TOKEN = \"ghp_...\"</code>을 추가해 주세요."
        )

    # OpenAI 클라이언트 → GitHub Models 엔드포인트로 연결
    client = OpenAI(
        base_url=GITHUB_MODELS_ENDPOINT,
        api_key=github_token,
    )

    model = _get_model()
    last_user_msg = history[-1]["content"] if history else ""
    system_prompt = _build_system_prompt(subject, last_user_msg)
    api_messages = _build_api_messages(history)

    if not api_messages or api_messages[-1]["role"] != "user":
        return "질문을 인식하지 못했습니다. 다시 입력해 주세요."

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                *api_messages,
            ],
            max_tokens=1024,
            temperature=0.7,
        )
        answer = response.choices[0].message.content or ""
        return _text_to_html(answer)

    except AuthenticationError:
        return (
            "GitHub Token이 유효하지 않습니다.<br>"
            "Token에 <b>models:read</b> 권한이 있는지 확인해 주세요."
        )
    except RateLimitError:
        return "요청 한도를 초과했습니다. 잠시 후 다시 시도해 주세요."
    except Exception as e:
        return f"오류가 발생했습니다: {str(e)}"
