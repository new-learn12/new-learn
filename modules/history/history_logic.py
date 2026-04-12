"""
history_logic.py
한국 근대사 교육 챗봇 로직 모듈

NewLearn app.py에서 다음과 같이 임포트해서 사용합니다:
    from history_logic import get_history_bot_result

call_llm() 함수 내 역사(歷史) 과목 분기에 연결하면 됩니다.
"""

from transformers.utils import logging as hf_logging
from transformers import pipeline
import torch
import re
import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"


hf_logging.disable_progress_bar()
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

# ─── 설정 ───────────────────────────────────────────────────────────────────
MODEL_ID = "Qwen/Qwen2.5-3B-Instruct"          # 메모리에 맞게 변경 가능
DATA_FILE = "korean_modern_history_chatbot_ready.txt"  # 학습 데이터 파일 경로
TOP_K = 3                                      # 검색할 상위 섹션 수
MAX_TOKENS = 512                                    # 최대 생성 토큰
# ────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """당신은 한국 근대사 전문 교육 챗봇입니다.
아래 [참고 자료]를 바탕으로 학생의 질문에 친절하고 정확하게 답변하세요.

응답 규칙:
응답 규칙:
1. 반드시 한국어(한글)로만 답변합니다.
2. 한자를 절대 출력하지 않습니다. 괄호 안에도 한자 금지입니다.
3. [참고 자료]에 있는 내용만을 바탕으로 답변합니다. 자료에 없는 내용은 추가하지 않습니다.
4. 모르는 내용은 '이 부분은 제 자료에 없습니다'라고 말합니다.
5. 중학생이 이해하기 쉽게 기 - 승 - 전 - 결 순서로 설명합니다.
6. 어려운 역사 용어는 바로 뒤에 쉬운 말로 풀어 설명합니다. 예: "통리기무아문 — 외교·군사 담당 기관"
7. 선생님이 학생에게 이야기하는 말투로 작성합니다.
8. 4문장 이상으로 답변합니다."""


# ─── 모델 & 데이터 지연 로드 (처음 호출 시 한 번만 초기화) ─────────────────
_pipe = None
_sections = None


def _remove_hanja(text):
    """생성된 텍스트에서 한자(CJK)를 제거합니다."""
    import re as _re
    return _re.sub(r"[一-鿿㐀-䶿豈-﫿]+", "", text)


def _load_resources():
    """모델과 역사 데이터를 처음 사용 시 한 번만 로드합니다."""
    global _pipe, _sections

    if _sections is None:
        _sections = _load_history_data(DATA_FILE)

    if _pipe is None:
        device = 0 if torch.cuda.is_available() else -1
        dtype = torch.float16 if device == 0 else torch.float32
        _pipe = pipeline(
            task="text-generation",
            model=MODEL_ID,
            device=device,
            trust_remote_code=True,
            torch_dtype=dtype,
        )


def _load_history_data(file_path: str) -> list:
    """한국근대사 텍스트 파일을 읽어 섹션 단위 리스트로 반환합니다."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            raw_text = f.read()
    except FileNotFoundError:
        return []

    sections = re.split(r"(?=###)", raw_text)
    parsed = []
    for section in sections:
        section = section.strip()
        if not section or not section.startswith("#"):
            continue

        title_match = re.match(r"#{2,3}\s+(.+)", section)
        title = title_match.group(1).strip() if title_match else "(제목 없음)"

        kw_match = re.search(r"주요 키워드[:\s]+(.+)", section)
        keywords = [k.strip()
                    for k in kw_match.group(1).split(",")] if kw_match else []

        q_match = re.search(r"예상 질문[:\s]+(.+)", section)
        questions = [q.strip()
                     for q in q_match.group(1).split("/")] if q_match else []

        parsed.append({
            "title": title,
            "content": section,
            "keywords": keywords,
            "questions": questions,
        })
    return parsed


def _retrieve_context(user_query: str, sections: list, top_k: int = 2) -> str:
    """사용자 질문과 가장 관련 있는 섹션을 검색하여 컨텍스트로 반환합니다."""
    query_tokens = set(re.findall(r"[가-힣a-zA-Z0-9]{2,}", user_query))

    scores = []
    for sec in sections:
        title_tokens = set(re.findall(r"[가-힣a-zA-Z0-9]{2,}", sec["title"]))
        kw_tokens = set(
            re.findall(
                r"[가-힣a-zA-Z0-9]{2,}",
                " ".join(
                    sec["keywords"])))
        q_tokens = set(
            re.findall(
                r"[가-힣a-zA-Z0-9]{2,}",
                " ".join(
                    sec["questions"])))

        score = (
            len(query_tokens & title_tokens) * 3
            + len(query_tokens & kw_tokens) * 2
            + len(query_tokens & q_tokens) * 1
        )
        scores.append((score, sec))

    scores.sort(key=lambda x: x[0], reverse=True)
    top_sections = [sec for score, sec in scores[:top_k] if score > 0]

    if not top_sections:
        return "이 챗봇은 한국 근대사(1860년대~1945년) 전반을 다룹니다."

    parts = []
    for sec in top_sections:
        core_match = re.search(
            r"핵심 포인트:[\s\S]+?(?=주요 키워드|예상 질문|$)", sec["content"]
        )
        core_text = core_match.group(0).strip(
        ) if core_match else sec["content"][:300]
        parts.append(f"[{sec['title']}]\n{core_text}")

    return "\n\n".join(parts)


# ─── 공개 API ────────────────────────────────────────────────────────────────

def get_history_bot_result(
        user_query: str,
        chat_history: list = None) -> tuple:
    """
    한국 근대사 질문에 대한 QWEN 모델의 답변을 반환합니다.

    Args:
        user_query  : 사용자 질문 문자열
        chat_history: app.py histories 형식 [{"role": "bot"/"user", "content": ..., "time": ...}, ...]

    Returns:
        str: 모델 응답 텍스트 (HTML 태그 없는 순수 텍스트)
    """
    if chat_history is None:
        chat_history = []

    # 처음 호출 시 모델 & 데이터 로드
    _load_resources()

    # RAG 컨텍스트 검색
    context = _retrieve_context(user_query, _sections, top_k=TOP_K)

    # 메시지 구성
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # 최근 대화 이력 (최대 8턴)
    for turn in chat_history[-8:]:
        role = "assistant" if turn.get("role") == "bot" else "user"
        content = re.sub(r"<[^>]+>", "", turn.get("content", ""))  # HTML 태그 제거
        messages.append({"role": role, "content": content})

    messages.append({
        "role": "user",
        "content": f"[참고 자료]\n{context}\n\n[질문]\n{user_query}",
    })

    # 모델 추론
    outputs = _pipe(
        messages,
        max_new_tokens=MAX_TOKENS,
        temperature=0.3,
        do_sample=True,
        repetition_penalty=1.2,
        return_full_text=False,
    )

    generated = outputs[0]["generated_text"]

    # 리스트 형식 처리 (일부 모델 버전에서 다르게 반환)
    if isinstance(generated, list):
        for msg in reversed(generated):
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                _remove_hanja(msg.get("content", "").strip())
        return _remove_hanja(str(generated[-1]).strip()), None

    return _remove_hanja(str(generated).strip()), None
