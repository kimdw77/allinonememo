"""
db/notes.py — notes 테이블 CRUD 함수
"""
import logging
from typing import Optional

from db.client import get_db

logger = logging.getLogger(__name__)


def insert_note(
    source: str,
    raw_content: str,
    summary: str = "",
    keywords: Optional[list[str]] = None,
    category: str = "기타",
    content_type: str = "other",
    url: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> Optional[dict]:
    """노트 저장. 성공 시 생성된 레코드 반환, 실패 시 None"""
    try:
        db = get_db()
        result = db.table("notes").insert({
            "source": source,
            "raw_content": raw_content,
            "summary": summary,
            "keywords": keywords or [],
            "category": category,
            "content_type": content_type,
            "url": url,
            "metadata": metadata or {},
        }).execute()

        return result.data[0] if result.data else None

    except Exception as e:
        logger.error("노트 저장 실패: %s", e)
        return None


def get_notes(
    query: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> list[dict]:
    """노트 목록 조회 (키워드 검색·카테고리 필터 지원)"""
    try:
        db = get_db()
        q = db.table("notes").select("*").order("created_at", desc=True)

        if category:
            q = q.eq("category", category)

        if query:
            # 특수문자 이스케이프 후 검색 (PostgREST or_ 인젝션 방지)
            safe_query = query.replace("%", r"\%").replace("_", r"\_").replace(",", r"\,")
            q = q.or_(
                f"raw_content.ilike.%{safe_query}%,summary.ilike.%{safe_query}%"
            )

        result = q.range(offset, offset + limit - 1).execute()
        return result.data or []

    except Exception as e:
        logger.error("노트 조회 실패: %s", e)
        return []


def get_note_by_id(note_id: str) -> Optional[dict]:
    """단일 노트 조회"""
    try:
        db = get_db()
        result = db.table("notes").select("*").eq("id", note_id).single().execute()
        return result.data
    except Exception as e:
        logger.error("노트 단건 조회 실패 (id=%s): %s", note_id, e)
        return None


def delete_note(note_id: str) -> bool:
    """노트 삭제. 성공 시 True"""
    try:
        db = get_db()
        db.table("notes").delete().eq("id", note_id).execute()
        return True
    except Exception as e:
        logger.error("노트 삭제 실패 (id=%s): %s", note_id, e)
        return False
