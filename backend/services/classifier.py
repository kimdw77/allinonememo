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

{{"summary":"2-3문장 핵심 요약","highlights":["핵심문장1","핵심문장2","핵심문장3"],"keywords":["키1","키2","키3"],"category":"카테고리","content_type":"article|video|memo|link|other"}}

카테고리: {categories}
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
    return "비즈니스|기술|무역/수출|건강|교육|뉴스|개인메모|기타"


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
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": CLASSIFY_PROMPT.format(content=truncated, categories=categories_str),
            }],
        )

        raw = response.content[0].text if response.content else ""
        logger.info("Claude 원본 응답: %s", raw[:200])

        # 코드블록 제거 후 JSON 추출
        import re
        cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            logger.error("Claude 응답에서 JSON 추출 실패. 원본: %s", raw[:200])
            return _FALLBACK.copy()

        result = json.loads(match.group())
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
        logger.error("Claude API 오류: %s", e)
        return _FALLBACK.copy()
    except Exception as e:
        logger.error("분류 중 예상치 못한 오류: %s", e)
        return _FALLBACK.copy()
