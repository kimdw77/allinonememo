"""
db/tasks.py — tasks 테이블 CRUD
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from db.client import get_db

logger = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))


def insert_tasks(
    tasks_data: list[dict],
    source: str = "",
    note_id: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> list[dict]:
    """태스크 목록 저장. 저장된 레코드 반환."""
    if not tasks_data:
        return []
    try:
        db = get_db()
        rows = []
        for t in tasks_data:
            row: dict = {
                "title": (t.get("title") or "")[:200],
                "description": t.get("description") or "",
                "priority": t.get("priority") or "medium",
                "project": t.get("project") or "",
                "status": "todo",
                "source": source,
            }
            if note_id:
                row["note_id"] = note_id
            if trace_id:
                row["trace_id"] = trace_id
            rows.append(row)
        result = db.table("tasks").insert(rows).execute()
        return result.data or []
    except Exception as e:
        logger.error("태스크 저장 실패: %s", e)
        return []


def get_tasks(
    status: Optional[str] = None,
    project: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """태스크 목록 조회"""
    try:
        db = get_db()
        q = db.table("tasks").select("*").order("created_at", desc=True)
        if status:
            q = q.eq("status", status)
        if project:
            q = q.eq("project", project)
        result = q.range(offset, offset + limit - 1).execute()
        return result.data or []
    except Exception as e:
        logger.error("태스크 조회 실패: %s", e)
        return []


def get_tasks_this_week() -> list[dict]:
    """지난 7일 태스크 조회"""
    try:
        db = get_db()
        week_ago = (datetime.now(KST) - timedelta(days=7)).isoformat()
        result = (
            db.table("tasks")
            .select("*")
            .gte("created_at", week_ago)
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []
    except Exception as e:
        logger.error("주간 태스크 조회 실패: %s", e)
        return []


def update_task(task_id: str, fields: dict) -> Optional[dict]:
    """태스크 부분 업데이트. 성공 시 업데이트된 레코드 반환."""
    try:
        db = get_db()
        result = db.table("tasks").update(fields).eq("id", task_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error("태스크 수정 실패 (id=%s): %s", task_id, e)
        return None


def delete_task(task_id: str) -> bool:
    """태스크 삭제. 성공 시 True."""
    try:
        db = get_db()
        db.table("tasks").delete().eq("id", task_id).execute()
        return True
    except Exception as e:
        logger.error("태스크 삭제 실패 (id=%s): %s", task_id, e)
        return False


def get_task_stats() -> dict:
    """태스크 상태별 통계"""
    try:
        db = get_db()
        result = db.table("tasks").select("status, priority").execute()
        rows = result.data or []
        by_status: dict[str, int] = {}
        by_priority: dict[str, int] = {}
        for r in rows:
            s = r.get("status", "todo")
            p = r.get("priority", "medium")
            by_status[s] = by_status.get(s, 0) + 1
            by_priority[p] = by_priority.get(p, 0) + 1
        return {
            "total": len(rows),
            "by_status": by_status,
            "by_priority": by_priority,
        }
    except Exception as e:
        logger.error("태스크 통계 조회 실패: %s", e)
        return {"total": 0, "by_status": {}, "by_priority": {}}
