"""
services/storage.py — Supabase Storage 원본 파일 업로드
"""
import logging
import uuid
from typing import Optional

logger = logging.getLogger(__name__)

BUCKET = "media"


def upload_file(
    file_bytes: bytes,
    folder: str,
    extension: str,
    content_type: str,
) -> Optional[str]:
    """
    Supabase Storage에 파일 업로드.
    성공 시 public URL 반환, 실패 시 None.
    folder: "photos" | "voices"
    """
    try:
        from db.client import get_db
        db = get_db()

        file_path = f"{folder}/{uuid.uuid4().hex}.{extension}"

        db.storage.from_(BUCKET).upload(
            path=file_path,
            file=file_bytes,
            file_options={"content-type": content_type, "upsert": "false"},
        )

        url: str = db.storage.from_(BUCKET).get_public_url(file_path)
        logger.info("Storage 업로드 완료: %s", file_path)
        return url

    except Exception as e:
        logger.error("Storage 업로드 실패: %s", e)
        return None
