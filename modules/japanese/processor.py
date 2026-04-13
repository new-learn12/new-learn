"""
후처리 및 하이라이팅 모듈 (Post-processing & Highlighting)

설계: 보고서 2.4항 반영
- pykakasi를 사용하여 한자 위에 히라가나를 올리는 HTML <ruby> 태그 생성
- Gemini가 반환한 핵심 토큰 리스트를 순회하며 원문에 마크다운 ** 또는 HTML <mark> 처리
- fugashi를 활용한 형태소 분석 기반 토큰 매칭
"""

import re
from typing import List, Dict, Any
from enum import Enum

try:
    import pykakasi
except ImportError:
    raise ImportError("pykakasi 라이브러리가 필요합니다. pip install pykakasi 실행해주세요.")

try:
    import fugashi
except ImportError:
    print("[Warning] fugashi 라이브러리가 설치되지 않았습니다. 형태소 분석 기능이 제한됩니다.")
    fugashi = None


class OutputFormat(str, Enum):
    """출력 형식"""
    MARKDOWN = "markdown"  # **bold** 형식
    HTML = "html"          # <mark> 태그
    PLAIN = "plain"        # 일반 텍스트


class JapaneseTextProcessor:
    """일본어 텍스트 후처리 및 하이라이팅 프로세서"""

    def __init__(self):
        """프로세서 초기화"""
        # pykakasi 초기화 (히라가나 변환용)
        self.kakasi = pykakasi.kakasi()

        # fugashi 초기화 (형태소 분석용)
        self.tagger = fugashi.Tagger() if fugashi else None

        # 한자 패턴 (CJK 통합 한자 범위)
        self.kanji_pattern = re.compile(r'[\u4e00-\u9fff]+')

    def _convert_to_hiragana(self, text: str) -> str:
        """
        텍스트를 히라가나로 변환 (pykakasi 사용)

        Args:
            text: 변환할 일본어 텍스트

        Returns:
            히라가나로 변환된 텍스트
        """
        try:
            result = self.kakasi.convert(text)
            # kakasi 결과는 리스트 형태로 반환됨
            hiragana_text = ''.join([item['hira'] for item in result])
            return hiragana_text
        except Exception as e:
            print(f"[Warning] 히라가나 변환 실패: {e}")
            return text

    def _find_token_positions(
            self, text: str, tokens: List[str]) -> List[tuple[int, int, str]]:
        """
        텍스트에서 토큰들의 위치를 찾음

        Args:
            text: 원본 텍스트
            tokens: 찾을 토큰 리스트

        Returns:
            (start, end, token) 튜플 리스트
        """
        positions = []

        for token in tokens:
            if not token.strip():
                continue

            # 대소문자 구분 없이 검색 (일본어는 대소문자 없음)
            pattern = re.compile(re.escape(token), re.IGNORECASE)
            for match in pattern.finditer(text):
                positions.append((match.start(), match.end(), token))

        # 겹치지 않도록 정렬 및 필터링
        positions.sort(key=lambda x: x[0])
        filtered_positions = []
        prev_end = -1

        for start, end, token in positions:
            if start >= prev_end:  # 겹치지 않음
                filtered_positions.append((start, end, token))
                prev_end = end

        return filtered_positions

    def _morphological_tokenize(self, text: str) -> List[str]:
        """
        형태소 분석을 통한 토큰화 (fugashi 활용)

        Args:
            text: 토큰화할 텍스트

        Returns:
            형태소 토큰 리스트
        """
        if not self.tagger:
            # fugashi가 없으면 간단한 공백/구두점 분리
            return re.findall(r'\w+', text)

        try:
            tokens = []
            for word in self.tagger(text):
                # 형태소의 표층형(원형) 사용
                surface = str(word.surface)
                if surface.strip():
                    tokens.append(surface)
            return tokens
        except Exception as e:
            print(f"[Warning] 형태소 분석 실패: {e}")
            return re.findall(r'\w+', text)

    def add_ruby_tags(self, text: str,
                      format_type: OutputFormat = OutputFormat.HTML) -> str:
        """
        한자에 히라가나 루비 태그를 추가

        Args:
            text: 일본어 텍스트
            format_type: 출력 형식 (HTML 또는 Markdown)

        Returns:
            루비 태그가 추가된 텍스트
        """
        if not text:
            return text

        try:
            # pykakasi로 변환 결과 얻기
            kakasi_result = self.kakasi.convert(text)

            if format_type == OutputFormat.HTML:
                # HTML <ruby> 태그로 변환
                result_parts = []
                current_pos = 0

                for item in kakasi_result:
                    orig = item['orig']
                    hira = item['hira']

                    # 원본 텍스트에서 현재 위치 찾기
                    pos = text.find(orig, current_pos)
                    if pos == -1:
                        continue

                    # 이전 텍스트 추가
                    if pos > current_pos:
                        result_parts.append(text[current_pos:pos])

                    # 한자가 포함되어 있고 히라가나가 다른 경우 루비 태그 추가
                    if self.kanji_pattern.search(orig) and orig != hira:
                        result_parts.append(
                            f"<ruby>{orig}<rt>{hira}</rt></ruby>")
                    else:
                        result_parts.append(orig)

                    current_pos = pos + len(orig)

                # 남은 텍스트 추가
                if current_pos < len(text):
                    result_parts.append(text[current_pos:])

                return ''.join(result_parts)

            elif format_type == OutputFormat.MARKDOWN:
                # Markdown 형식으로 변환 (제한적 지원)
                result_parts = []
                current_pos = 0

                for item in kakasi_result:
                    orig = item['orig']
                    hira = item['hira']

                    pos = text.find(orig, current_pos)
                    if pos == -1:
                        continue

                    if pos > current_pos:
                        result_parts.append(text[current_pos:pos])

                    # 한자가 있고 히라가나가 다른 경우 괄호로 표기
                    if self.kanji_pattern.search(orig) and orig != hira:
                        result_parts.append(f"{orig}({hira})")
                    else:
                        result_parts.append(orig)

                    current_pos = pos + len(orig)

                if current_pos < len(text):
                    result_parts.append(text[current_pos:])

                return ''.join(result_parts)

            else:  # PLAIN
                return text

        except Exception as e:
            print(f"[Warning] 루비 태그 추가 실패: {e}")
            return text

    def highlight_key_tokens(
        self,
        text: str,
        key_tokens: List[str],
        format_type: OutputFormat = OutputFormat.HTML,
        case_sensitive: bool = False
    ) -> str:
        """
        핵심 토큰들을 하이라이팅

        Args:
            text: 원본 텍스트
            key_tokens: 하이라이팅할 토큰 리스트
            format_type: 출력 형식
            case_sensitive: 대소문자 구분 여부

        Returns:
            토큰이 하이라이팅된 텍스트
        """
        if not text or not key_tokens:
            return text

        try:
            # 토큰 위치 찾기
            positions = self._find_token_positions(text, key_tokens)

            if not positions:
                return text

            # 위치를 역순으로 정렬 (뒤에서부터 교체)
            positions.sort(key=lambda x: x[0], reverse=True)

            result = text
            for start, end, token in positions:
                highlighted_token = self._apply_highlight(token, format_type)
                result = result[:start] + highlighted_token + result[end:]

            return result

        except Exception as e:
            print(f"[Warning] 토큰 하이라이팅 실패: {e}")
            return text

    def _apply_highlight(self, token: str, format_type: OutputFormat) -> str:
        """
        토큰에 하이라이팅 적용

        Args:
            token: 하이라이팅할 토큰
            format_type: 출력 형식

        Returns:
            하이라이팅된 토큰
        """
        if format_type == OutputFormat.HTML:
            return f"<mark>{token}</mark>"
        elif format_type == OutputFormat.MARKDOWN:
            return f"**{token}**"
        else:  # PLAIN
            return token

    def process_comprehensive_result(
        self,
        result: Dict[str, Any],
        format_type: OutputFormat = OutputFormat.HTML,
        include_ruby: bool = True,
        highlight_tokens: bool = True
    ) -> Dict[str, Any]:
        """
        ComprehensiveResult를 후처리하여 하이라이팅과 루비 태그 추가

        Args:
            result: translator.py의 번역 결과 딕셔너리
            format_type: 출력 형식
            include_ruby: 루비 태그 포함 여부
            highlight_tokens: 토큰 하이라이팅 여부

        Returns:
            후처리된 결과 딕셔너리
        """
        processed_result = result.copy()

        try:
            # 번역된 텍스트에 루비 태그 추가 (일본어인 경우)
            if 'translated_text' in result and result.get('task') == 'ko_to_ja':
                base_text = result['translated_text']

                # 1. 루비 태그 먼저 적용
                ruby_text = self.add_ruby_tags(base_text)

                # 2. 하이라이팅 적용 (실패 시 ruby_text 유지)
                try:
                    if 'key_tokens' in result and result['key_tokens']:
                        ruby_text = self.highlight_key_tokens(
                            ruby_text, result['key_tokens'])
                except Exception as e:
                    print(f"[Warning] 하이라이팅 적용 실패: {e}")

                # 3. 최종 결과 저장 (UI가 이 키를 참조하도록 일치시킴)
                result['translated_text_ruby'] = ruby_text

            # 스타일 변형에도 루비 태그 추가
            if 'style_variations' in result and isinstance(
                    result['style_variations'], dict):
                processed_variations = {}
                for style, text in result['style_variations'].items():
                    if include_ruby:
                        processed_variations[style] = self.add_ruby_tags(
                            text, format_type)
                    else:
                        processed_variations[style] = text

                    # 토큰 하이라이팅 적용
                    if highlight_tokens and 'key_tokens' in result:
                        processed_variations[style] = self.highlight_key_tokens(
                            processed_variations[style],
                            result['key_tokens'],
                            format_type
                        )

                processed_result['style_variations_processed'] = processed_variations

            # 원본 텍스트 토큰 하이라이팅 (한국어인 경우)
            if highlight_tokens and 'key_tokens' in result and 'original_text' in result:
                processed_result['original_text_highlighted'] = self.highlight_key_tokens(
                    result['original_text'],
                    result['key_tokens'],
                    format_type
                )

        except Exception as e:
            print(f"[Warning] 종합 결과 후처리 실패: {e}")
            # 실패 시 원본 결과 반환
            return result

        return processed_result

    def extract_key_phrases(self, text: str,
                            max_phrases: int = 5) -> List[str]:
        """
        텍스트에서 핵심 구문 추출 (fugashi 활용)

        Args:
            text: 분석할 텍스트
            max_phrases: 최대 추출 구문 수

        Returns:
            핵심 구문 리스트
        """
        if not self.tagger:
            # fugashi가 없으면 간단한 명사 추출 시도
            return []

        try:
            phrases = []
            for word in self.tagger(text):
                # 명사, 동사, 형용사 등 의미 있는 품사만 추출
                pos = word.feature.pos1
                if pos in ['名詞', '動詞', '形容詞'] and len(str(word.surface)) > 1:
                    phrases.append(str(word.surface))

            # 중복 제거 및 제한
            unique_phrases = list(set(phrases))
            return unique_phrases[:max_phrases]

        except Exception as e:
            print(f"[Warning] 구문 추출 실패: {e}")
            return []


# ─── 테스트 코드 ───
if __name__ == "__main__":
    print("[Japanese Text Processor Test]\n")

    processor = JapaneseTextProcessor()

    # 테스트 텍스트
    test_text = "こんにちは、世界！今日は良い天気ですね。"
    key_tokens = ["こんにちは", "世界", "天気"]

    print("1. 루비 태그 테스트:")
    ruby_html = processor.add_ruby_tags(test_text, OutputFormat.HTML)
    ruby_md = processor.add_ruby_tags(test_text, OutputFormat.MARKDOWN)
    print(f"원본: {test_text}")
    print(f"HTML: {ruby_html}")
    print(f"Markdown: {ruby_md}")
    print()

    print("2. 토큰 하이라이팅 테스트:")
    highlighted_html = processor.highlight_key_tokens(
        test_text, key_tokens, OutputFormat.HTML)
    highlighted_md = processor.highlight_key_tokens(
        test_text, key_tokens, OutputFormat.MARKDOWN)
    print(f"원본: {test_text}")
    print(f"HTML: {highlighted_html}")
    print(f"Markdown: {highlighted_md}")
    print()

    print("3. 형태소 분석 테스트:")
    if processor.tagger:
        tokens = processor._morphological_tokenize(test_text)
        print(f"토큰: {tokens}")
    else:
        print("fugashi 미설치로 형태소 분석 생략")
    print()

    print("4. 종합 결과 후처리 테스트:")
    mock_result = {
        "task": "ko_to_ja",
        "original_text": "안녕하세요, 오늘 날씨가 좋네요.",
        "translated_text": "こんにちは、今日は良い天気ですね。",
        "key_tokens": ["こんにちは", "天気"],
        "style_variations": {
            "casual": "こんにちは、今日はいい天気だね。",
            "polite": "こんにちは、今日は良い天気ですね。"
        }
    }

    processed = processor.process_comprehensive_result(
        mock_result, OutputFormat.HTML)
    print("후처리된 번역 텍스트:", processed.get('translated_text_ruby', 'N/A'))
    print("후처리된 스타일 변형:", processed.get('style_variations_processed', {}))
    print("하이라이팅된 원본:", processed.get('original_text_highlighted', 'N/A'))

    print("\n✅ 모든 테스트 완료!")
