import os
import json
import html
import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv
from modules.japanese import AsymmetricTranslator, JapaneseTextProcessor, TaskType, OutputFormat

GITHUB_MODELS_ENDPOINT = "https://models.inference.ai.azure.com"
GITHUB_MODELS_MODEL = "Llama-3.3-70B-Instruct"


def _sanitize_basic_html(text: str, allow_mark: bool = False) -> str:
    escaped = html.escape(text or "")
    if allow_mark:
        escaped = escaped.replace("&lt;mark&gt;", "<mark>")
        escaped = escaped.replace("&lt;/mark&gt;", "</mark>")
    return escaped


def _sanitize_ruby_html(text: str) -> str:
    escaped = _sanitize_basic_html(text, allow_mark=True)
    escaped = escaped.replace("&lt;ruby&gt;", "<ruby>")
    escaped = escaped.replace("&lt;/ruby&gt;", "</ruby>")
    escaped = escaped.replace("&lt;rt&gt;", "<rt>")
    escaped = escaped.replace("&lt;/rt&gt;", "</rt>")
    return escaped


def get_japanese_bot_result(history):
    """일본어 회화 모드용 LLM 호출 로직"""
    if os.path.exists(".env"):
        load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY2", "").strip()
    if not api_key:
        return "[오류] 서버에 OPENAI_API_KEY2가 설정되지 않았습니다. 관리자에게 문의하세요."

    try:
        client = OpenAI(base_url=GITHUB_MODELS_ENDPOINT, api_key=api_key)

        context = []
        for msg in history[1:]:
            if len(msg["content"]) > 10:
                context.append(msg)
            if len(context) >= 3:
                break
        context = context[-3:] if context else []
        context_text = "\n".join(
            [f"[{msg['role']}]: {msg['content']}" for msg in context])

        # 수정된 프롬프트 구성
        prompt = f"""당신은 일본어 학습 튜터입니다. 사용자의 질문에 답변하세요.

### 지시 사항
1. 반드시 아래의 **JSON 스키마**를 엄격히 준수하여 응답하세요.
2. 답변 외에 서론이나 결론 등 다른 텍스트를 포함하지 마세요.
3. JSON 키 값은 반드시 아래 영어 단어를 사용하세요.

### JSON 스키마
- "response": 일본어 문장 (한자/가나 혼용)
- "meaning": 한국어 뜻
- "pronunciation": 한글 독음 (예: 콘니치와)
- "explanation": 문법이나 상황에 대한 간결한 설명

### 응답 예시
{{
  "response": "こんにちは",
  "meaning": "안녕 / 안녕하세요",
  "pronunciation": "콘니치와",
  "explanation": "낮에 사용하는 일반적인 인사말입니다."
}}

### 이전 대화 Context
{context_text}

### 사용자 질문
{history[-1]['content']}
"""

        response = client.chat.completions.create(
            model=GITHUB_MODELS_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        answer = response.choices[0].message.content
        return format_japanese_answer_to_html(answer) if answer else "[응답 생성 실패]"
    except Exception as e:
        return f"[API 오류] {str(e)}"


def format_japanese_answer_to_html(answer_str: str) -> str:
    """JSON 형태의 답변 문자열을 파싱하여 깔끔한 HTML로 변환합니다."""
    try:
        # JSON 문자열 파싱
        data = json.loads(answer_str)

        # 각 필드 추출 (안전하게 가져오기 위해 get 사용)
        response = html.escape(str(data.get("response", "")))
        meaning = html.escape(str(data.get("meaning", "")))
        pronunciation = html.escape(str(data.get("pronunciation", "")))
        explanation = html.escape(str(data.get("explanation", "")))

        # HTML 템플릿 작성 (인라인 CSS 사용)
        html_content = f"""
        <div style="padding: 16px; border: 1px solid #dbe8f7; border-radius: 12px; background-color: #f8fbff; font-family: sans-serif; line-height: 1.6;">
            <div style="font-size: 1.2em; font-weight: bold; color: #1e3a8a; margin-bottom: 8px;">
                🇯🇵 {response}
            </div>
            <div style="margin-bottom: 4px;">
                <span style="background-color: #e0f2fe; color: #0369a1; padding: 2px 6px; border-radius: 4px; font-size: 0.85em; font-weight: bold; margin-right: 6px;">의미</span>
                <span>{meaning}</span>
            </div>
            <div style="margin-bottom: 12px;">
                <span style="background-color: #f3e8ff; color: #7e22ce; padding: 2px 6px; border-radius: 4px; font-size: 0.85em; font-weight: bold; margin-right: 6px;">발음</span>
                <span>{pronunciation}</span>
            </div>
            <hr style="border: none; border-top: 1px dashed #cbd5e1; margin: 10px 0;">
            <div style="color: #475569; font-size: 0.95em;">
                <strong>💡 설명:</strong> {explanation}
            </div>
        </div>
        """
        return html_content
    except json.JSONDecodeError:
        # JSON 형식이 아닌 일반 텍스트로 왔을 경우를 대비한 예외 처리
        return f"<div style='padding: 16px;'>{html.escape(str(answer_str))}</div>"


def render_japanese_ui(history, render_messages_func):
    """일본어 전용 UI를 렌더링하고 메인 입력창 스킵 여부를 반환합니다.

    Args:
        history: 현재 과목의 대화 히스토리 목록
        render_messages_func: 회화 모드 메시지 HTML 렌더링 함수

    Returns:
        bool: 번역 모드(True)면 메인 chat_input을 스킵하고, 회화 모드(False)면 사용합니다.
    """
    tab_col1, tab_col2, _ = st.columns([1, 1, 4])

    # 탭 버튼 UI
    if tab_col1.button("회화 모드", key="btn_chat_mode",
                       type="primary" if not st.session_state.jp_translation_mode else "secondary", use_container_width=True):
        st.session_state.jp_translation_mode = False
        st.rerun()

    if tab_col2.button("번역 모드", key="btn_translation_mode",
                       type="primary" if st.session_state.jp_translation_mode else "secondary", use_container_width=True):
        st.session_state.jp_translation_mode = True
        st.rerun()

    # 모드에 따른 렌더링 분기
    if st.session_state.jp_translation_mode:
        # 1. 위젯 영역 및 로직 처리
        # render_translation_mode 내부에서 st.radio 등을 실행하고
        # 최종 '결과 HTML 문자열'만 리턴받습니다.
        result_html = render_translation_mode()

        # 2. UI 렌더링 (HTML 프레임워크 안에 결과 주입)
        st.html(
            f"""
            <div class="app-wrapper">
                    <div class="chat-area">
                        <div class="chat-header">
                            <span class="badge-subject">일본어</span> <strong>번역 모드</strong>
                        </div>
                        <div class="chat-messages">
                            {result_html}
                        </div>
                    </div>
                </div>
                """
        )
        return True
    else:
        st.markdown(
            f"""<div class="app-wrapper"><div class="chat-area"><div class="chat-header">
            <span class="badge-subject">일본어</span> <strong>회화 모드</strong>
            </div><div class="chat-messages">{render_messages_func(history)}</div></div></div>""",
            unsafe_allow_html=True
        )
        return False  # 회화 모드이므로 메인 프레임워크의 chat_input을 사용하도록 False 반환


def render_translation_mode():
    """번역 모드 입력/실행을 처리하고 결과 영역에 삽입할 HTML을 반환합니다.

    Returns:
        str: 번역 결과 영역에 표시할 HTML 문자열
    """
    task_labels = {
        TaskType.KOREAN_TO_JAPANESE.value: "한국어 → 일본어",
        TaskType.JAPANESE_TO_KOREAN.value: "일본어 → 한국어",
    }
    current_task = st.session_state.translation_task
    current_index = 0 if current_task == TaskType.KOREAN_TO_JAPANESE.value else 1
    # 1. 라디오 버튼 렌더링
    selected = st.radio(
        "번역 방향",
        [task_labels[TaskType.KOREAN_TO_JAPANESE.value],
         task_labels[TaskType.JAPANESE_TO_KOREAN.value]],
        index=current_index,
        horizontal=True,
        key="translation_task_radio",
    )
    # 2. 선택된 태스크 매핑
    selected_task = (
        TaskType.KOREAN_TO_JAPANESE.value
        if selected == task_labels[TaskType.KOREAN_TO_JAPANESE.value]
        else TaskType.JAPANESE_TO_KOREAN.value
    )

    # 3. 중요: 태스크가 변경되었다면 세션 상태를 업데이트하고 즉시 리런!
    if selected_task != st.session_state.translation_task:
        st.session_state.translation_task = selected_task
        st.session_state.translation_result = {}  # 이전 결과 삭제

    # 4. 입력창 처리
    placeholders = {
        TaskType.KOREAN_TO_JAPANESE.value: "한국어 문장을 입력하세요...",
        TaskType.JAPANESE_TO_KOREAN.value: "일본어 문장을 입력하세요...",
    }
    prompt = st.chat_input(
        placeholders[selected_task],
        key="translation_input")
    if prompt:
        st.session_state.translation_result = {}
        with st.spinner("번역 생성 중...💭"):
            result = run_translation(prompt, selected_task)
            if selected_task == TaskType.KOREAN_TO_JAPANESE.value:
                processor = get_text_processor()
                result = processor.process_comprehensive_result(
                    result,
                    OutputFormat.HTML,
                    include_ruby=True,
                    highlight_tokens=True,
                )
        st.session_state.translation_result = result
        st.rerun()

    # 5. 결과 HTML 반환 (render_japanese_ui의 chat-messages div 안으로 들어감)
    return build_translation_result_html(st.session_state.translation_result)


def build_translation_result_html(result: dict) -> str:
    """번역 결과를 하나의 완성된 HTML 문자열로 조립합니다."""
    if not result:
        return "<div style='color:#888; text-align:center; padding:20px;'>번역할 문장을 입력해주세요.</div>"

    html_parts = []

    # 1. 문법 점검 섹션 (Badge 스타일)
    grammar = result.get("grammar_check", {})
    if grammar.get("is_correct", True):
        html_parts.append(
            "<div style='color:#059669; background:#ecfdf5; padding:8px; border-radius:8px; margin-bottom:10px; font-size:0.9em;'>✅ 문법 점검: 정상</div>")
    else:
        safe_correction = html.escape(str(grammar.get("correction", "")))
        html_parts.append(
            f"<div style='color:#d97706; background:#fffbeb; padding:8px; border-radius:8px; margin-bottom:10px; font-size:0.9em;'>⚠️ 문법 점검: 오류 발견 ({safe_correction})</div>")

    # 2. 메인 번역 결과 카드
    task = result.get("task")

    # [한국어 -> 일본어]
    if task == TaskType.KOREAN_TO_JAPANESE.value:
        translated = result.get(
            "translated_text_ruby") or result.get("translated_text", "")
        original = result.get(
            "original_text_highlighted") or result.get("original_text", "")
        safe_translated = _sanitize_ruby_html(str(translated))
        safe_original = _sanitize_basic_html(str(original), allow_mark=True)
        safe_pronunciation = html.escape(str(result.get("pronunciation", "")))
        safe_tokens = ", ".join(html.escape(str(t)) for t in result.get("key_tokens", []))

        html_parts.append(f"""
            <div style='padding:20px; border:1px solid #dbe8f7; border-radius:16px; background:#f8fbff; margin-bottom:15px;'>
                <div style='font-size:1.25em; line-height:1.8; color:#1e293b;'>{safe_translated}</div>
                <div style='margin-top:10px; font-size:0.9em; color:#64748b; border-top:1px dashed #cbd5e1; padding-top:8px;'>
                    <strong>원문:</strong> {safe_original}
                </div>
            </div>
        """)

        # 추가 보기 (st.expander 대체)
        html_parts.append(f"""
            <details style='cursor:pointer; font-size:0.9em; color:#475569; background:#f1f5f9; padding:10px; border-radius:8px;'>
                <summary style='font-weight:bold;'>🔍 상세 분석 보기</summary>
                <div style='margin-top:10px; padding-left:5px;'>
                    <p><strong>발음:</strong> {safe_pronunciation}</p>
                    <p><strong>핵심 단어:</strong> {safe_tokens}</p>
                </div>
            </details>
        """)

    # [일본어 -> 한국어]
    else:
        recommended = result.get("recommended") or ""
        if recommended:
            safe_recommended = _sanitize_basic_html(str(recommended), allow_mark=True)
            html_parts.append(f"""
                <div style='padding:18px 20px; border:1px solid #dbe8f7; border-radius:16px; background:#f8fbff; line-height:1.7; margin-bottom:15px;'>
                    {safe_recommended}
                </div>
            """)

        original_text = result.get("original_text")
        if original_text:
            safe_original_text = html.escape(str(original_text))
            html_parts.append(
                f"<div style='margin-bottom:10px;'><strong>원문 일본어:</strong><br>{safe_original_text}</div>")

        # st.expander를 대체할 추가 보기 내용 조립
        translations_html = ""
        for translation in result.get("translations", []):
            style = html.escape(str(translation.get("style", "")))
            method = html.escape(str(translation.get("method", "")))
            text = html.escape(str(translation.get("text", "")))
            translations_html += f"<div style='margin-bottom:12px;'><strong>{method} / {style}</strong><br>{text}</div>"

        if translations_html:
            html_parts.append(f"""
                <details style='cursor:pointer; font-size:0.9em; color:#475569; background:#f1f5f9; padding:10px; border-radius:8px;'>
                    <summary style='font-weight:bold;'>🔍 추가 보기</summary>
                    <div style='margin-top:10px; padding-left:5px;'>
                        {translations_html}
                    </div>
                </details>
            """)

    return "".join(html_parts)


def get_translator():
    if "translator" in st.session_state and st.session_state.translator is not None:
        return st.session_state.translator

    if os.path.exists(".env"):
        load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY2", "").strip() or os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None

    try:
        st.session_state.translator = AsymmetricTranslator(api_key)
        return st.session_state.translator
    except Exception as e:
        st.session_state.translator = None
        st.session_state.translator_error = str(e)
        return None


def get_text_processor():
    if "japanese_processor" in st.session_state and st.session_state.japanese_processor is not None:
        return st.session_state.japanese_processor

    processor = JapaneseTextProcessor()
    st.session_state.japanese_processor = processor
    return processor


def run_translation(input_text: str, task_value: str) -> dict:
    translator = get_translator()
    if translator is None:
        return {
            "task": task_value,
            "original_text": input_text,
            "grammar_check": {"is_correct": False, "correction": None},
            "translated_text": "[OPENAI_API_KEY2가 설정되지 않았습니다.]",
            "style_variations": {},
            "key_tokens": [],
            "pronunciation": "",
            "error": "missing_api_key",
        }

    try:
        task_type = TaskType(task_value)
        return translator.translate(input_text, task_type)
    except Exception as e:
        print(str(e))
        return {
            "task": task_value,
            "original_text": input_text,
            "grammar_check": {"is_correct": False, "correction": None},
            "translated_text": "[번역 중 오류가 발생했습니다.]",
            "style_variations": {},
            "key_tokens": [],
            "pronunciation": "",
            "error": str(e),
        }
