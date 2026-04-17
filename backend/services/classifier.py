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
CLASSIFY_PROMPT = """다음 내용을 분석하여 JSON으로만 응답하라. 부가 설명 없이 JSON만.

{content}

{{"summary":"2-3문장 핵심 요약","keywords":["키1","키2","키3"],"category":"카테고리","content_type":"article|video|memo|link|other"}}

카테고리: 비즈니스|기술|무역/수출|건강|교육|뉴스|개인메모|기타"""

# 분류 실패 시 반환할 기본값
_FALLBACK: dict = {
    "summary": "",
    "keywords": [],
    "category": "기타",
    "content_type": "other",
}


def classify_content(content: str) -> dict:
    """
    텍스트 내용을 요약·분류·키워드 추출 (단일 API 호출)
    실패 시 빈 요약과 '기타' 카테고리를 반환 (데이터 손실 방지)
    """
    # 토큰 절약: 2000자 초과 시 잘라서 처리
    truncated = content[:2000] if len(content) > 2000 else content

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,  # JSON 응답이므로 충분
            messages=[{
                "role": "user",
                "content": CLASSIFY_PROMPT.format(content=truncated),
            }],
        )
        result = json.loads(response.content[0].text)

        # 필수 키 검증
        return {
            "summary": result.get("summary", ""),
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
