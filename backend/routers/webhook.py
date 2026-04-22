"""
routers/webhook.py — 카카오·텔레그램 메시지 수신 처리
비즈니스 로직 없음: 수신 → services/classifier → db/notes 호출
"""
import hashlib
import hmac
import logging
from typing import Any

from fastapi import APIRouter, Request, Response, HTTPException

import httpx

from config import settings
from services.classifier import classify_content
from services.fetcher import fetch_url_content
from db.notes import insert_note, get_notes, get_stats

logger = logging.getLogger(__name__)
router = APIRouter()


def _verify_telegram_signature(secret: str, body_bytes: bytes, signature_header: str | None) -> bool:
    """
    Telegram Webhook 서명 검증.
    BotFather에서 설정한 secret_token으로 HMAC-SHA256 검증.
    secret이 설정되지 않은 경우 검증 건너뜀 (하위 호환).
    """
    if not secret:
        return True
    if not signature_header:
        return False
    expected = hmac.new(
        key=hashlib.sha256(secret.encode()).digest(),
        msg=body_bytes,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature_header)


# ─────────────────────────────────────────
# 텔레그램 Webhook
# ─────────────────────────────────────────

@router.post("/telegram")
async def telegram_webhook(request: Request) -> Response:
    """
    텔레그램 봇 메시지 수신.
    항상 200 반환 (재시도 루프 방지).
    """
    # 서명 검증 (TELEGRAM_WEBHOOK_SECRET 설정 시)
    body_bytes = await request.body()
    signature = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if not _verify_telegram_signature(settings.TELEGRAM_WEBHOOK_SECRET, body_bytes, signature):
        logger.warning("Telegram Webhook 서명 검증 실패")
        return Response(status_code=200)

    try:
        import json
        body: dict[str, Any] = json.loads(body_bytes)
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

    chat_id = message.get("chat", {}).get("id")

    # 명령어 처리 (/search, /today, /list, /help, /stats)
    if text.startswith("/"):
        await _handle_command(text, chat_id)
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

    # 일정 감지 → Google Calendar 자동 등록
    await _detect_and_schedule(text)
    await _process_and_save(
        source="telegram",
        raw_content=text,
        url=url,
        metadata={
            "chat_id": chat_id,
            "message_id": message.get("message_id"),
        },
    )
    await _send_telegram(chat_id, "✅ 노트가 저장되었습니다!")

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


async def _send_telegram(chat_id: int | None, text: str) -> None:
    """텔레그램 메시지 전송 (Markdown 지원). 실패 시 로그만 남김."""
    if not chat_id or not settings.TELEGRAM_BOT_TOKEN:
        return
    try:
        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
            })
    except Exception as e:
        logger.error("텔레그램 메시지 전송 실패: %s", e)


async def _handle_command(text: str, chat_id: int | None) -> None:
    """
    텔레그램 봇 명령어 처리.
    /search <키워드> — 노트 검색
    /today — 오늘 저장된 노트 목록
    /list — 최근 5개 노트
    /stats — 통계 요약
    /help — 명령어 안내
    """
    parts = text.strip().split(None, 1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd in ("/search", "/search@myvaultbot"):
        if not arg:
            await _send_telegram(chat_id, "사용법: `/search 키워드`")
            return
        notes = get_notes(query=arg, limit=5)
        if not notes:
            await _send_telegram(chat_id, f"🔍 *{arg}* 검색 결과가 없습니다.")
            return
        lines = [f"🔍 *{arg}* 검색 결과 ({len(notes)}개)\n"]
        for n in notes:
            summary = (n.get("summary") or "")[:80]
            cat = n.get("category", "기타")
            lines.append(f"• [{cat}] {summary}")
        await _send_telegram(chat_id, "\n".join(lines))

    elif cmd in ("/today", "/today@myvaultbot"):
        from datetime import datetime, timedelta, timezone
        KST = timezone(timedelta(hours=9))
        today = datetime.now(KST).strftime("%Y-%m-%d")
        notes = get_notes(query=today, limit=10)
        if not notes:
            await _send_telegram(chat_id, f"📅 오늘 ({today}) 저장된 노트가 없습니다.")
            return
        lines = [f"📅 오늘 저장된 노트 ({len(notes)}개)\n"]
        for n in notes:
            summary = (n.get("summary") or n.get("raw_content") or "")[:60]
            lines.append(f"• {summary}")
        await _send_telegram(chat_id, "\n".join(lines))

    elif cmd in ("/list", "/list@myvaultbot"):
        notes = get_notes(limit=5)
        if not notes:
            await _send_telegram(chat_id, "저장된 노트가 없습니다.")
            return
        lines = ["📋 *최근 노트 5개*\n"]
        for n in notes:
            summary = (n.get("summary") or "")[:70]
            cat = n.get("category", "기타")
            lines.append(f"• [{cat}] {summary}")
        await _send_telegram(chat_id, "\n".join(lines))

    elif cmd in ("/stats", "/stats@myvaultbot"):
        s = get_stats()
        top_cats = s.get("by_category", [])[:3]
        cat_lines = " | ".join(f"{c['name']} {c['count']}개" for c in top_cats)
        msg = (
            f"📊 *MyVault 통계*\n\n"
            f"전체 노트: *{s['total']}개*\n"
            f"오늘: *{s['today']}개*\n"
            f"이번 주: *{s['this_week']}개*\n"
            f"카테고리 TOP3: {cat_lines}"
        )
        await _send_telegram(chat_id, msg)

    elif cmd in ("/help", "/help@myvaultbot", "/start"):
        help_text = (
            "🤖 *MyVault 봇 명령어*\n\n"
            "/search `키워드` — 노트 검색\n"
            "/list — 최근 5개 노트\n"
            "/today — 오늘 저장된 노트\n"
            "/stats — 통계 요약\n"
            "/help — 이 메시지\n\n"
            "명령어 없이 텍스트/링크를 보내면 자동으로 저장됩니다."
        )
        await _send_telegram(chat_id, help_text)

    else:
        await _send_telegram(chat_id, f"알 수 없는 명령어입니다. /help 로 명령어를 확인하세요.")


async def _detect_and_schedule(text: str) -> None:
    """
    텍스트에서 일정을 감지하면 Google Calendar에 자동 등록.
    실패해도 전체 처리 흐름에 영향 없음.
    """
    try:
        from services.schedule_detector import detect_schedule
        from services.calendar import create_event

        schedule = detect_schedule(text)
        if not schedule:
            return

        event_url = create_event(
            title=schedule["title"],
            start=schedule["start"],
            end=schedule["end"],
            location=schedule.get("location", ""),
            description=schedule.get("description", ""),
        )
        if event_url:
            logger.info("일정 자동 등록 완료: %s → %s", schedule["title"], event_url)
    except Exception as e:
        logger.error("일정 감지/등록 중 오류 (무시): %s", e)


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
        highlights=classify_result.get("highlights", []),
        keywords=classify_result.get("keywords", []),
        category=classify_result.get("category", "기타"),
        content_type=classify_result.get("content_type", "other"),
        url=url,
        metadata=metadata,
    )
