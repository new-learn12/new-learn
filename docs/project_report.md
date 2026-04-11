# Role: Expert Python & NLP Backend Developer
# Context: 'NEW LEARN' 프로젝트 (AI 일본어 교육 챗봇 서비스) 핵심 모듈 구현

현재 Pinned Contexts에 추가되어 있는 **"[REPORT] NEW LEARN 프로젝트: 일본어 교육 모듈 구조 개선 보고서"**를 정독하고, 해당 설계안을 완벽하게 반영한 소스 코드를 작성해줘. 
특히 보고서에 강조된 '하이브리드 언어 감지', '비대칭 파이프라인', '메모리/비용 최적화'를 코드로 어떻게 구현할지에 집중해야 해.

---
## 1. 파일 구조 및 핵심 기능 개발 지시

### [파일 1: modules/japanese/detector.py]
- **보고서 2.1항 반영:** 1. (Regex) 한글/가나 판별로 1차 분류 (속도 최우선).
  2. (Library) `langdetect`로 2차 검증.
  3. (Fallback) 3글자 이하 또는 모호할 때만 Gemini 1.5 Flash에 언어 판별(ISO 639-1 포맷) 위임.

### [파일 2: modules/japanese/translator.py] - 메인 로직
- **보고서 2.2항 & 2.3항 반영 (비대칭 파이프라인 및 동적 스키마):**
  - **Task A (일본어 입력):** - Gemini를 통한 문법 검증(Fail-Fast) 선행.
    - Helsinki-NLP(직역) vs Gemini(의역) 대조 로직 구현. (Helsinki 모델은 `ko-ja`는 절대 로드하지 말고 `ja-ko`만 사용할 것).
    - 메모리 최적화를 위해 Helsinki 모델은 Task A 진입 시에만 `@st.cache_resource`로 지연 로딩(Lazy Loading)할 것.
  - **Task B (한국어 입력):** - Helsinki 로드 금지. 단일 Gemini API 호출로 모든 결과(번역, 5종 스타일, 문법, 키워드, 발음)를 통합 JSON으로 응답받을 것.

### [파일 3: modules/japanese/processor.py]
- **보고서 2.4항 반영 (후처리 및 하이라이팅):**
  - `pykakasi`를 사용하여 한자 위에 히라가나를 올리는 HTML `<ruby>` 태그 생성 함수 구현.
  - Gemini가 반환한 '핵심 토큰' 리스트를 순회하며 원문에 마크다운 `**` 또는 HTML `<mark>` 처리를 하는 유틸리티 작성 (`fugashi` 활용 고려).

### [파일 4: app.py]
- Streamlit 기반 메인 UI 작성.
- Pinned Contexts의 보고서 3항(최종 기술 스택)에 맞게 파이프라인 1~4단계를 UI 플로우로 구현할 것.

## 2. Gemini Structured Output (JSON Schema 강제)
Gemini 1.5 Flash API 호출 시, Task B 기준 아래의 JSON 스키마를 프롬프트에 강제하여 파싱 에러를 방지해:
```json
{
  "is_correct": boolean,
  "correction": "string (optional)",
  "translated_text": "string",
  "style_variations": { "casual": "...", "polite": "...", "business": "...", "feminine": "...", "masculine": "..." },
  "key_tokens": ["token1", "token2"],
  "pronunciation": "string"
}

## 3. 코드 작성 규칙 (Pythonic & Clean Code)
- 모든 함수는 Type Hinting을 적용하고, 변수명은 논리적이고 직관적으로 작성할 것.
- 외부 API(Gemini) 호출 시 에러 핸들링 로직을 반드시 포함할 것.