"""
psychology_rag.py
─────────────────
파이프라인:
  키워드 매칭 → 챕터 찾기 → 해당 PDF 페이지 텍스트 추출 → 컨텍스트 주입

필요 파일 (app.py와 같은 폴더에 위치함):
  chapter_summaries.json   - 챕터 메타 + 페이지 정보
  section PDFs/            - 나눠진 PDF 파일들 (PDF_DIR로 경로 지정)
"""

import json
import os
import re

import pdfplumber

# ── 경로 설정 ──────────────────────────────────────────────────────────────
_BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
_SUMMARY_PATH = os.path.join(_BASE_DIR, "chapter_summaries.json")

# PDF 파일 위치: app.py와 같은 폴더 안 'pdfs/' 서브폴더가 기본값
# 변경하려면 이 줄만 수정하면 됨ㅁ.
PDF_DIR = os.path.join(_BASE_DIR, "pdfs")

# 챕터당 추출할 최대 글자 수 (토큰 절약용)
MAX_CHARS_PER_CHAPTER = 2500

_data = None


def _load() -> dict:
    global _data
    if _data is None:
        with open(_SUMMARY_PATH, "r", encoding="utf-8") as f:
            _data = json.load(f)
    return _data


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[가-힣a-zA-Z]+", text.lower())


def _extract_pdf_text(section_file: str, page_start: int, page_end: int) -> str:
    """
    section_file의 page_start ~ page_end-1 페이지에서 텍스트를 추출합니다.
    PDF가 없으면 빈 문자열을 반환합니다.
    """
    pdf_path = os.path.join(PDF_DIR, section_file)
    if not os.path.exists(pdf_path):
        return ""

    texts = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i in range(page_start, min(page_end, len(pdf.pages))):
                page_text = pdf.pages[i].extract_text() or ""
                texts.append(page_text)
    except Exception:
        return ""

    raw = "\n".join(texts)

    # 불필요한 공백·반복 줄바꿈 정리
    raw = re.sub(r'\n{3,}', '\n\n', raw)
    raw = re.sub(r'[ \t]+', ' ', raw)

    # 글자 수 제한
    if len(raw) > MAX_CHARS_PER_CHAPTER:
        raw = raw[:MAX_CHARS_PER_CHAPTER] + "\n...(이하 생략)"

    return raw.strip()


def find_relevant_chapters(query: str, top_k: int = 2) -> list[dict]:
    """
    질문과 관련성이 높은 챕터 정보를 반환합니다.
    PDF 텍스트 추출 성공 시 'text' 키에 원문이 담깁니다.
    """
    data = _load()
    q_tokens = set(_tokenize(query))

    scored = []
    for section in data["sections"]:
        for ch in section["chapters"]:
            score = 0

            for kw in ch.get("keywords", []):
                if set(_tokenize(kw)) & q_tokens:
                    score += 2

            score += len(set(_tokenize(ch["title"])) & q_tokens)
            score += int(len(set(_tokenize(ch["summary"])) & q_tokens) * 0.3)

            if score > 0:
                scored.append((score, ch, section["section_title"]))

    scored.sort(key=lambda x: -x[0])
    results = []
    for score, ch, section_title in scored[:top_k]:
        entry = {
            "section": section_title,
            "chapter": ch["chapter"],
            "title": ch["title"],
            "summary": ch["summary"],
            "score": score,
            "text": "",
        }
        # PDF 원문 추출 시도
        if "section_file" in ch:
            extracted = _extract_pdf_text(
                ch["section_file"],
                ch.get("local_page_start", 0),
                ch.get("local_page_end", 0),
            )
            entry["text"] = extracted

        results.append(entry)

    return results


def build_context_block(query: str) -> str:
    """
    llm_handler에서 system prompt에 붙일 컨텍스트 문자열을 반환합니다.
    PDF 원문이 있으면 원문을, 없으면 요약본을 사용합니다.
    """
    results = find_relevant_chapters(query)
    if not results:
        return ""

    lines = ["[관련 교재 내용]"]
    for r in results:
        lines.append(f"\n■ 챕터 {r['chapter']}: {r['title']}")

        if r["text"]:
            lines.append("(교재 원문)")
            lines.append(r["text"])
        else:
            # PDF 없을 때 요약으로 폴백
            lines.append("(요약본 — PDF 파일을 pdfs/ 폴더에 넣으면 원문이 사용됩니다)")
            lines.append(r["summary"])

    return "\n".join(lines)
