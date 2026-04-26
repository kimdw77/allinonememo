"""
db/agent_runs.py — agent_runs 테이블 CRUD (에이전트 파이프라인 실행 기록)
"""
import logging
from typing import Optional

from db.client import get_db

logger = logging.getLogger(__name__)


def insert_agent_run(
    input_text: str,
    intent: str,
    confidence: float,
    final_action: str,
    needs_user_confirmation: bool = False,
    issues: Optional[list[str]] = None,
    note_id: Optional[str] = None,
    has_tasks: bool = False,
    task_count: int = 0,
    source: str = "",
    trace_id: Optional[str] = None,
) -> Optional[dict]:
    """파이프라인 실행 기록 저장. 실패해도 메인 흐름에 영향 없음."""
    try:
        db = get_db()
        row: dict = {
            "input_text": input_text[:500],
            "intent": intent,
            "confidence": round(confidence, 3),
            "final_action": final_action,
            "needs_user_confirmation": needs_user_confirmation,
            "issues": issues or [],
            "has_tasks": has_tasks,
            "task_count": task_count,
            "source": source,
        }
        if note_id:
            row["note_id"] = note_id
        if trace_id:
            row["trace_id"] = trace_id
        result = db.table("agent_runs").insert(row).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        # DB에 agent_runs 테이블이 없어도 전체 흐름 중단 안 함
        logger.warning("agent_runs 저장 실패 (무시): %s", e)
        return None
