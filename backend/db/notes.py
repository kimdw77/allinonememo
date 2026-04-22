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
    highlights: Optional[list[str]] = None,
    keywords: Optional[list[str]] = None,
    category: str = "기타",
    content_type: str = "other",
    url: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> Optional[dict]:
    """노트 저장. 성공 시 생성된 레코드 반환, 실패 시 None"""
    try:
        db = get_db()

        # 임베딩 생성 (VOYAGE_API_KEY 없으면 건너뜀)
        embedding = None
        try:
            from services.embedder import embed_text
            text_for_embed = f"{summary or ''}\n{raw_content}".strip()
            embedding = embed_text(text_for_embed)
        except Exception as emb_err:
            logger.warning("임베딩 생성 건너뜀: %s", emb_err)

        row: dict = {
            "source": source,
            "raw_content": raw_content,
            "summary": summary,
            "highlights": highlights or [],
            "keywords": keywords or [],
            "category": category,
            "content_type": content_type,
            "url": url,
            "metadata": metadata or {},
        }
        if embedding is not None:
            row["embedding"] = embedding

        result = db.table("notes").insert(row).execute()
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


def vector_search_notes(query_vector: list[float], limit: int = 10) -> list[dict]:
    """
    pgvector 코사인 유사도 기반 의미 검색.
    Supabase RPC 'match_notes' 함수 호출 (supabase/vector_search.sql 필요).
    """
    try:
        db = get_db()
        result = db.rpc("match_notes", {
            "query_embedding": query_vector,
            "match_count": limit,
        }).execute()
        return result.data or []

    except Exception as e:
        logger.error("벡터 검색 실패: %s", e)
        return []


def get_related_notes(note_id: str, limit: int = 5) -> list[dict]:
    """
    키워드 겹침 기반 연관 노트 조회.
    같은 카테고리 + 공통 키워드가 많은 순으로 반환.
    """
    try:
        db = get_db()
        # 기준 노트 조회
        base = db.table("notes").select("keywords,category").eq("id", note_id).single().execute()
        if not base.data:
            return []

        keywords = base.data.get("keywords") or []
        category = base.data.get("category", "")

        if not keywords:
            # 키워드 없으면 같은 카테고리 노트 반환
            result = db.table("notes").select(
                "id,summary,keywords,category,content_type,url,created_at"
            ).eq("category", category).neq("id", note_id).limit(limit).execute()
            return result.data or []

        # 키워드 배열 중 하나라도 겹치는 노트 조회 (PostgreSQL @> 연산자)
        # PostgREST: keywords 배열에 any 매칭
        result = db.table("notes").select(
            "id,summary,keywords,category,content_type,url,created_at"
        ).neq("id", note_id).overlaps("keywords", keywords).limit(limit * 3).execute()

        notes = result.data or []

        # 공통 키워드 수로 정렬
        keyword_set = set(keywords)
        scored = sorted(
            notes,
            key=lambda n: len(keyword_set & set(n.get("keywords") or [])),
            reverse=True,
        )
        return scored[:limit]

    except Exception as e:
        logger.error("연관 노트 조회 실패 (id=%s): %s", note_id, e)
        return []


def get_graph_data(limit: int = 200) -> dict:
    """
    그래프 시각화용 노드·엣지 데이터 반환.
    노드: 노트, 엣지: 공통 키워드 2개 이상인 노트 쌍.
    """
    try:
        db = get_db()
        result = db.table("notes").select(
            "id,summary,keywords,category,content_type,created_at"
        ).order("created_at", desc=True).limit(limit).execute()

        notes = result.data or []
        nodes = [
            {
                "id": n["id"],
                "label": (n.get("summary") or "")[:50],
                "category": n.get("category", "기타"),
                "content_type": n.get("content_type", "other"),
            }
            for n in notes
        ]

        # 엣지: 공통 키워드 2개 이상인 쌍만 연결
        edges = []
        for i, a in enumerate(notes):
            kw_a = set(a.get("keywords") or [])
            if not kw_a:
                continue
            for b in notes[i + 1:]:
                kw_b = set(b.get("keywords") or [])
                common = kw_a & kw_b
                if len(common) >= 2:
                    edges.append({
                        "source": a["id"],
                        "target": b["id"],
                        "weight": len(common),
                    })

        return {"nodes": nodes, "edges": edges}

    except Exception as e:
        logger.error("그래프 데이터 조회 실패: %s", e)
        return {"nodes": [], "edges": []}


def delete_note(note_id: str) -> bool:
    """노트 삭제. 성공 시 True"""
    try:
        db = get_db()
        db.table("notes").delete().eq("id", note_id).execute()
        return True
    except Exception as e:
        logger.error("노트 삭제 실패 (id=%s): %s", note_id, e)
        return False
