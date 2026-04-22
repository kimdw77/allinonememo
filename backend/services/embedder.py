"""
embedder.py — 텍스트 임베딩 생성 서비스 (Voyage AI)
벡터 검색을 위한 1536차원 임베딩 생성
모든 임베딩 API 호출은 이 모듈에서만 처리
"""
import logging
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)

# Voyage AI 클라이언트 (지연 초기화)
_voyage_client = None


def _get_client():
    global _voyage_client
    if _voyage_client is None:
        import voyageai
        _voyage_client = voyageai.Client(api_key=settings.VOYAGE_API_KEY)
    return _voyage_client


def embed_text(text: str) -> Optional[list[float]]:
    """
    텍스트를 1536차원 벡터로 변환.
    실패 시 None 반환 (임베딩 없이도 노트는 저장됨).
    """
    if not settings.VOYAGE_API_KEY:
        return None

    # 8000자 제한 (Voyage 토큰 한도)
    truncated = text[:8000]

    try:
        client = _get_client()
        result = client.embed([truncated], model="voyage-large-2", input_type="document")
        return result.embeddings[0] if result.embeddings else None

    except Exception as e:
        logger.error("임베딩 생성 실패: %s", e)
        return None


def embed_query(query: str) -> Optional[list[float]]:
    """
    검색 쿼리를 벡터로 변환 (검색 시 사용).
    input_type='query'로 설정하여 쿼리 최적화 임베딩 생성.
    """
    if not settings.VOYAGE_API_KEY:
        return None

    try:
        client = _get_client()
        result = client.embed([query], model="voyage-large-2", input_type="query")
        return result.embeddings[0] if result.embeddings else None

    except Exception as e:
        logger.error("쿼리 임베딩 생성 실패: %s", e)
        return None
