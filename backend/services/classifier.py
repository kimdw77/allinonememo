"""
classifier.py — Claude API를 이용한 텍스트 요약·분류·키워드 추출
모든 Claude API 호출은 이 모듈에서만 처리
"""
import json
import logging
from typing import Optional

import anthropic

from config import settings

logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

# 요약·분류·키워드 추출을 단일 호출로 처리 (토큰 절약)
# {categories} 자리에 DB에서 가져온 카테고리 목록을 동적 주입
CLASSIFY_PROMPT = """다음 내용을 분석하여 JSON으로만 응답하라. 부가 설명 없이 JSON만.

{content}

{{"summary":"2-3문장 핵심 요약","highlights":["핵심문장1","핵심문장2","핵심문장3"],"keywords":["키1","키2","키3","키4","키5","키6","키7"],"category":"카테고리","content_type":"article|video|memo|link|other"}}

카테고리: {categories}
카테고리 포함 범위: 건강(스포츠·운동·피트니스·헬스 포함)
keywords: 핵심 키워드 5~7개. 고유명사·브랜드명·핵심 개념을 우선 포함하라.
highlights: 본문에서 가장 중요한 문장 3개 원문 그대로 발췌. 본문이 짧으면 1-2개도 가능."""

# 분류 실패 시 반환할 기본값
_FALLBACK: dict = {
    "summary": "",
    "keywords": [],
    "category": "기타",
    "content_type": "other",
}


def _get_categories_str() -> str:
    """DB에서 카테고리 목록을 읽어 '|' 구분 문자열로 반환. 실패 시 기본값"""
    try:
        from db.categories import get_category_names
        names = get_category_names()
        if names:
            return "|".join(names)
    except Exception as e:
        logger.warning("카테고리 목록 조회 실패, 기본값 사용: %s", e)
    return "비즈니스|기술|AI|무역/수출|건강|교육|뉴스|개인메모|기타"


def _extract_first_json(text: str) -> dict | None:
    """응답에서 첫 번째 완전한 JSON 객체를 괄호 카운팅으로 추출. greedy regex 오파싱 방지."""
    import re
    cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", text).strip()
    start = cleaned.find("{")
    if start == -1:
        return None
    depth = 0
    for i, ch in enumerate(cleaned[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(cleaned[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def classify_content(content: str) -> dict:
    """
    텍스트 내용을 요약·분류·키워드 추출 (단일 API 호출)
    카테고리 목록은 DB에서 동적으로 로드하여 프롬프트에 주입
    실패 시 빈 요약과 '기타' 카테고리를 반환 (데이터 손실 방지)
    """
    # 토큰 절약: 2000자 초과 시 잘라서 처리
    truncated = content[:2000] if len(content) > 2000 else content
    categories_str = _get_categories_str()

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[{
                "role": "user",
                "content": CLASSIFY_PROMPT.format(content=truncated, categories=categories_str),
            }],
        )

        raw = response.content[0].text if response.content else ""
        logger.info("Claude 원본 응답: %s", raw[:200])

        result = _extract_first_json(raw)
        if result is None:
            logger.error("Claude 응답에서 JSON 추출 실패. 원본(%d자): %s", len(raw), raw[:300])
            return _FALLBACK.copy()

        return {
            "summary": result.get("summary", ""),
            "highlights": result.get("highlights", []),
            "keywords": result.get("keywords", []),
            "category": result.get("category", "기타"),
            "content_type": result.get("content_type", "other"),
        }

    except json.JSONDecodeError as e:
        logger.error("Claude 응답 JSON 파싱 실패: %s", e)
        return _FALLBACK.copy()
    except anthropic.APIError as e:
        logger.error("Claude API 오류 [%s]: %s", type(e).__name__, e)
        return _FALLBACK.copy()
    except Exception as e:
        logger.error("분류 중 예상치 못한 오류 [%s]: %s", type(e).__name__, e)
        return _FALLBACK.copy()


IMAGE_PROMPT = """이 이미지를 분석하여 아래 JSON 형식으로만 응답하라. JSON 외 어떤 텍스트도 출력하지 말 것.

{{"summary":"","highlights":[],"keywords":[],"category":"","content_type":"","ocr_text":"","is_newspaper":false,"news_headline":"","search_query":""}}

각 필드 작성 규칙:
- summary: 이미지 핵심 내용 3-5문장 요약
- highlights: 본문에서 중요한 문장 3개를 원문 그대로 배열로
- keywords: 고유명사·브랜드명·핵심 개념 위주로 5-7개
- category: 아래 목록 중 하나 선택 — {categories}
- content_type: 신문이면 "newspaper", 일반 기사·문서이면 "article", 텍스트 없는 사진이면 "image", 메모이면 "memo", 기타 "other"
- ocr_text: 이미지에서 읽히는 주요 텍스트를 최대 400자까지만 추출. 텍스트 없는 사진은 빈 문자열.
- is_newspaper: 신문 페이지(다단 레이아웃·신문명·날짜 표기·기사 헤드라인 형태)이면 true, 아니면 false
- news_headline: is_newspaper가 true일 때 가장 큰 헤드라인 제목. 아니면 빈 문자열.
- search_query: content_type이 newspaper 또는 article이면 헤드라인+핵심어 조합의 뉴스 검색 쿼리. 아니면 빈 문자열."""


def analyze_image(image_bytes: bytes, media_type: str) -> dict:
    """
    Claude Vision으로 이미지 OCR + 분류.
    media_type: 'image/jpeg' | 'image/png' | 'image/gif' | 'image/webp'
    문서·잡지·책 촬영 이미지도 텍스트 추출 가능.
    """
    import base64

    # Claude Vision이 지원하지 않는 포맷은 jpeg로 폴백
    _ALLOWED_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
    if media_type not in _ALLOWED_TYPES:
        logger.warning("지원되지 않는 미디어 타입 '%s' → image/jpeg로 폴백", media_type)
        media_type = "image/jpeg"

    categories_str = _get_categories_str()
    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": b64},
                    },
                    {"type": "text", "text": IMAGE_PROMPT.format(categories=categories_str)},
                ],
            }],
        )

        raw = response.content[0].text if response.content else ""
        logger.info("이미지 분석 Claude 응답 (앞300자): %s", raw[:300])

        result = _extract_first_json(raw)
        if result is None:
            logger.error("이미지 분석 JSON 추출 실패. 응답 전체(%d자): %s", len(raw), raw[:500])
            return _FALLBACK.copy()

        return {
            "summary": result.get("summary", ""),
            "highlights": result.get("highlights", []),
            "keywords": result.get("keywords", []),
            "category": result.get("category", "기타"),
            "content_type": result.get("content_type", "other"),
            "ocr_text": result.get("ocr_text", ""),
            "is_newspaper": bool(result.get("is_newspaper", False)),
            "news_headline": result.get("news_headline", ""),
            "search_query": result.get("search_query", ""),
        }

    except anthropic.APIError as e:
        logger.error("이미지 분석 Claude API 오류 [%s]: %s", type(e).__name__, e)
        return _FALLBACK.copy()
    except Exception as e:
        logger.error("이미지 분석 실패 [%s]: %s", type(e).__name__, e)
        return _FALLBACK.copy()
