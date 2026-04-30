"""
routers/sync.py — 외부 서비스 동기화 API
Notion 일괄 동기화, Google Drive 백업, GitHub KMS 동기화 (Phase 9-1)
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from config import settings
from dependencies.auth import require_api_key
from services.notion_sync import bulk_sync_to_notion
from services.gdrive_backup import backup_notes_to_drive

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_api_key)])


@router.post("/notion")
async def sync_notion(limit: int = Query(100, ge=1, le=500)):
    if not settings.NOTION_TOKEN or not settings.NOTION_DATABASE_ID:
        raise HTTPException(status_code=503, detail="Notion 환경변수(NOTION_TOKEN, NOTION_DATABASE_ID) 미설정")
    return bulk_sync_to_notion(limit=limit)


@router.post("/gdrive")
async def backup_gdrive():
    if not settings.GOOGLE_SERVICE_ACCOUNT_JSON or not settings.GOOGLE_DRIVE_FOLDER_ID:
        raise HTTPException(status_code=503, detail="Google 환경변수 미설정")
    result = backup_notes_to_drive()
    if not result:
        raise HTTPException(status_code=500, detail="Google Drive 백업 실패")
    return {"status": "ok", "file": result}


# ── GitHub KMS 동기화 (Phase 9-1) ─────────────────────────────────────


@router.post("/github/note/{note_id}")
async def sync_note_to_github(note_id: str):
    """노트 1건을 my-kms GitHub Repo에 수동 재동기화."""
    if not settings.GITHUB_TOKEN or not settings.GITHUB_REPO:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN/GITHUB_REPO 환경변수 미설정")

    from db.notes import get_note_by_id
    from workers.sync_worker import enqueue_sync
    from utils.trace_id import new_trace_id
    import asyncio

    note = get_note_by_id(note_id)
    if not note:
        raise HTTPException(status_code=404, detail=f"note_id={note_id} 없음")

    trace_id = new_trace_id()
    asyncio.create_task(enqueue_sync(note, trace_id))
    return {"status": "queued", "note_id": note_id, "trace_id": trace_id}


@router.get("/github/status")
async def get_sync_status(
    status: str = Query(None, description="pending|synced|failed|quarantined"),
    limit: int = Query(50, ge=1, le=200),
):
    """동기화 상태 목록 조회."""
    from db.sync_status import get_sync_status_list
    return get_sync_status_list(limit=limit, status=status)


@router.get("/github/failed")
async def get_failed_syncs(limit: int = Query(50, ge=1, le=200)):
    """실패 항목 목록 조회."""
    from db.sync_status import get_failed_syncs
    return get_failed_syncs(limit=limit)


@router.post("/github/retry/{sync_id}")
async def retry_sync(sync_id: str):
    """실패·격리된 sync_status 항목을 수동 재시도."""
    if not settings.GITHUB_TOKEN or not settings.GITHUB_REPO:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN/GITHUB_REPO 환경변수 미설정")

    from db.sync_status import get_sync_by_id
    from db.notes import get_note_by_id
    from workers.sync_worker import enqueue_sync
    from utils.trace_id import new_trace_id
    import asyncio

    sync_record = get_sync_by_id(sync_id)
    if not sync_record:
        raise HTTPException(status_code=404, detail=f"sync_id={sync_id} 없음")
    if sync_record.get("status") not in ("failed", "quarantined"):
        raise HTTPException(
            status_code=400,
            detail=f"재시도 불가 상태: {sync_record.get('status')} (failed/quarantined 만 가능)",
        )

    note_id = sync_record.get("note_id")
    note = get_note_by_id(note_id) if note_id else None
    if not note:
        raise HTTPException(status_code=404, detail=f"연결된 note_id={note_id} 없음")

    trace_id = new_trace_id()
    asyncio.create_task(enqueue_sync(note, trace_id))
    return {"status": "queued", "sync_id": sync_id, "note_id": note_id, "trace_id": trace_id}
