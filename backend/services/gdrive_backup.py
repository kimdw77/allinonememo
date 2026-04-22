"""
gdrive_backup.py — Google Drive 노트 백업 서비스
전체 노트를 JSON으로 직렬화하여 지정된 Drive 폴더에 업로드
서비스 계정 방식 인증 (GOOGLE_SERVICE_ACCOUNT_JSON 환경변수)
"""
import io
import json
import logging
from datetime import datetime
from typing import Optional

from config import settings, KST

logger = logging.getLogger(__name__)


def _get_drive_service():
    """
    서비스 계정 자격증명으로 Google Drive API 클라이언트 생성.
    GOOGLE_SERVICE_ACCOUNT_JSON: JSON 문자열 또는 파일 경로
    """
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    sa_value = settings.GOOGLE_SERVICE_ACCOUNT_JSON.strip()
    if not sa_value:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON 미설정")

    # JSON 문자열인지 파일 경로인지 구분
    if sa_value.startswith("{"):
        info = json.loads(sa_value)
    else:
        with open(sa_value, "r", encoding="utf-8") as f:
            info = json.load(f)

    creds = service_account.Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/drive.file"],
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def backup_notes_to_drive() -> Optional[str]:
    """
    전체 노트를 JSON으로 직렬화 후 Google Drive 폴더에 업로드.
    성공 시 업로드된 파일명 반환, 실패 시 None.
    """
    try:
        from db.notes import get_notes
        # 최근 1000개 노트 백업
        notes = get_notes(limit=1000)
        if not notes:
            logger.info("백업할 노트 없음")
            return None

        now_kst = datetime.now(KST)
        filename = f"myvault_backup_{now_kst.strftime('%Y%m%d_%H%M')}.json"

        # JSON 직렬화
        payload = {
            "exported_at": now_kst.isoformat(),
            "count": len(notes),
            "notes": notes,
        }
        content = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        file_stream = io.BytesIO(content.encode("utf-8"))

        drive = _get_drive_service()

        _delete_old_backups(drive)

        # 새 파일 업로드
        from googleapiclient.http import MediaIoBaseUpload
        media = MediaIoBaseUpload(file_stream, mimetype="application/json")
        file_meta = {
            "name": filename,
            "parents": [settings.GOOGLE_DRIVE_FOLDER_ID],
        }
        uploaded = drive.files().create(
            body=file_meta,
            media_body=media,
            fields="id, name",
        ).execute()

        logger.info("Google Drive 백업 완료: %s (id=%s)", uploaded["name"], uploaded["id"])
        return uploaded["name"]

    except Exception as e:
        logger.error("Google Drive 백업 실패: %s", e)
        return None


def _delete_old_backups(drive, max_keep: int = 7) -> None:
    """Drive 폴더에서 오래된 백업 파일 정리 (최근 max_keep개 유지)."""
    try:
        query = (
            f"'{settings.GOOGLE_DRIVE_FOLDER_ID}' in parents"
            f" and name contains 'myvault_backup_'"
            f" and mimeType='application/json'"
            f" and trashed=false"
        )
        resp = drive.files().list(
            q=query,
            orderBy="createdTime desc",
            fields="files(id, name)",
            pageSize=50,
        ).execute()

        files = resp.get("files", [])
        # max_keep 초과분 삭제
        for old_file in files[max_keep:]:
            drive.files().delete(fileId=old_file["id"]).execute()
            logger.info("오래된 백업 삭제: %s", old_file["name"])

    except Exception as e:
        logger.warning("기존 백업 정리 실패 (무시): %s", e)
