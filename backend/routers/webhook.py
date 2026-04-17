"""
routers/webhook.py — 카카오·텔레그램 메시지 수신 처리
비즈니스 로직 없음: 수신 → services/classifier → db/notes 호출
"""
import logging
from typing import Any

from fastapi import APIRouter, Request, Response, HTTPException

from config import settings
from services.classifier import classify_content
from services.fetcher import fetch_url_content
from db.notes import insert_note

logger = logging.getLogger(__name__)
router = APIRouter()


# ─────────────────────────────────────────
# 텔레그램 Webhook
# ─────────────────────────────────────────

@router.post("/telegram")
async def telegram_webhook(request: Request) -> Response:
    """
    텔레그램 봇 메시지 수신.
    항상 200 반환 (재시도 루프 방지).
    """
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        # 잘못된 JSON도 200 반환
        return Response(status_code=200)

    message = body.get("message") or body.get("edited_message")
    if not message:
        return Response(status_code=200)

    # 보안: 나의 Telegram User ID만 처리
    sender_id = str(message.get("from", {}).get("id", ""))
    if not _is_allowed_user(sender_id):
        logger.warning("허용되지 않은 텔레그램 사용자: %s", sender_id)
        return Response(status_code=200)

    # 텍스트 또는 링크 추출
    text: str = message.get("text", "").strip()
    if not text:
        return Response(status_code=200)

    # URL 추출 (첫 번째 entity가 URL인 경우)
    url: str | None = None
    entities = message.get("entities", [])
    for entity in entities:
        if entity.get("type") == "url":
            offset = entity["offset"]
            length = entity["length"]
            url = text[offset: offset + length]
            break

    # Claude로 분류 후 Supabase 저장 (비동기 처리를 위해 백그라운드 태스크 사용)
    await _process_and_save(
        source="telegram",
        raw_content=text,
        url=url,
        metadata={
            "chat_id": message.get("chat", {}).get("id"),
            "message_id": message.get("message_id"),
        },
    )

    return Response(status_code=200)


# ─────────────────────────────────────────
# 카카오 Webhook (Webhook URL 검증 + 메시지 수신)
# ─────────────────────────────────────────

@router.get("/kakao")
async def kakao_verify(hub_verify_token: str, hub_challenge: str) -> Response:
    """카카오 Webhook URL 검증 (GET 요청)"""
    if hub_verify_token != settings.KAKAO_VERIFY_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid verify token")
    return Response(content=hub_challenge, media_type="text/plain")


@router.post("/kakao")
async def kakao_webhook(request: Request) -> Response:
    """카카오 메시지 수신. 항상 200 반환."""
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        return Response(status_code=200)

    # TODO(phase2): 카카오 메시지 파싱 로직 구현
    # 현재는 텔레그램 우선 MVP
    text: str = body.get("content", "").strip()
    if not text:
        return Response(status_code=200)

    await _process_and_save(source="kakao", raw_content=text)
    return Response(status_code=200)


# ─────────────────────────────────────────
# 내부 헬퍼
# ─────────────────────────────────────────

def _is_allowed_user(user_id: str) -> bool:
    """나의 Telegram User ID 화이트리스트 검사"""
    return user_id == settings.TELEGRAM_ALLOWED_USER_ID


async def _process_and_save(
    source: str,
    raw_content: str,
    url: str | None = None,
    metadata: dict | None = None,
) -> None:
    """Claude 분류 후 Supabase 저장 (에러 발생 시 raw_content만 저장)"""
    # URL이 있으면 본문 크롤링 후 분류에 활용
    content_for_classify = raw_content
    if url:
        fetched = fetch_url_content(url)
        if fetched:
            content_for_classify = fetched
            logger.info("URL 본문 추출 성공: %s (%d자)", url, len(fetched))

    classify_result = classify_content(content_for_classify)

    insert_note(
        source=source,
        raw_content=raw_content,
        summary=classify_result.get("summary", ""),
        keywords=classify_result.get("keywords", []),
        category=classify_result.get("category", "기타"),
        content_type=classify_result.get("content_type", "other"),
        url=url,
        metadata=metadata,
    )
