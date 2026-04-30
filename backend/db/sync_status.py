"""
db/sync_status.py — sync_status 테이블 CRUD (Phase 9-1)
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from config import KST

logger = logging.getLogger(__name__)


def insert_sync(
    note_id: str,
    trace_id: str,
    status: str = "pending",
) -> Optional[dict]:
    """sync_status 레코드 생성. 실패 시 None 반환."""
    try:
        from db.client import get_db
        result = get_db().table("sync_status").insert({
            "note_id": note_id,
            "trace_id": trace_id,
            "status": status,
        }).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error("insert_sync 실패: %s", e)
        return None


def update_sync_status(
    sync_id: str,
    status: str,
    github_path: Optional[str] = None,
    github_sha: Optional[str] = None,
    last_error: Optional[str] = None,
    attempts: Optional[int] = None,
    synced_at: Optional[datetime] = None,
) -> None:
    """sync_status 레코드 갱신. 실패해도 예외 전파 안 함."""
    try:
        from db.client import get_db
        payload: dict = {
            "status": status,
            "updated_at": datetime.now(KST).isoformat(),
        }
        if github_path is not None:
            payload["github_path"] = github_path
        if github_sha is not None:
            payload["github_sha"] = github_sha
        if last_error is not None:
            payload["last_error"] = last_error[:500]  # 너무 긴 에러 자름
        if attempts is not None:
            payload["attempts"] = attempts
        if synced_at is not None:
            payload["synced_at"] = synced_at.isoformat()
        get_db().table("sync_status").update(payload).eq("id", sync_id).execute()
    except Exception as e:
        logger.error("update_sync_status 실패: %s", e)


def get_failed_syncs(limit: int = 50) -> list[dict]:
    """status='failed' 레코드 목록 반환."""
    try:
        from db.client import get_db
        result = (
            get_db().table("sync_status")
            .select("*")
            .eq("status", "failed")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
    except Exception as e:
        logger.error("get_failed_syncs 실패: %s", e)
        return []


def get_sync_status_list(limit: int = 100, status: Optional[str] = None) -> list[dict]:
    """sync_status 레코드 목록 반환 (선택적 status 필터)."""
    try:
        from db.client import get_db
        query = (
            get_db().table("sync_status")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
        )
        if status:
            query = query.eq("status", status)
        return query.execute().data or []
    except Exception as e:
        logger.error("get_sync_status_list 실패: %s", e)
        return []


def get_sync_by_id(sync_id: str) -> Optional[dict]:
    """단일 sync_status 레코드 조회."""
    try:
        from db.client import get_db
        result = get_db().table("sync_status").select("*").eq("id", sync_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error("get_sync_by_id 실패: %s", e)
        return None


def get_sync_lag_stats() -> dict:
    """
    최근 1시간 동기화 완료 건의 지연 통계 (초 단위).
    HARNESS 3-1 에서 사용.
    반환: {"avg_lag_seconds": float, "max_lag_seconds": float, "count": int}
    """
    try:
        from db.client import get_db
        one_hour_ago = (datetime.now(KST) - timedelta(hours=1)).isoformat()
        result = (
            get_db().table("sync_status")
            .select("created_at,synced_at")
            .eq("status", "synced")
            .gte("created_at", one_hour_ago)
            .execute()
        )
        records = result.data or []
        if not records:
            return {"avg_lag_seconds": 0.0, "max_lag_seconds": 0.0, "count": 0}

        lags: list[float] = []
        for r in records:
            if r.get("synced_at") and r.get("created_at"):
                try:
                    created = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00"))
                    synced = datetime.fromisoformat(r["synced_at"].replace("Z", "+00:00"))
                    lag = (synced - created).total_seconds()
                    if lag >= 0:
                        lags.append(lag)
                except ValueError:
                    continue

        if not lags:
            return {"avg_lag_seconds": 0.0, "max_lag_seconds": 0.0, "count": 0}

        return {
            "avg_lag_seconds": sum(lags) / len(lags),
            "max_lag_seconds": max(lags),
            "count": len(lags),
        }
    except Exception as e:
        logger.error("get_sync_lag_stats 실패: %s", e)
        return {"avg_lag_seconds": 0.0, "max_lag_seconds": 0.0, "count": 0}


def get_fail_rate_24h() -> float:
    """
    최근 24시간 동기화 실패율 (0.0 ~ 100.0).
    HARNESS 3-2 에서 사용.
    """
    try:
        from db.client import get_db
        one_day_ago = (datetime.now(KST) - timedelta(hours=24)).isoformat()
        result = (
            get_db().table("sync_status")
            .select("status")
            .gte("created_at", one_day_ago)
            .execute()
        )
        records = result.data or []
        if not records:
            return 0.0
        total = len(records)
        failed = sum(1 for r in records if r.get("status") == "failed")
        return (failed / total) * 100.0
    except Exception as e:
        logger.error("get_fail_rate_24h 실패: %s", e)
        return 0.0
