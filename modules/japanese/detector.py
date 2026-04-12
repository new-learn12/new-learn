"""
하이브리드 언어 감지 모듈 (Hybrid Language Detection)

설계: 보고서 2.1항 반영
- 1단계 (Regex): 한글/가나 판별로 1차 분류 (속도 최우선)
- 2단계 (Library): langdetect으로 2차 검증
- 3단계 (Fallback): 3글자 이하 또는 모호할 때만 Gemini 1.5 Flash에 언어 판별 위임
"""

import re
from typing import Tuple, Literal
from enum import Enum

try:
    from langdetect import detect_langs, LangDetectException
except ImportError:
    raise ImportError(
        "langdetect 라이브러리가 필요합니다. pip install langdetect 실행해주세요.")

try:
    from openai import OpenAI
except ImportError:
    raise ImportError("openai 라이브러리가 필요합니다. (pip install openai)")

GITHUB_MODELS_ENDPOINT = "https://models.inference.ai.azure.com"
GITHUB_MODELS_MODEL = "gpt-4.1-mini"


class Language(str, Enum):
    """지원 언어 코드 (ISO 639-1)"""
    KOREAN = "ko"
    JAPANESE = "ja"
    ENGLISH = "en"
    CHINESE = "zh"
    OTHER = "other"


class DetectionResult:
    """언어 감지 결과"""

    def __init__(
        self,
        language: Language,
        confidence: float,
        method: Literal["regex", "langdetect", "gemini"],
        original_text: str
    ):
        self.language = language
        self.confidence = confidence
        self.method = method
        self.original_text = original_text

    def __repr__(self) -> str:
        return (
            f"DetectionResult(language={self.language.value}, "
            f"confidence={self.confidence:.2f}, method={self.method})"
        )


class HybridLanguageDetector:
    """하이브리드 언어 감지기 - 3단계 파이프라인"""

    # 정규표현식 패턴 정의 (개별 문자 매칭을 위해 + 제거)
    HANGUL_PATTERN = re.compile(r"[\uac00-\ud7af\u1100-\u11ff\u3130-\u318f]")
    HIRAGANA_PATTERN = re.compile(r"[\u3040-\u309f]")
    KATAKANA_PATTERN = re.compile(r"[\u30a0-\u30ff]")
    KANJI_PATTERN = re.compile(r"[\u4e00-\u9fff]")

    def __init__(self, llm_api_key: str | None = None):
        """
        Args:
            llm_api_key: GitHub Models API 키 (OPENAI_API_KEY2 또는 OPENAI_API_KEY, 없으면 2단계까지만 동작)
        """
        if llm_api_key:
            self.client = OpenAI(
                base_url=GITHUB_MODELS_ENDPOINT,
                api_key=llm_api_key,
            )

    def _step1_regex_detection(
            self, text: str) -> Tuple[Language | None, float]:
        """
        단계 1: 정규표현식을 사용한 빠른 1차 분류

        Args:
            text: 입력 텍스트

        Returns:
            (감지된 언어, 신뢰도) 튜플. 명확하지 않으면 (None, 0.0)
        """
        if not text:
            return None, 0.0

        # 각 문자열 타입별 문자 개수 계산
        hangul_chars = len(self.HANGUL_PATTERN.findall(text))
        hiragana_chars = len(self.HIRAGANA_PATTERN.findall(text))
        katakana_chars = len(self.KATAKANA_PATTERN.findall(text))
        kanji_chars = len(self.KANJI_PATTERN.findall(text))

        total_cjk = hangul_chars + hiragana_chars + katakana_chars + kanji_chars

        if total_cjk == 0:
            # CJK 문자가 없으면 Regex로 판별 불가
            return None, 0.0

        # 한글이 60% 이상이고, 일본어 요소(히라가나+카타카나+한자)가 30% 미만이면 Korean
        japanese_elements = hiragana_chars + katakana_chars + kanji_chars
        if hangul_chars >= total_cjk * 0.6 and japanese_elements < total_cjk * 0.3:
            confidence = hangul_chars / total_cjk
            return Language.KOREAN, min(confidence, 1.0)

        # 일본어 요소(히라가나+카타카나+한자)가 40% 이상이면 Japanese
        if japanese_elements >= total_cjk * 0.4:
            # 한자만 있는 경우도 일본어로 간주 (중국어와 구분)
            if kanji_chars > 0 and (hiragana_chars + katakana_chars) == 0:
                # 한자만 있는 경우: 짧은 텍스트는 일본어로, 긴 텍스트는 중국어 가능성 고려
                if len(text) <= 5:
                    confidence = 0.8  # 짧은 한자는 일본어로 가정
                    return Language.JAPANESE, confidence
                else:
                    # 긴 한자 텍스트는 중국어로 가정 (임시)
                    confidence = 0.6
                    return Language.CHINESE, confidence
            else:
                confidence = japanese_elements / total_cjk
            return Language.JAPANESE, min(confidence, 1.0)

        # 한글과 일본어 요소가 섞여 있는 경우 (혼합 텍스트)
        if hangul_chars > 0 and japanese_elements > 0:
            # 어느 쪽이 더 많은지 비교
            if hangul_chars > japanese_elements:
                confidence = hangul_chars / total_cjk * 0.8  # 혼합 페널티
                return Language.KOREAN, confidence
            else:
                confidence = japanese_elements / total_cjk * 0.8  # 혼합 페널티
                return Language.JAPANESE, confidence

        # 명확하지 않음 - 다음 단계로 넘김
        return None, 0.0

    def _step2_langdetect_validation(
            self, text: str) -> Tuple[Language, float]:
        """
        단계 2: langdetect 라이브러리를 사용한 2차 검증

        Args:
            text: 입력 텍스트

        Returns:
            (감지된 언어, 신뢰도) 튜플
        """
        try:
            # 다중 언어 확률 반환
            probabilities = detect_langs(text)

            if not probabilities:
                return Language.OTHER, 0.0

            top_lang = probabilities[0]
            iso_code = top_lang.lang
            confidence = top_lang.prob

            # ISO 639-1 코드를 Language enum으로 변환
            try:
                detected_language = Language(iso_code)
            except ValueError:
                detected_language = Language.OTHER

            return detected_language, confidence

        except LangDetectException:
            # 텍스트가 너무 짧거나 감지 실패
            return Language.OTHER, 0.0

    def _step3_gemini_fallback(self, text: str) -> Tuple[Language, float]:
        """
        단계 3: Gemini 1.5 Flash를 사용한 정확한 언어 판별 (Fallback)

        Args:
            text: 입력 텍스트

        Returns:
            (감지된 언어, 신뢰도) 튜플
        """

        try:
            prompt = (
                f"다음 텍스트의 언어를 ISO 639-1 포맷(예: ko, ja, en, zh)으로 판별해줘. "
                f"필수: JSON 형식으로 {{\"language\": \"ISO code\", \"confidence\": 0.0~1.0}} 로만 응답.\n\n"
                f"텍스트: {text}"
            )

            response = self.client.chat.completions.create(
                model=GITHUB_MODELS_MODEL,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}  # JSON Mode 그대로 지원
            )
            content = response.choices[0].message.content
            response_text = content.strip() if content else ""

            # 만약 response_text가 비어있다면 바로 Fallback으로 넘어가도록 처리
            if not response_text:
                print("[Warning] API 응답 내용이 비어있습니다.")
                return Language.OTHER, 0.0

            # JSON 파싱 시도
            import json
            try:
                result = json.loads(response_text)
                lang_code = result.get("language", "other")
                confidence = float(result.get("confidence", 0.5))

                try:
                    detected_language = Language(lang_code)
                except ValueError:
                    detected_language = Language.OTHER

                return detected_language, min(confidence, 1.0)

            except json.JSONDecodeError:
                # JSON 파싱 실패 시 텍스트에서 직접 추출 시도
                response_lower = response_text.lower()

                # 우선순위: ko > ja > zh > en
                if "ko" in response_lower or "korean" in response_lower or "한국" in response_lower:
                    return Language.KOREAN, 0.8
                elif "ja" in response_lower or "japanese" in response_lower or "일본" in response_lower:
                    return Language.JAPANESE, 0.8
                elif "zh" in response_lower or "chinese" in response_lower or "중국" in response_lower:
                    return Language.CHINESE, 0.8
                elif "en" in response_lower or "english" in response_lower or "영어" in response_lower:
                    return Language.ENGLISH, 0.8
                else:
                    # 그래도 판별 실패 시 OTHER
                    return Language.OTHER, 0.5

        except Exception as e:
            print(f"[Warning] Gemini API 호출 실패: {e}")
            return Language.OTHER, 0.0

    def detect(self, text: str, force_gemini: bool = False) -> DetectionResult:
        """
        하이브리드 언어 감지 - 3단계 파이프라인 실행

        Args:
            text: 입력 텍스트
            force_gemini: True면 항상 Gemini를 사용 (테스트/디버깅용)

        Returns:
            DetectionResult 객체
        """
        text = text.strip()

        if not text:
            return DetectionResult(
                language=Language.OTHER,
                confidence=0.0,
                method="regex",
                original_text=text
            )

        # Gemini 강제 모드
        if force_gemini:
            language, confidence = self._step3_gemini_fallback(text)
            return DetectionResult(
                language=language,
                confidence=confidence,
                method="gemini",
                original_text=text
            )

        # 단계 1: Regex 기반 빠른 판별
        lang_regex, conf_regex = self._step1_regex_detection(text)
        if lang_regex and conf_regex >= 0.8:  # 신뢰도 80% 이상이면 즉시 반환
            return DetectionResult(
                language=lang_regex,
                confidence=conf_regex,
                method="regex",
                original_text=text
            )

        # 단계 2: langdetect 기반 검증
        lang_ld, conf_ld = self._step2_langdetect_validation(text)
        if conf_ld >= 0.8:  # 신뢰도 80% 이상이면 반환
            return DetectionResult(
                language=lang_ld,
                confidence=conf_ld,
                method="langdetect",
                original_text=text
            )

        # 단계 3: Fallback - 3글자 이하 또는 모호한 경우 Gemini 호출
        should_use_gemini = (
            len(text) <= 3  # 3글자 이하
            or conf_ld <= 0.7  # langdetect 신뢰도 낮음 (모호함)
        )

        if should_use_gemini:
            lang_gemini, conf_gemini = self._step3_gemini_fallback(text)
            return DetectionResult(
                language=lang_gemini,
                confidence=conf_gemini,
                method="gemini",
                original_text=text
            )

        # Gemini 호출 불가능한 경우 langdetect 결과 반환
        return DetectionResult(
            language=lang_ld,
            confidence=conf_ld,
            method="langdetect",
            original_text=text
        )

    def batch_detect(
        self,
        texts: list[str]
    ) -> list[DetectionResult]:
        """
        여러 텍스트를 한 번에 감지

        Args:
            texts: 텍스트 리스트

        Returns:
            DetectionResult 리스트
        """
        return [self.detect(text) for text in texts]


# ─── 테스트 코드 ───
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    if os.path.exists(".env"):
        load_dotenv()

    # Gemini API 키 로드 (환경변수에서)
    api_key = os.getenv("OPENAI_API_KEY2", "").strip() or os.getenv("OPENAI_API_KEY", "").strip()

    detector = HybridLanguageDetector(llm_api_key=api_key)

    # 테스트 케이스
    test_texts = [
        # 기본 케이스
        "こんにちは",  # 일본어 (히라가나)
        "안녕하세요",  # 한국어
        "Hello",  # 영어

        # 한자 포함 케이스
        "こんにちは世界",  # 일본어 (히라가나 + 한자)
        "日本",  # 한자만 (일본어로 판별되어야 함)
        "中国",  # 한자만 (중국어 가능성)

        # 혼합 텍스트
        "こんにちは안녕",  # 일본어 + 한국어 혼합
        "안녕하세요こんにちは",  # 한국어 + 일본어 혼합

        # 짧은 텍스트 (Gemini fallback)
        "Hi",  # 영어 (3글자 이하)
        "あ",  # 히라가나 1글자
        "가",  # 한글 1글자

        # 카타카나 케이스
        "コンニチハ",  # 카타카나
        "カフェ",  # 혼합 (히라가나 + 카타카나)

        # 모호한 케이스
        "test",  # 영어지만 langdetect로 검증 필요
        "123",  # 숫자 (OTHER)
        "",  # 빈 문자열
    ]

    print("[Hybrid Language Detection Test]\n")
    for text in test_texts:
        result = detector.detect(text)
        print(f"Text: {text:15} → {result}")
