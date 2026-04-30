"""
workers/sync_worker.py — GitHub 동기화 비동기 워커 (Phase 9-1)

pipeline.py 에서 asyncio.create_task(enqueue_sync(...)) 로 호출된다.
fire-and-forget: 실패해도 pipeline 응답에 영향 없음.

HARNESS Layer 3 포함:
  3-1. 동기화 지연 모니터링 (push 성공 직후 lag 확인)
  3-2. 실패율 점검 (main.py APScheduler 매시간 호출 → check_fail_rate())
  3-3. 민감정보 오라우팅 즉시 격리 (push 전 validate_routing())
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional

from config import KST, settings

logger = logging.getLogger(__name__)


async def enqueue_sync(note: dict, trace_id: str) -> None:
    """
    노트를 GitHub에 동기화.
    (a) 저장 성공한 note dict 를 받아 처리
    (b) 동기화 실패가 pipeline 응답을 막지 않음 (예외 전파 안 함)
    (c) 예외는 done_callback 이 아닌 내부 try/except 로 sync_status에 기록
    (d) trace_id 는 인자로 명시적 전달 + ContextVar 자동 전파 (이중 보장)
    """
    if not settings.GITHUB_TOKEN or not settings.GITHUB_REPO:
        logger.warning("GITHUB_TOKEN/GITHUB_REPO 미설정 → 동기화 건너뜀 trace=%s", trace_id[:8])
        return

    from db.sync_status import insert_sync, update_sync_status
    from services.github_sync import determine_domain, validate_routing, push_note

    note_id: Optional[str] = note.get("id")
    sync_record = insert_sync(note_id=note_id, trace_id=trace_id, status="pending")
    if not sync_record:
        logger.error("sync_status insert 실패 → 동기화 건너뜀 note_id=%s", note_id)
        return

    sync_id: str = sync_record["id"]

    try:
        # ── HARNESS 3-3: 오라우팅 검증 (push 전 반드시 실행) ──────────
        domain = determine_domain(note)
        validation = validate_routing(note, domain)

        if validation["blocked"]:
            await _handle_quarantine(sync_id, note, trace_id, validation)
            return

        # ── GitHub push (blocking I/O → thread pool 분리) ──────────────
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,           # 기본 ThreadPoolExecutor
            push_note,      # blocking 함수
            note, domain, trace_id,
        )

        # ── 성공 기록 ────────────────────────────────────────────────────
        synced_at = datetime.now(KST)
        update_sync_status(
            sync_id=sync_id,
            status="synced",
            github_path=result["path"],
            github_sha=result["sha"],
            attempts=1,
            synced_at=synced_at,
        )
        logger.info(
            "동기화 완료 | note_id=%s path=%s trace=%s",
            note_id, result["path"], trace_id[:8],
        )

        # ── HARNESS 3-1: 지연 확인 (fire-and-forget) ────────────────────
        asyncio.create_task(_check_lag_alert())

        # ── Phase 9-2: Wiki Compiler (fire-and-forget) ───────────────────
        asyncio.create_task(_run_wiki_compiler(note, domain, trace_id))

    except Exception as exc:
        logger.error("동기화 실패 | note_id=%s: %s trace=%s", note_id, exc, trace_id[:8])
        update_sync_status(
            sync_id=sync_id,
            status="failed",
            last_error=str(exc),
            attempts=1,
        )
        await _send_sync_fail_alert(note_id, trace_id, str(exc))


# ── Phase 9-2: Wiki Compiler 트리거 ──────────────────────────────────


async def _run_wiki_compiler(note: dict, domain: str, trace_id: str) -> None:
    """동기화 성공 후 wiki 컴파일. 실패해도 동기화 결과에 영향 없음."""
    try:
        from agents.wiki_compiler import compile_wiki
        result = await compile_wiki(note, domain, trace_id)
        if result.get("pages_created") or result.get("pages_updated"):
            logger.info(
                "wiki 컴파일 완료 +%d ~%d trace=%s",
                result.get("pages_created", 0),
                result.get("pages_updated", 0),
                trace_id[:8],
            )
    except Exception as e:
        logger.warning("wiki_compiler 실행 실패 (무시): %s trace=%s", e, trace_id[:8])


# ── HARNESS 3-3: 격리 처리 ────────────────────────────────────────────


async def _handle_quarantine(
    sync_id: str,
    note: dict,
    trace_id: str,
    validation: dict,
) -> None:
    """오라우팅 감지 → sync_status = 'quarantined' + 텔레그램 즉시 알림."""
    from db.sync_status import update_sync_status

    note_id = note.get("id") or "?"
    reason = validation.get("reason", "")
    detected = validation.get("detected_keywords", [])

    update_sync_status(sync_id=sync_id, status="quarantined", last_error=reason)
    logger.error(
        "오라우팅 격리! note_id=%s 키워드=%s trace=%s",
        note_id, detected, trace_id[:8],
    )

    msg = (
        f"🚨 *민감정보 오라우팅 감지*\n"
        f"note\\_id: `{note_id[:8]}...`\n"
        f"검출 키워드: `{', '.join(detected)}`\n"
        f"차단 사유: {reason}\n"
        f"trace: `{trace_id[:8]}`\n"
        f"→ `sync\\_status.status = 'quarantined'` 기록\n"
        f"수동 검토 후 `/api/sync/retry/<sync_id>` 로 재처리"
    )
    await _send_telegram(msg)


# ── HARNESS 3-1: 지연 모니터링 ────────────────────────────────────────


async def _check_lag_alert() -> None:
    """최근 1시간 동기화 지연 통계 확인 → 임계치 초과 시 텔레그램 알림."""
    try:
        from db.sync_status import get_sync_lag_stats
        stats = get_sync_lag_stats()
        avg_lag: float = stats.get("avg_lag_seconds", 0.0)
        max_lag: float = stats.get("max_lag_seconds", 0.0)
        threshold: int = settings.SYNC_LAG_ALERT_SECONDS

        if max_lag > 300:
            await _send_telegram(
                f"🚨 *동기화 지연 심각*\n"
                f"최대 지연: {max_lag:.0f}초 (임계치: 300초)\n"
                f"평균 지연: {avg_lag:.0f}초\n즉시 확인 필요"
            )
        elif avg_lag > threshold:
            await _send_telegram(
                f"⚠️ *동기화 지연 경고*\n"
                f"평균 지연: {avg_lag:.0f}초 (임계치: {threshold}초)\n"
                f"최대 지연: {max_lag:.0f}초"
            )
    except Exception as e:
        logger.warning("지연 모니터링 실패 (무시): %s", e)


# ── HARNESS 3-2: 실패율 점검 (APScheduler → main.py 에서 매시간 호출) ──


async def check_fail_rate() -> None:
    """
    최근 24시간 동기화 실패율 점검.
    임계치(SYNC_FAIL_RATE_ALERT_PERCENT) 초과 시 텔레그램 알림 + 실패 목록.
    """
    try:
        from db.sync_status import get_fail_rate_24h, get_failed_syncs
        fail_rate = get_fail_rate_24h()
        threshold = settings.SYNC_FAIL_RATE_ALERT_PERCENT

        if fail_rate > threshold:
            failed = get_failed_syncs(limit=5)
            items = "\n".join(
                f"• `{(r.get('note_id') or '?')[:8]}...` — {(r.get('last_error') or '')[:60]}"
                for r in failed
            )
            await _send_telegram(
                f"⚠️ *동기화 실패율 초과*\n"
                f"24시간 실패율: {fail_rate:.1f}% (임계치: {threshold}%)\n\n"
                f"최근 실패 항목:\n{items}"
            )
    except Exception as e:
        logger.warning("실패율 점검 실패 (무시): %s", e)


# ── 내부 알림 유틸 ────────────────────────────────────────────────────


async def _send_sync_fail_alert(
    note_id: Optional[str], trace_id: str, error: str
) -> None:
    await _send_telegram(
        f"⚠️ *GitHub 동기화 실패*\n"
        f"note\\_id: `{(note_id or '?')[:8]}...`\n"
        f"오류: `{error[:120]}`\n"
        f"trace: `{trace_id[:8]}`\n"
        f"3회 재시도 모두 실패 — `sync\\_status.status = 'failed'`"
    )


async def _send_telegram(message: str) -> None:
    """텔레그램 알림 전송. 실패해도 예외 전파 없음."""
    try:
        import httpx
        token = settings.TELEGRAM_BOT_TOKEN
        chat_id = settings.TELEGRAM_ALLOWED_USER_ID
        if not token or not chat_id:
            logger.warning("텔레그램 환경변수 미설정, 알림 건너뜀")
            return
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"},
            )
    except Exception as e:
        logger.warning("텔레그램 알림 전송 실패 (무시): %s", e)
