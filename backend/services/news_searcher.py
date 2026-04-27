"""
services/news_searcher.py — Tavily API로 신문·기사 관련 웹 링크 및 이미지 수집
TAVILY_API_KEY 미설정 시 빈 결과 반환 (파이프라인 중단 없음)
"""
import logging

import httpx

from config import settings

logger = logging.getLogger(__name__)

TAVILY_URL = "https://api.tavily.com/search"


async def search_related_articles(query: str, max_results: int = 5) -> dict:
    """
    Tavily 검색 API로 관련 기사 링크와 이미지 URL 수집.
    반환: {
      "articles": [{"title", "url", "description", "published_date"}, ...],
      "images": ["https://...", ...],
      "search_query": "사용된 검색어"
    }
    """
    if not settings.TAVILY_API_KEY:
        logger.warning("TAVILY_API_KEY 미설정 — 관련 링크 검색 건너뜀")
        return {"articles": [], "images": [], "search_query": query}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                TAVILY_URL,
                json={
                    "api_key": settings.TAVILY_API_KEY,
                    "query": query,
                    "search_depth": "basic",
                    "topic": "news",
                    "max_results": max_results,
                    "include_images": True,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        articles = [
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "description": (item.get("content") or "")[:200],
                "published_date": item.get("published_date", ""),
            }
            for item in data.get("results", [])
            if item.get("url")
        ]

        # Tavily 이미지는 결과 상단의 별도 리스트로 반환됨
        images = [img for img in data.get("images", []) if img][:5]

        logger.info("Tavily 검색 완료: 기사 %d개, 이미지 %d개 (쿼리: %s)", len(articles), len(images), query)
        return {
            "articles": articles,
            "images": images,
            "search_query": query,
        }

    except httpx.HTTPStatusError as e:
        logger.error("Tavily API HTTP 오류 (%s): %s", e.response.status_code, e)
        return {"articles": [], "images": [], "search_query": query}
    except Exception as e:
        logger.error("Tavily 검색 실패: %s", e)
        return {"articles": [], "images": [], "search_query": query}
