"""
db/thoughts.py — thoughts 테이블 CRUD
ask_user / reject 케이스의 스테이징 레코드 관리
"""
import logging
from typing import Optional

from db.client import get_db

logger = logging.getLogger(__name__)

# 허용 status 값
_VALID_STATUS = {
    "pending",
    "processed",
    "pending_user_confirm",
    "manual_review",
    "rejected",
}


def insert_thought(
    raw_input: str,
    trace_id: str,
    source: str = "telegram",
    status: str = "pending",
) -> Optional[dict]:
    """파이프라인 시작 시 입력 원본 기록. 실패해도 None 반환 (흐름 유지)."""
    try:
        db = get_db()
        result = db.table("thoughts").insert({
            "raw_input": raw_input[:2000],
            "trace_id": trace_id,
            "source": source,
            "status": status,
        }).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.warning("thoughts 저장 실패 (무시): %s", e)
        return None


def update_thought_status(
    thought_id: Optional[str],
    status: str,
    critic_issues: Optional[list[str]] = None,
    critic_suggested_fixes: Optional[list[str]] = None,
) -> Optional[dict]:
    """파이프라인 결과에 따라 thought 상태 갱신."""
    if not thought_id:
        return None
    if status not in _VALID_STATUS:
        logger.warning("유효하지 않은 thought status: %s", status)
        return None
    try:
        db = get_db()
        fields: dict = {"status": status}
        if critic_issues is not None:
            fields["critic_issues"] = critic_issues
        if critic_suggested_fixes is not None:
            fields["critic_suggested_fixes"] = critic_suggested_fixes
        result = db.table("thoughts").update(fields).eq("id", thought_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.warning("thought 상태 갱신 실패 (무시): %s", e)
        return None


def get_thought_by_trace(trace_id: str) -> Optional[dict]:
    """trace_id로 thought 조회 (최신 1건)."""
    try:
        db = get_db()
        result = (
            db.table("thoughts")
            .select("*")
            .eq("trace_id", trace_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error("thought 조회 실패: %s", e)
        return None
