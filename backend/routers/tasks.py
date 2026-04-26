"""
routers/tasks.py — tasks 테이블 REST API
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from db.tasks import delete_task, get_task_stats, get_tasks, update_task

logger = logging.getLogger(__name__)
router = APIRouter()


class TaskUpdateRequest(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    project: Optional[str] = None


@router.get("")
def list_tasks(
    status: Optional[str] = Query(None),
    project: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return get_tasks(status=status, project=project, limit=limit, offset=offset)


@router.get("/stats")
def task_stats():
    return get_task_stats()


@router.patch("/{task_id}")
def patch_task(task_id: str, body: TaskUpdateRequest):
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="수정할 필드가 없습니다")
    if "status" in fields and fields["status"] not in ("todo", "in_progress", "done"):
        raise HTTPException(status_code=400, detail="유효하지 않은 status 값")
    updated = update_task(task_id, fields)
    if not updated:
        raise HTTPException(status_code=404, detail="태스크를 찾을 수 없습니다")
    return updated


@router.delete("/{task_id}")
def remove_task(task_id: str):
    ok = delete_task(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="태스크를 찾을 수 없습니다")
    return {"deleted": task_id}
