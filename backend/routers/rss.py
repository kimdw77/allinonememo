"""
routers/rss.py — RSS 구독 관리 API
"""
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl

from db.subscriptions import (
    get_active_subscriptions,
    insert_subscription,
    delete_subscription,
)
from services.rss_fetcher import fetch_all_feeds

logger = logging.getLogger(__name__)
router = APIRouter()


class SubscribeRequest(BaseModel):
    url: HttpUrl
    name: str = ""


@router.get("")
async def list_subscriptions() -> list[dict]:
    """등록된 RSS 구독 목록 반환"""
    return get_active_subscriptions()


@router.post("", status_code=201)
async def subscribe(body: SubscribeRequest) -> dict:
    """RSS 피드 구독 등록"""
    result = insert_subscription(str(body.url), body.name)
    if not result:
        raise HTTPException(status_code=500, detail="구독 등록 실패")
    return result


@router.delete("/{subscription_id}", status_code=204)
async def unsubscribe(subscription_id: str) -> None:
    """RSS 구독 삭제"""
    success = delete_subscription(subscription_id)
    if not success:
        raise HTTPException(status_code=404, detail="구독을 찾을 수 없습니다")


@router.post("/fetch-now", status_code=200)
async def fetch_now() -> dict:
    """모든 RSS 피드 즉시 수집 (수동 트리거)"""
    fetch_all_feeds()
    return {"message": "RSS 수집 완료"}
