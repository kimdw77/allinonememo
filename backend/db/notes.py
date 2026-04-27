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
    trace_id: Optional[str] = None,
    related_links: Optional[dict] = None,
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
            "related_links": related_links or {},
        }
        if embedding is not None:
            row["embedding"] = embedding
        if trace_id:
            row["trace_id"] = trace_id

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
    연관 노트 조회. 벡터 임베딩 있으면 코사인 유사도 우선, 없으면 키워드 겹침 폴백.
    """
    try:
        db = get_db()
        base = db.table("notes").select("keywords,category,embedding").eq("id", note_id).single().execute()
        if not base.data:
            return []

        # 벡터 유사도 검색 (임베딩이 있을 때)
        embedding = base.data.get("embedding")
        if embedding:
            try:
                result = db.rpc("match_notes", {
                    "query_embedding": embedding,
                    "match_count": limit + 1,
                }).execute()
                notes = [n for n in (result.data or []) if n.get("id") != note_id]
                if notes:
                    return notes[:limit]
            except Exception:
                pass  # 벡터 검색 실패 시 키워드 폴백

        # 키워드 겹침 폴백
        keywords = base.data.get("keywords") or []
        category = base.data.get("category", "")

        if not keywords:
            result = db.table("notes").select(
                "id,summary,keywords,category,content_type,url,created_at"
            ).eq("category", category).neq("id", note_id).limit(limit).execute()
            return result.data or []

        result = db.table("notes").select(
            "id,summary,keywords,category,content_type,url,created_at"
        ).neq("id", note_id).overlaps("keywords", keywords).limit(limit * 3).execute()

        notes = result.data or []
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


def get_top_keywords(limit: int = 50) -> list[str]:
    """전체 노트에서 사용 빈도 높은 키워드 목록 반환 (자동완성용)"""
    try:
        db = get_db()
        result = db.table("notes").select("keywords").execute()
        freq: dict[str, int] = {}
        for row in (result.data or []):
            for kw in (row.get("keywords") or []):
                if kw:
                    freq[kw] = freq.get(kw, 0) + 1
        sorted_kw = sorted(freq, key=lambda k: -freq[k])
        return sorted_kw[:limit]
    except Exception as e:
        logger.error("키워드 목록 조회 실패: %s", e)
        return []


def bulk_delete_notes(note_ids: list[str]) -> int:
    """여러 노트 일괄 삭제. 삭제된 수 반환."""
    if not note_ids:
        return 0
    try:
        db = get_db()
        db.table("notes").delete().in_("id", note_ids).execute()
        return len(note_ids)
    except Exception as e:
        logger.error("노트 일괄 삭제 실패: %s", e)
        return 0


def export_notes(
    category: Optional[str] = None,
    note_ids: Optional[list[str]] = None,
    limit: int = 1000,
) -> list[dict]:
    """내보내기용 노트 전체 조회"""
    try:
        db = get_db()
        q = db.table("notes").select("*").order("created_at", desc=True)
        if note_ids:
            q = q.in_("id", note_ids)
        elif category:
            q = q.eq("category", category)
        result = q.limit(limit).execute()
        return result.data or []
    except Exception as e:
        logger.error("노트 내보내기 조회 실패: %s", e)
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


def update_note(note_id: str, fields: dict) -> Optional[dict]:
    """노트 부분 업데이트. 성공 시 업데이트된 레코드 반환"""
    try:
        db = get_db()
        result = db.table("notes").update(fields).eq("id", note_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error("노트 수정 실패 (id=%s): %s", note_id, e)
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


def get_duplicates(threshold: int = 3) -> list[dict]:
    """
    키워드 공통 개수 >= threshold 인 노트 쌍을 중복 후보로 반환.
    최신 300개 노트 대상, O(n²) 이므로 limit로 범위 제한.
    """
    try:
        db = get_db()
        result = db.table("notes").select(
            "id,summary,keywords,category,created_at"
        ).order("created_at", desc=True).limit(300).execute()

        notes = result.data or []
        pairs: list[dict] = []

        for i, a in enumerate(notes):
            kw_a = set(a.get("keywords") or [])
            if not kw_a:
                continue
            for b in notes[i + 1:]:
                kw_b = set(b.get("keywords") or [])
                common = kw_a & kw_b
                if len(common) >= threshold:
                    pairs.append({
                        "note_a": {
                            "id": a["id"],
                            "summary": (a.get("summary") or "")[:100],
                            "category": a.get("category", ""),
                            "created_at": a.get("created_at", ""),
                        },
                        "note_b": {
                            "id": b["id"],
                            "summary": (b.get("summary") or "")[:100],
                            "category": b.get("category", ""),
                            "created_at": b.get("created_at", ""),
                        },
                        "common_keywords": sorted(common),
                        "score": len(common),
                    })

        # 점수 높은 순 정렬
        pairs.sort(key=lambda p: p["score"], reverse=True)
        return pairs[:50]

    except Exception as e:
        logger.error("중복 노트 감지 실패: %s", e)
        return []


def merge_notes(keep_id: str, remove_id: str) -> Optional[dict]:
    """
    두 노트 병합: keep_id 노트의 keywords에 remove_id 키워드를 합치고
    remove_id 노트는 삭제. 병합된 keep 노트 반환.
    """
    try:
        db = get_db()
        keep = get_note_by_id(keep_id)
        remove = get_note_by_id(remove_id)
        if not keep or not remove:
            return None

        # 키워드 합집합
        merged_kw = list(dict.fromkeys(
            (keep.get("keywords") or []) + (remove.get("keywords") or [])
        ))

        updated = update_note(keep_id, {"keywords": merged_kw})
        db.table("notes").delete().eq("id", remove_id).execute()
        return updated

    except Exception as e:
        logger.error("노트 병합 실패 (keep=%s, remove=%s): %s", keep_id, remove_id, e)
        return None


def get_stats() -> dict:
    """
    대시보드 통계 데이터 반환.
    - 카테고리별 노트 수
    - 소스별 노트 수
    - 오늘/이번 주 추가된 노트 수
    - 총 노트 수
    """
    try:
        db = get_db()
        result = db.table("notes").select("id,category,source,created_at").execute()
        notes = result.data or []

        from datetime import datetime, timedelta, timezone

        KST = timezone(timedelta(hours=9))
        now = datetime.now(KST)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=now.weekday())

        category_counts: dict[str, int] = {}
        source_counts: dict[str, int] = {}
        today_count = 0
        week_count = 0

        for n in notes:
            cat = n.get("category") or "기타"
            src = n.get("source") or "unknown"
            category_counts[cat] = category_counts.get(cat, 0) + 1
            source_counts[src] = source_counts.get(src, 0) + 1

            try:
                created = datetime.fromisoformat(n["created_at"].replace("Z", "+00:00"))
                created_kst = created.astimezone(KST)
                if created_kst >= today_start:
                    today_count += 1
                if created_kst >= week_start:
                    week_count += 1
            except Exception:
                pass

        # 일별 추이: 최근 7일
        daily: list[dict] = []
        for i in range(6, -1, -1):
            day = today_start - timedelta(days=i)
            day_end = day + timedelta(days=1)
            count = sum(
                1 for n in notes
                if _in_range(n.get("created_at", ""), day, day_end, KST)
            )
            daily.append({"date": day.strftime("%m/%d"), "count": count})

        return {
            "total": len(notes),
            "today": today_count,
            "this_week": week_count,
            "by_category": [
                {"name": k, "count": v}
                for k, v in sorted(category_counts.items(), key=lambda x: -x[1])
            ],
            "by_source": [
                {"name": k, "count": v}
                for k, v in sorted(source_counts.items(), key=lambda x: -x[1])
            ],
            "daily_trend": daily,
        }

    except Exception as e:
        logger.error("통계 조회 실패: %s", e)
        return {"total": 0, "today": 0, "this_week": 0, "by_category": [], "by_source": [], "daily_trend": []}


def _in_range(created_at: str, start, end, tz) -> bool:
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00")).astimezone(tz)
        return start <= dt < end
    except Exception:
        return False
