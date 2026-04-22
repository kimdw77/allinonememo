"""
routers/sync.py — 외부 서비스 동기화 API
Notion 일괄 동기화, Google Drive 백업 수동 트리거
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from dependencies.auth import require_api_key

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_api_key)])


@router.post("/notion")
async def sync_notion(limit: int = Query(100, ge=1, le=500, description="동기화할 최근 노트 수")):
    """최근 노트를 Notion 데이터베이스에 일괄 동기화"""
    from config import settings
    if not settings.NOTION_TOKEN or not settings.NOTION_DATABASE_ID:
        raise HTTPException(status_code=503, detail="Notion 환경변수(NOTION_TOKEN, NOTION_DATABASE_ID) 미설정")

    from services.notion_sync import bulk_sync_to_notion
    result = bulk_sync_to_notion(limit=limit)
    return result


@router.post("/gdrive")
async def backup_gdrive():
    """전체 노트를 Google Drive에 JSON 백업"""
    from config import settings
    if not settings.GOOGLE_SERVICE_ACCOUNT_JSON or not settings.GOOGLE_DRIVE_FOLDER_ID:
        raise HTTPException(status_code=503, detail="Google 환경변수 미설정")

    from services.gdrive_backup import backup_notes_to_drive
    result = backup_notes_to_drive()
    if not result:
        raise HTTPException(status_code=500, detail="Google Drive 백업 실패")
    return {"status": "ok", "file": result}
