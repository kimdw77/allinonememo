"""
db/subscriptions.py — RSS 구독 테이블 CRUD 함수
"""
import logging
from typing import Optional

from db.client import get_db

logger = logging.getLogger(__name__)


def get_active_subscriptions() -> list[dict]:
    """활성화된 RSS 구독 목록 조회"""
    try:
        db = get_db()
        result = db.table("subscriptions").select("*").eq("is_active", True).execute()
        return result.data or []
    except Exception as e:
        logger.error("RSS 구독 목록 조회 실패: %s", e)
        return []


def insert_subscription(url: str, name: str = "") -> Optional[dict]:
    """RSS 구독 등록. 성공 시 생성된 레코드 반환"""
    try:
        db = get_db()
        result = db.table("subscriptions").insert({
            "url": url,
            "name": name or url,
        }).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error("RSS 구독 등록 실패 (%s): %s", url, e)
        return None


def update_last_fetched(subscription_id: str) -> None:
    """마지막 수집 시각 갱신"""
    try:
        db = get_db()
        db.table("subscriptions").update(
            {"last_fetched_at": "now()"}
        ).eq("id", subscription_id).execute()
    except Exception as e:
        logger.error("last_fetched_at 갱신 실패 (id=%s): %s", subscription_id, e)


def delete_subscription(subscription_id: str) -> bool:
    """RSS 구독 삭제. 성공 시 True"""
    try:
        db = get_db()
        db.table("subscriptions").delete().eq("id", subscription_id).execute()
        return True
    except Exception as e:
        logger.error("RSS 구독 삭제 실패 (id=%s): %s", subscription_id, e)
        return False


def url_already_saved(url: str) -> bool:
    """해당 URL이 이미 notes 테이블에 저장되어 있는지 확인 (중복 방지)"""
    try:
        db = get_db()
        result = db.table("notes").select("id").eq("url", url).limit(1).execute()
        return len(result.data) > 0
    except Exception as e:
        logger.error("URL 중복 확인 실패 (%s): %s", url, e)
        return False
