import os
import streamlit as st
from dotenv import load_dotenv
from modules.japanese import AsymmetricTranslator, JapaneseTextProcessor, TaskType, OutputFormat

# 기존 B 파일의 get_translator, get_text_processor, run_translation,
# render_translation_result, render_translation_mode 함수들을 그대로 이 곳에 둡니다.
# (단, init_state 로직은 메인 A 파일로 넘깁니다)


def get_japanese_bot_result(history):
    """일본어 전용 Groq API 호출 로직 (B 파일의 call_llm 내부 로직)"""
    if os.path.exists(".env"):
        load_dotenv()
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return "[오류] GROQ_API_KEY가 설정되지 않았습니다."

    try:
        from groq import Groq
        client = Groq(api_key=api_key)

        context = []
        for msg in history[1:]:
            if len(msg["content"]) > 10:
                context.append(msg)
            if len(context) >= 3:
                break
        context = context[-3:] if context else []
        context_text = "\n".join(
            [f"[{msg['role']}]: {msg['content']}" for msg in context])

        prompt = f"""당신은 일본어 학습 튜터입니다. 문법/발음/회화를 간결히 설명하세요.
반드시 **json** 형식으로만 응답해야 합니다.

[이전 대화]
{context_text}

[현재 질문]
{history[-1]['content']}

간결하고 명확한 답변을 300자 이내로 작성하세요."""

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        answer = response.choices[0].message.content
        return answer if answer else "[응답 생성 실패]"
    except Exception as e:
        return f"[API 오류] {str(e)}"


def render_japanese_ui(history, render_messages_func, now_func):
    """일본어 전용 UI 렌더링 (회화/번역 탭 분기)"""
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
        st.markdown(
            """<div class="app-wrapper"><div class="chat-area"><div class="chat-header">
            <span class="badge-subject">일본어</span> <strong>번역 모드</strong>
            </div></div></div>""", unsafe_allow_html=True
        )
        # B 파일의 번역 모드 렌더링 함수 호출
        render_translation_mode("일본어")
        return True  # 번역 모드에서는 자체 chat_input을 쓰므로 메인 프레임워크에 True를 반환해 알림
    else:
        st.markdown(
            f"""<div class="app-wrapper"><div class="chat-area"><div class="chat-header">
            <span class="badge-subject">일본어</span> <strong>회화 모드</strong>
            </div><div class="chat-messages">{render_messages_func(history)}</div></div></div>""",
            unsafe_allow_html=True
        )
        return False  # 회화 모드이므로 메인 프레임워크의 chat_input을 사용하도록 False 반환


def render_translation_mode(subject: str):
    task_labels = {
        TaskType.KOREAN_TO_JAPANESE.value: "한국어 → 일본어",
        TaskType.JAPANESE_TO_KOREAN.value: "일본어 → 한국어",
    }
    current_task = st.session_state.translation_task
    current_index = 0 if current_task == TaskType.KOREAN_TO_JAPANESE.value else 1
    selected = st.radio(
        "번역 방향",
        [task_labels[TaskType.KOREAN_TO_JAPANESE.value],
         task_labels[TaskType.JAPANESE_TO_KOREAN.value]],
        index=current_index,
        horizontal=True,
        key="translation_task_radio",
    )
    selected_task = (
        TaskType.KOREAN_TO_JAPANESE.value
        if selected == task_labels[TaskType.KOREAN_TO_JAPANESE.value]
        else TaskType.JAPANESE_TO_KOREAN.value
    )

    if selected_task != st.session_state.translation_task:
        st.session_state.translation_task = selected_task
        st.session_state.translation_result = {}

    placeholders = {
        TaskType.KOREAN_TO_JAPANESE.value: "한국어 문장을 입력하세요...",
        TaskType.JAPANESE_TO_KOREAN.value: "일본어 문장을 입력하세요...",
    }
    prompt = st.chat_input(
        placeholders[selected_task],
        key="translation_input")
    if prompt:
        st.session_state.translation_result = {}
        with st.spinner("번역 생성 중..."):
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

    render_translation_result(st.session_state.translation_result)


def render_translation_result(result: dict):
    if not result:
        st.info("번역할 문장을 입력해주세요.")
        return

    grammar = result.get("grammar_check", {})
    is_correct = grammar.get("is_correct", True)
    correction = grammar.get("correction")

    if is_correct:
        st.success("문법 점검: 정상")
    else:
        st.warning("문법 점검: 오류 발견")

    if correction is not None:
        st.markdown(f"**수정 제안:** {correction}")

    if result.get("error"):
        st.error(result.get("translated_text", "번역 오류가 발생했습니다."))

    task = result.get("task")
    if task == TaskType.KOREAN_TO_JAPANESE.value:
        translated_text = result.get(
            "translated_text_ruby") or result.get("translated_text", "")
        st.markdown(
            f"<div style='padding:18px 20px;border:1px solid #dbe8f7;border-radius:16px;background:#f8fbff;line-height:1.7;'>{translated_text}</div>",
            unsafe_allow_html=True,
        )

        original_text = result.get(
            "original_text_highlighted") or result.get("original_text", "")
        if original_text:
            st.markdown("**원문 한국어:**", unsafe_allow_html=True)
            st.markdown(original_text, unsafe_allow_html=True)

        with st.expander("추가 보기", expanded=False):
            pronunciation = result.get("pronunciation")
            if pronunciation:
                st.markdown(f"**발음:** {pronunciation}")

            variations = result.get("style_variations_processed") or result.get(
                "style_variations", {})
            if variations:
                for style, text in variations.items():
                    st.markdown(f"**{style}**", unsafe_allow_html=True)
                    st.markdown(text, unsafe_allow_html=True)

            if result.get("key_tokens"):
                st.markdown(f"**핵심 토큰:** {', '.join(result['key_tokens'])}")

    else:
        recommended = result.get("recommended") or ""
        if recommended:
            st.markdown(
                f"<div style='padding:18px 20px;border:1px solid #dbe8f7;border-radius:16px;background:#f8fbff;line-height:1.7;'>{recommended}</div>",
                unsafe_allow_html=True,
            )

        if result.get("original_text"):
            st.markdown("**원문 일본어:**")
            st.markdown(result["original_text"], unsafe_allow_html=True)

        with st.expander("추가 보기", expanded=False):
            for translation in result.get("translations", []):
                style = translation.get("style", "")
                method = translation.get("method", "")
                text = translation.get("text", "")
                st.markdown(f"**{method} / {style}**")
                st.markdown(text, unsafe_allow_html=True)


def get_translator():
    if "translator" in st.session_state and st.session_state.translator is not None:
        return st.session_state.translator

    if os.path.exists(".env"):
        load_dotenv()

    api_key = os.getenv("GROQ_API_KEY")
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
            "translated_text": "[GROQ_API_KEY가 설정되지 않았습니다.]",
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
