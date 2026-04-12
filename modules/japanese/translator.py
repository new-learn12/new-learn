"""
비대칭 번역 파이프라인 모듈 (Asymmetric Translation Pipeline)

설계: 보고서 2.2항 & 2.3항 반영
- Task A (일본어 입력): Gemini 문법 검증 → Helsinki(직역) vs Gemini(의역) 대조
- Task B (한국어 입력): 단일 Gemini API로 통합 JSON 응답
- 메모리 최적화: Helsinki 모델은 Task A에서만 @st.cache_resource 지연 로딩
"""

import json
import os
from typing import Dict, List, Optional, Any, Literal
from dataclasses import dataclass
from enum import Enum

try:
    import streamlit as st
except ImportError:
    # Streamlit이 없을 경우 mock 객체 생성
    class MockSt:
        @staticmethod
        def cache_resource(func):
            return func
    st = MockSt()

try:
    from groq import Groq
except ImportError:
    raise ImportError("groq 라이브러리가 필요합니다. (pip install groq)")

try:
    from transformers import pipeline
except ImportError:
    raise ImportError("transformers 라이브러리가 필요합니다.")


class TaskType(str, Enum):
    """번역 작업 타입"""
    JAPANESE_TO_KOREAN = "ja_to_ko"  # Task A
    KOREAN_TO_JAPANESE = "ko_to_ja"  # Task B


class TranslationStyle(str, Enum):
    """번역 스타일"""
    LITERAL = "literal"      # 직역 (Helsinki)
    NATURAL = "natural"      # 의역 (Gemini)
    CASUAL = "casual"        # 캐주얼
    POLITE = "polite"        # 정중체
    BUSINESS = "business"    # 비즈니스
    FEMININE = "feminine"    # 여성스러운
    MASCULINE = "masculine"  # 남성스러운


@dataclass
class GrammarCheckResult:
    """문법 검증 결과"""
    is_correct: bool
    correction: Optional[str] = None
    confidence: float = 1.0


@dataclass
class TranslationResult:
    """번역 결과"""
    original_text: str
    translated_text: str
    style: TranslationStyle
    method: Literal["helsinki", "gemini"]
    confidence: float = 1.0


@dataclass
class ComprehensiveResult:
    """종합 번역 결과 (Task B)"""
    is_correct: bool
    correction: Optional[str]
    translated_text: str
    style_variations: Dict[str, str]
    key_tokens: List[str]
    pronunciation: str


@st.cache_resource
def load_ja_en_pipeline():
    """일본어 -> 영어 모델 로드"""
    try:
        import torch
        device = 0 if torch.cuda.is_available() else -1
        print(f"[Info] Helsinki 모델을 {'GPU' if device == 0 else 'CPU'}로 로드합니다.")

        return pipeline("translation_ja_to_en", model="Helsinki-NLP/opus-mt-ja-en",
                        device=device, src_lang="ja", tgt_lang="en")
    except Exception as e:
        print(f"[Warning] ja-en 로드 실패: {e}")
        return None


@st.cache_resource
def load_en_ko_pipeline():
    """영어 -> 한국어 모델 로드"""
    try:
        import torch
        device = 0 if torch.cuda.is_available() else -1
        print(f"[Info] Helsinki 모델을 {'GPU' if device == 0 else 'CPU'}로 로드합니다.")

        return pipeline("translation_en_to_ko", model="Helsinki-NLP/opus-mt-tc-big-en-ko",
                        device=device, src_lang="en", tgt_lang="ko")
    except Exception as e:
        print(f"[Warning] en-ko 로드 실패: {e}")
        return None


class AsymmetricTranslator:
    """비대칭 번역 파이프라인 - Task A/B에 따라 다른 로직 적용"""

    def __init__(self, groq_api_key: str):
        """
        Args:
            groq_api_key: Gemini API 키
        """
        self.client = Groq(api_key=groq_api_key)

        # 지연 로딩(Lazy Loading)을 위한 파이프라인 변수 초기화
        self._ja_en_pipeline = None
        self._en_ko_pipeline = None

        # Helsinki 모델은 Task A에서만 지연 로딩
        self._helsinki_pipeline = None

    def _get_helsinki_pipelines(self):
        """Helsinki 파이프라인(ja-en, en-ko) getter (지연 로딩)"""
        # 1. 일본어 -> 영어 파이프라인 체크 및 로드
        if self._ja_en_pipeline is None:
            self._ja_en_pipeline = load_ja_en_pipeline()

        # 2. 영어 -> 한국어 파이프라인 체크 및 로드
        if self._en_ko_pipeline is None:
            self._en_ko_pipeline = load_en_ko_pipeline()

        return self._ja_en_pipeline, self._en_ko_pipeline

    def _grammar_check_with_gemini(
            self, text: str, source_lang: str) -> GrammarCheckResult:
        """
        Gemini를 사용한 문법 검증 (Fail-Fast)
        """
        response_text = ""  # 스코프 확보를 위해 미리 초기화
        try:
            prompt = (
                f"다음 {source_lang} 텍스트의 문법을 검증해주세요.\n\n"
                f"응답 형식: JSON 객체\n"
                f"{{\n"
                f'  "is_correct": boolean,\n'
                f'  "correction": string or null,\n'
                f'  "confidence": number\n'
                f"}}\n\n"
                f"텍스트: {text}\n\n"
                f"반드시 JSON 형식으로만 응답하세요."
            )

            response = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}  # JSON Mode 그대로 지원
            )

            # 1. response 또는 response.choices 유효한지 검증
            if not response or not hasattr(
                    response, 'choices') or not response.choices or not response.choices[0].message.content:
                raise ValueError(
                    "Gemini 응답이 비어있거나 유효하지 않습니다. (Safety Filter 등에 의한 차단 가능성)")

            content = response.choices[0].message.content
            response_text = content.strip()

            # JSON 추출 (마크다운 제거)
            if "```json" in response_text:
                response_text = response_text.split(
                    "```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split(
                    "```")[1].split("```")[0].strip()

            result = json.loads(response_text)

            return GrammarCheckResult(
                is_correct=result.get("is_correct", True),
                correction=result.get("correction"),
                confidence=min(float(result.get("confidence", 1.0)), 1.0)
            )

        except (json.JSONDecodeError, ValueError) as e:
            print(f"[Warning] 문법 검증 파싱 실패: {e}")
            if response_text:
                print(f"[Debug] 원문: {response_text[:100]}...")
        except Exception as e:
            print(f"[Warning] 문법 검증 중 예외 발생: {type(e).__name__}: {e}")

        # Fallback: 실패 시 기본값 반환
        return GrammarCheckResult(is_correct=True, confidence=0.0)

    def _translate_with_helsinki(self, text: str) -> str:
        """
        Helsinki-NLP를 사용한 직역 번역 (ja-ko only)

        Args:
            text: 번역할 일본어 텍스트

        Returns:
            번역된 한국어 텍스트
        """
        pipe_ja_en, pipe_en_ko = self._get_helsinki_pipelines()
        if (not pipe_ja_en) or (not pipe_en_ko):
            return "[Helsinki 모델 로드 실패]"

        try:
            # 1단계: 일본어 -> 영어
            en_result = pipe_ja_en(text, max_length=512, num_beams=4)
            en_text = en_result[0]["translation_text"]

            # 2단계: 영어 -> 한국어
            ko_result = pipe_en_ko(
                en_text,
                max_length=512,
                num_beams=4,           # 4개의 후보를 두고 가장 적절한 결과 선택
                early_stopping=True,    # 적절한 시점에서 종료
                no_repeat_ngram_size=2  # 무의미한 반복(예: ....) 방지
            )
            return ko_result[0]["translation_text"]
        except Exception as e:
            print(f"[Warning] Helsinki 번역 실패: {e}")
            return "[번역 실패]"

    def _translate_with_gemini(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        style: TranslationStyle = TranslationStyle.NATURAL
    ) -> str:
        """
        Gemini를 사용한 의역 번역

        Args:
            text: 번역할 텍스트
            source_lang: 원본 언어
            target_lang: 목표 언어
            style: 번역 스타일

        Returns:
            번역된 텍스트
        """
        try:
            style_descriptions = {
                TranslationStyle.NATURAL: "자연스러운 일상 표현으로",
                TranslationStyle.CASUAL: "친근하고 캐주얼한 말투로",
                TranslationStyle.POLITE: "정중하고 예의바른 말투로",
                TranslationStyle.BUSINESS: "비즈니스/공식적인 상황에 맞게",
                TranslationStyle.FEMININE: "여성스러운 부드러운 말투로",
                TranslationStyle.MASCULINE: "남성스러운 직설적인 말투로",
            }

            style_desc = style_descriptions.get(style, "자연스럽게")

            prompt = (
                f"{source_lang} 텍스트를 {target_lang}로 번역해주세요. "
                f"{style_desc} 번역하세요.\n\n"
                f"텍스트: {text}\n\n"
                f"결과는 반드시 **json** 형식으로 출력해야 합니다. "
                f"번역만 출력하세요."
            )

            response = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}  # JSON Mode 그대로 지원
            )
            content = response.choices[0].message.content
            return content.strip() if content else ""

        except Exception as e:
            print(f"[Warning] Gemini 번역 실패: {e}")
            return "[번역 실패]"

    @staticmethod
    def _clean_json_text(response_text: str) -> str:
        text = (response_text or "").strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        if not text.startswith("{"):
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                text = text[start:end + 1]
            else:
                raise ValueError("No valid JSON object found in model response")
        return text

    @staticmethod
    def _normalize_comprehensive_result(raw: Dict[str, Any]) -> Dict[str, Any]:
        translated_text = str(
            raw.get("translated_text")
            or raw.get("translation")
            or raw.get("text")
            or ""
        ).strip()
        if not translated_text:
            raise ValueError("Missing required field: translated_text")

        style_variations = raw.get("style_variations")
        if not isinstance(style_variations, dict):
            style_variations = raw.get("styles") if isinstance(raw.get("styles"), dict) else {}
        required_styles = ["casual", "polite", "business", "feminine", "masculine"]
        normalized_styles = {}
        for style in required_styles:
            value = style_variations.get(style)
            normalized_styles[style] = str(value).strip() if value is not None else ""

        key_tokens = raw.get("key_tokens")
        if isinstance(key_tokens, list):
            normalized_tokens = [str(token).strip() for token in key_tokens if str(token).strip()]
        elif isinstance(key_tokens, str):
            normalized_tokens = [t.strip() for t in key_tokens.split(",") if t.strip()]
        else:
            normalized_tokens = []

        pronunciation = raw.get("pronunciation")
        if pronunciation is None:
            pronunciation = raw.get("romanization", "")

        return {
            "is_correct": bool(raw.get("is_correct", True)),
            "correction": raw.get("correction"),
            "translated_text": translated_text,
            "style_variations": normalized_styles,
            "key_tokens": normalized_tokens,
            "pronunciation": str(pronunciation).strip(),
        }

    def _comprehensive_translate_with_gemini(
            self, text: str) -> ComprehensiveResult:
        """
        Task B: 단일 Gemini API 호출로 종합 번역 결과 생성

        Args:
            text: 한국어 입력 텍스트

        Returns:
            ComprehensiveResult 객체
        """
        try:
            # JSON 스키마를 프롬프트에 직접 포함 (deprecated 라이브러리 호환성)
            schema_description = """
필수 JSON 형식:
{
  "is_correct": boolean (문법이 맞는지),
  "correction": string or null (틀렸다면 수정된 한국어),
  "translated_text": string (기본 일본어 번역),
  "style_variations": {
    "casual": string (캐주얼한 일본어),
    "polite": string (정중한 일본어),
    "business": string (비즈니스 일본어),
    "feminine": string (여성스러운 일본어),
    "masculine": string (남성스러운 일본어)
  },
  "key_tokens": [string] (핵심 어휘/구문 리스트),
  "pronunciation": string (로마자 표기, 헵번식)
}
"""

            prompt = (
                f"다음 한국어 텍스트를 일본어로 번역하고 분석해주세요.\n\n"
                f"{schema_description}\n\n"
                f"요구사항:\n"
                f"- is_correct: 문법이 맞는지 boolean 값\n"
                f"- correction: 틀렸다면 수정된 한국어, 맞다면 null\n"
                f"- translated_text: 자연스러운 일본어 번역\n"
                f"- style_variations: 5가지 스타일별 일본어 번역\n"
                f"- key_tokens: 핵심 어휘나 구문 2-5개 리스트\n"
                f"- pronunciation: 번역된 일본어의 로마자 표기 (헵번식)\n\n"
                f"텍스트: {text}\n\n"
                f"반드시 위 JSON 형식으로만 응답하세요. 다른 텍스트는 포함하지 마세요."
            )

            # google-genai 1.72.0: JSON 응답 강제
            response = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}  # JSON Mode 그대로 지원
            )
            content = response.choices[0].message.content
            response_text = content.strip() if content else ""

            result = json.loads(self._clean_json_text(response_text))
            normalized = self._normalize_comprehensive_result(result)

            return ComprehensiveResult(
                is_correct=normalized["is_correct"],
                correction=normalized["correction"],
                translated_text=normalized["translated_text"],
                style_variations=normalized["style_variations"],
                key_tokens=normalized["key_tokens"],
                pronunciation=normalized["pronunciation"]
            )

        except json.JSONDecodeError as e:
            print(f"[Error] JSON 파싱 실패: {e}")
            print(f"[Debug] 응답 텍스트: {response_text[:200]}...")
        except Exception as e:
            print(f"[Error] 종합 번역 실패: {e}")

        # Fallback 결과
        return ComprehensiveResult(
            is_correct=True,
            correction=None,
            translated_text="[번역 실패]",
            style_variations={
                "casual": "[실패]",
                "polite": "[실패]",
                "business": "[실패]",
                "feminine": "[실패]",
                "masculine": "[실패]"
            },
            key_tokens=[],
            pronunciation="[실패]"
        )

    def translate_japanese_to_korean(self, text: str) -> Dict[str, Any]:
        """
        Task A: 일본어 → 한국어 번역 (비대칭 파이프라인)

        Args:
            text: 일본어 입력 텍스트

        Returns:
            종합 결과 딕셔너리
        """
        # 1. Gemini로 문법 검증 (Fail-Fast)
        grammar_result = self._grammar_check_with_gemini(text, "일본어")

        if not grammar_result.is_correct and grammar_result.correction:
            return {
                "task": "ja_to_ko",
                "original_text": text,
                "grammar_check": {
                    "is_correct": False,
                    "correction": grammar_result.correction,
                    "confidence": grammar_result.confidence
                },
                "translations": [],
                "error": "문법 오류가 발견되었습니다."
            }

        # 2. Helsinki로 직역 번역
        literal_translation = self._translate_with_helsinki(text)

        # 3. Gemini로 의역 번역
        natural_translation = self._translate_with_gemini(
            text, "일본어", "한국어", TranslationStyle.NATURAL
        )

        # 4. 결과 대조 및 종합
        translations = [
            TranslationResult(
                original_text=text,
                translated_text=literal_translation,
                style=TranslationStyle.LITERAL,
                method="helsinki",
                confidence=0.8
            ),
            TranslationResult(
                original_text=text,
                translated_text=natural_translation,
                style=TranslationStyle.NATURAL,
                method="gemini",
                confidence=0.9
            )
        ]

        return {
            "task": "ja_to_ko",
            "original_text": text,
            "grammar_check": {
                "is_correct": grammar_result.is_correct,
                "correction": grammar_result.correction,
                "confidence": grammar_result.confidence
            },
            "translations": [
                {
                    "text": t.translated_text,
                    "style": t.style.value,
                    "method": t.method,
                    "confidence": t.confidence
                }
                for t in translations
            ],
            "recommended": natural_translation  # 의역을 추천
        }

    def translate_korean_to_japanese(self, text: str) -> Dict[str, Any]:
        """
        Task B: 한국어 → 일본어 번역 (단일 Gemini API 호출)

        Args:
            text: 한국어 입력 텍스트

        Returns:
            종합 결과 딕셔너리
        """
        result = self._comprehensive_translate_with_gemini(text)

        return {
            "task": "ko_to_ja",
            "original_text": text,
            "grammar_check": {
                "is_correct": result.is_correct,
                "correction": result.correction
            },
            "translated_text": result.translated_text,
            "style_variations": result.style_variations,
            "key_tokens": result.key_tokens,
            "pronunciation": result.pronunciation
        }

    def translate(self, text: str, task_type: TaskType) -> Dict[str, Any]:
        """
        통합 번역 인터페이스

        Args:
            text: 입력 텍스트
            task_type: 번역 작업 타입

        Returns:
            번역 결과 딕셔너리
        """
        if task_type == TaskType.JAPANESE_TO_KOREAN:
            return self.translate_japanese_to_korean(text)
        elif task_type == TaskType.KOREAN_TO_JAPANESE:
            return self.translate_korean_to_japanese(text)
        else:
            raise ValueError(f"지원하지 않는 task_type: {task_type}")


# ─── 테스트 코드 ───
if __name__ == "__main__":
    from dotenv import load_dotenv

    if os.path.exists(".env"):
        load_dotenv()
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("⚠️  GROQ_API_KEY 환경변수가 설정되지 않았습니다.")
        print("실제 API 테스트를 위해서는 다음 명령어로 설정하세요:")
        print("$env:GROQ_API_KEY = 'your_api_key_here'")
        print("\n구조 검증만 진행합니다...")

        # 구조 검증
        try:
            translator = AsymmetricTranslator(groq_api_key="dummy_key")
            print("✅ 모듈 import 및 클래스 초기화 성공")

            # Task 타입 검증
            print("✅ TaskType enum:", [t.value for t in TaskType])
            print(
                "✅ TranslationStyle enum:", [
                    s.value for s in TranslationStyle])

            # 데이터 클래스 검증
            sample_grammar = GrammarCheckResult(
                is_correct=True, confidence=0.9)
            sample_translation = TranslationResult(
                original_text="test", translated_text="テスト",
                style=TranslationStyle.NATURAL, method="gemini"
            )
            sample_comprehensive = ComprehensiveResult(
                is_correct=True, translated_text="テスト",
                style_variations={"casual": "テスト"}, key_tokens=["test"], pronunciation="tesuto"
            )
            print("✅ 데이터 클래스 생성 성공")

            print("\n🎉 구조 검증 완료! API 키를 설정한 후 실제 테스트를 진행하세요.")

        except Exception as e:
            print(f"❌ 구조 검증 실패: {e}")
            import traceback
            traceback.print_exc()

        exit(0)

    translator = AsymmetricTranslator(groq_api_key=api_key)

    # Task A 테스트 (일본어 → 한국어)
    print("\n[Task A: 일본어 → 한국어]")
    ja_text = "こんにちは、世界！"
    try:
        result_a = translator.translate_japanese_to_korean(ja_text)
        print(f"✅ 입력: {ja_text}")
        print(f"✅ 문법 검증: {result_a['grammar_check']}")
        print(f"✅ 번역 결과 수: {len(result_a['translations'])}")
        if result_a['translations']:
            print(f"✅ 첫 번째 번역: {result_a['translations'][0]['text'][:50]}...")
    except Exception as e:
        print(f"❌ Task A 테스트 실패: {e}")

    # Task B 테스트 (한국어 → 일본어)
    print("\n[Task B: 한국어 → 일본어]")
    ko_text = "안녕하세요, 세계!"
    try:
        result_b = translator.translate_korean_to_japanese(ko_text)
        print(f"✅ 입력: {ko_text}")
        print(f"✅ 문법 검증: {result_b['grammar_check']}")
        print(f"✅ 기본 번역: {result_b['translated_text'][:50]}...")
        print(f"✅ 스타일 변형 수: {len(result_b['style_variations'])}")
        print(f"✅ 핵심 토큰 수: {len(result_b['key_tokens'])}")
        print(f"✅ 발음: {result_b['pronunciation'][:30]}...")
    except Exception as e:
        print(f"❌ Task B 테스트 실패: {e}")

    print("\n🎉 모든 테스트 완료!")
