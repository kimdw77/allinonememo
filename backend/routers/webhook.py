"""
routers/webhook.py — 카카오·텔레그램 메시지 수신 처리
비즈니스 로직 없음: 수신 → agents/router → 각 에이전트 호출
"""
import hashlib
import hmac
import logging
from collections import OrderedDict
from typing import Any

from fastapi import APIRouter, Request, Response, HTTPException

import httpx

from config import settings
from db.notes import get_notes, get_stats

logger = logging.getLogger(__name__)
router = APIRouter()

# 중복 webhook 방지: 최근 2000개 update_id 캐시 (FIFO)
_processed_updates: OrderedDict[int, bool] = OrderedDict()
_MAX_UPDATE_CACHE = 2000


def _seen_update_id(update_id: int) -> bool:
    """이미 처리한 update_id면 True. 새 ID면 등록 후 False."""
    if update_id in _processed_updates:
        return True
    _processed_updates[update_id] = True
    if len(_processed_updates) > _MAX_UPDATE_CACHE:
        _processed_updates.popitem(last=False)
    return False


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

    # update_id 중복 체크 — Telegram 재시도에 의한 다중 처리 방지
    update_id: int | None = body.get("update_id")
    if update_id and _seen_update_id(update_id):
        logger.warning("중복 update_id 무시: %d", update_id)
        return Response(status_code=200)

    # 인라인 버튼 응답 처리 (✅ 저장 / ❌ 취소)
    callback_query = body.get("callback_query")
    if callback_query:
        sender_id = str(callback_query.get("from", {}).get("id", ""))
        if _is_allowed_user(sender_id):
            await _handle_callback_query(callback_query)
        return Response(status_code=200)

    # edited_message는 미디어(사진·음성) 재처리 방지 — 텍스트 편집만 허용
    if "edited_message" in body and "message" not in body:
        edited = body["edited_message"]
        has_media = (
            edited.get("photo")
            or edited.get("voice")
            or edited.get("audio")
            or edited.get("document", {}).get("mime_type", "").startswith("image/")
        )
        if has_media:
            return Response(status_code=200)
        message: dict = edited
    else:
        message = body.get("message")

    if not message:
        return Response(status_code=200)

    # 보안: 나의 Telegram User ID만 처리
    sender_id = str(message.get("from", {}).get("id", ""))
    if not _is_allowed_user(sender_id):
        logger.warning("허용되지 않은 텔레그램 사용자: %s", sender_id)
        return Response(status_code=200)

    chat_id = message.get("chat", {}).get("id")

    # 사진 처리
    if message.get("photo") or (
        message.get("document", {}).get("mime_type", "").startswith("image/")
    ):
        await _handle_photo(message, chat_id)
        return Response(status_code=200)

    # 음성/오디오 처리
    if message.get("voice") or message.get("audio"):
        await _handle_voice(message, chat_id)
        return Response(status_code=200)

    # 텍스트 또는 링크 추출
    text: str = message.get("text", "").strip()
    if not text:
        return Response(status_code=200)

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

    await _run_router_agent(
        content=text,
        chat_id=chat_id,
        metadata={
            "chat_id": chat_id,
            "message_id": message.get("message_id"),
            "url": url,
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


async def _send_telegram(chat_id: int | None, text: str, parse_mode: str = "Markdown") -> None:
    """텔레그램 메시지 전송. 실패 시 로그만 남김."""
    if not chat_id or not settings.TELEGRAM_BOT_TOKEN:
        return
    try:
        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
            })
    except Exception as e:
        logger.error("텔레그램 메시지 전송 실패: %s", e)


async def _send_telegram_with_keyboard(
    chat_id: int | None,
    text: str,
    inline_keyboard: list[list[dict]],
) -> None:
    """인라인 버튼이 포함된 텔레그램 메시지 전송."""
    if not chat_id or not settings.TELEGRAM_BOT_TOKEN:
        return
    try:
        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "reply_markup": {"inline_keyboard": inline_keyboard},
            })
    except Exception as e:
        logger.error("텔레그램 인라인 버튼 메시지 전송 실패: %s", e)


async def _answer_callback_query(callback_query_id: str, text: str = "") -> None:
    """Telegram callback_query 수신 확인 응답 (필수, 미응답 시 로딩 표시 지속)."""
    if not settings.TELEGRAM_BOT_TOKEN:
        return
    try:
        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/answerCallbackQuery"
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(url, json={"callback_query_id": callback_query_id, "text": text})
    except Exception as e:
        logger.error("callback_query 응답 실패: %s", e)


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

    elif cmd in ("/cal", "/cal@myvaultbot", "/일정", "/일정@myvaultbot"):
        if not arg:
            await _send_telegram(chat_id, "사용법: `/cal 내일 오전 10시 팀 미팅`")
            return
        try:
            from services.schedule_detector import detect_schedule
            from services.calendar import create_event
            schedule = detect_schedule(arg)
            if not schedule:
                await _send_telegram(chat_id, "❌ 일정 정보를 인식하지 못했습니다.\n날짜·시간을 포함해서 다시 입력해 주세요.\n예) `/일정 내일 오후 3시 치과 예약`")
                return
            event_url = create_event(
                title=schedule["title"],
                start=schedule["start"],
                end=schedule["end"],
                location=schedule.get("location", ""),
                description=schedule.get("description", ""),
            )
            if event_url:
                await _send_telegram(
                    chat_id,
                    f"📅 캘린더에 등록했습니다!\n*{schedule['title']}*\n{schedule['start'][:16].replace('T', ' ')}\n[캘린더에서 보기]({event_url})",
                )
                # 30분 전 알림 스케줄링
                try:
                    from datetime import datetime, timedelta, timezone
                    from services.scheduler_instance import get_scheduler
                    event_start = datetime.fromisoformat(schedule["start"])
                    if event_start.tzinfo is None:
                        event_start = event_start.replace(tzinfo=timezone(timedelta(hours=9)))
                    reminder_time = event_start - timedelta(minutes=30)
                    if reminder_time > datetime.now(reminder_time.tzinfo):
                        sched = get_scheduler()
                        if sched:
                            import asyncio
                            title = schedule["title"]
                            start_str = schedule["start"][:16].replace("T", " ")
                            sched.add_job(
                                lambda: asyncio.run(_send_telegram(
                                    chat_id,
                                    f"⏰ 30분 후 일정!\n*{title}*\n{start_str}",
                                )),
                                "date",
                                run_date=reminder_time,
                                id=f"cal_reminder_{event_url[-10:]}",
                                replace_existing=True,
                            )
                            logger.info("캘린더 알림 예약: %s (30분 전)", reminder_time)
                except Exception as reminder_err:
                    logger.warning("알림 스케줄링 실패 (무시): %s", reminder_err)
            else:
                await _send_telegram(chat_id, "❌ 캘린더 등록 실패 (GOOGLE 환경변수 확인 필요)")
        except Exception as e:
            logger.error("/일정 처리 실패: %s", e)
            await _send_telegram(chat_id, "❌ 일정 등록 중 오류가 발생했습니다.")

    elif cmd in ("/task", "/task@myvaultbot"):
        # TaskExtractorAgent 강제 실행 (Router 의도 분류 없이)
        if not arg:
            await _send_telegram(chat_id, "사용법: `/task 내일까지 보고서 제출, 다음주 팀미팅 잡기`")
            return
        from agents.task_extractor import TaskExtractorAgent
        from agents.base import AgentInput
        out = TaskExtractorAgent().run(AgentInput(
            content=arg, source="telegram",
            chat_id=chat_id, metadata={"chat_id": chat_id},
        ))
        await _send_telegram(chat_id, out.reply_text or "⚠️ 추출된 태스크가 없습니다.")

    elif cmd in ("/critique", "/critique@myvaultbot"):
        # CriticAgent 강제 실행
        if not arg:
            await _send_telegram(chat_id, "사용법: `/critique 검토받을 내용`")
            return
        from agents.critic import CriticAgent
        from agents.base import AgentInput
        out = CriticAgent().run(AgentInput(
            content=arg, source="telegram",
            chat_id=chat_id, metadata={"chat_id": chat_id},
        ))
        await _send_telegram(chat_id, out.reply_text or "❌ 분석 실패")

    elif cmd in ("/report", "/report@myvaultbot"):
        # WeeklyReportAgent 강제 실행
        from agents.weekly_report import WeeklyReportAgent
        from agents.base import AgentInput
        out = WeeklyReportAgent().run(AgentInput(
            content="", source="telegram",
            chat_id=chat_id, metadata={"chat_id": chat_id},
        ))
        await _send_telegram(chat_id, out.reply_text or "❌ 보고서 생성 실패")

    elif cmd in ("/yes", "/yes@myvaultbot"):
        from db.thoughts import get_pending_confirm_thought, update_thought_status
        from services.classifier import classify_content
        from db.notes import insert_note
        from agents.pipeline import _schedule_sync
        from utils.trace_id import new_trace_id
        thought = get_pending_confirm_thought()
        if not thought:
            await _send_telegram(chat_id, "⚠️ 확인 대기 중인 메모가 없습니다.")
            return
        result = classify_content(thought["raw_input"])
        note = insert_note(
            source="telegram",
            raw_content=thought["raw_input"],
            summary=result.get("summary", ""),
            highlights=result.get("highlights", []),
            keywords=result.get("keywords", []),
            category=result.get("category", "기타"),
            content_type=result.get("content_type", "other"),
            metadata={"confirmed_by": "user"},
        )
        update_thought_status(thought["id"], "processed")
        if note:
            _schedule_sync(note, new_trace_id())
        await _send_telegram(chat_id, "✅ 저장 완료!")

    elif cmd in ("/no", "/no@myvaultbot"):
        from db.thoughts import get_pending_confirm_thought, update_thought_status
        thought = get_pending_confirm_thought()
        if not thought:
            await _send_telegram(chat_id, "⚠️ 확인 대기 중인 메모가 없습니다.")
            return
        update_thought_status(thought["id"], "rejected")
        await _send_telegram(chat_id, "❌ 저장을 취소했습니다.")

    elif cmd in ("/wiki", "/wiki@myvaultbot"):
        # 특정 노트의 wiki 컴파일 강제 실행 (arg = note_id 또는 최근 노트)
        from agents.wiki_compiler import compile_wiki
        from services.github_sync import determine_domain
        from utils.trace_id import new_trace_id
        notes = get_notes(limit=1)
        if not notes:
            await _send_telegram(chat_id, "⚠️ 저장된 노트가 없습니다.")
            return
        note = notes[0]
        domain = determine_domain(note)
        trace = new_trace_id()
        await _send_telegram(chat_id, f"🔨 Wiki 컴파일 시작 (노트: `{(note.get('id') or '')[:8]}`)…")
        try:
            result = await compile_wiki(note, domain, trace)
            if result.get("error"):
                await _send_telegram(chat_id, f"❌ 오류: {result['error']}")
            else:
                created = result.get("pages_created", 0)
                updated = result.get("pages_updated", 0)
                queued = result.get("pages_queued", 0)
                rejected = result.get("pages_rejected", 0)
                await _send_telegram(
                    chat_id,
                    f"✅ Wiki 컴파일 완료\n"
                    f"신규: {created}  업데이트: {updated}  "
                    f"큐: {queued}  거절: {rejected}",
                )
        except Exception as e:
            await _send_telegram(chat_id, f"❌ Wiki 컴파일 실패: {e}")

    elif cmd in ("/lint", "/lint@myvaultbot"):
        # Wiki lint 실행 (arg = domain 이름 또는 전체)
        from agents.wiki_reporter import lint_wiki
        domain_arg = arg.strip() or None
        await _send_telegram(chat_id, f"🔍 Wiki Lint 실행 중{'(' + domain_arg + ')' if domain_arg else '(전체)'}…")
        try:
            result = await lint_wiki(domain=domain_arg)
            if result.get("error"):
                await _send_telegram(chat_id, f"❌ {result['error']}")
                return
            total = result.get("total", 0)
            errors = result.get("errors") or []
            warnings = result.get("warnings") or []
            lines = [f"📋 *Wiki Lint 결과* (총 {total}개 페이지)"]
            if errors:
                lines.append(f"\n🚨 오류 {len(errors)}건")
                for e in errors[:5]:
                    lines.append(f"  • `{e['path'].split('/')[-1]}`: {e['msg']}")
                if len(errors) > 5:
                    lines.append(f"  … 외 {len(errors) - 5}건")
            if warnings:
                lines.append(f"\n⚠️ 경고 {len(warnings)}건")
                for w in warnings[:3]:
                    lines.append(f"  • `{w['path'].split('/')[-1]}`: {w['msg']}")
                if len(warnings) > 3:
                    lines.append(f"  … 외 {len(warnings) - 3}건")
            if not errors and not warnings:
                lines.append("\n✅ 이상 없음")
            await _send_telegram(chat_id, "\n".join(lines))
        except Exception as e:
            await _send_telegram(chat_id, f"❌ Lint 실패: {e}")

    elif cmd in ("/report-wiki", "/report-wiki@myvaultbot"):
        # 주간 wiki 보고서 즉시 실행
        from agents.wiki_reporter import send_weekly_wiki_report
        await _send_telegram(chat_id, "📖 주간 Wiki 보고서 생성 중…")
        try:
            await send_weekly_wiki_report()
        except Exception as e:
            await _send_telegram(chat_id, f"❌ 보고서 생성 실패: {e}")

    elif cmd in ("/help", "/help@myvaultbot", "/start"):
        help_text = (
            "🤖 *MyVault 에이전트 명령어*\n\n"
            "🧠 *AI 에이전트*\n"
            "/task `내용` — 태스크 추출·저장\n"
            "/critique `내용` — 비판적 검토·피드백\n"
            "/report — 주간 보고서 생성\n\n"
            "📖 *Wiki (Phase 9)*\n"
            "/wiki — 최근 노트로 wiki 컴파일\n"
            "/lint `[도메인]` — wiki 페이지 lint 검사\n"
            "/report\\-wiki — 주간 wiki 변경 보고서\n\n"
            "📅 *일정·검색*\n"
            "/cal `내용` — Google Calendar 등록\n"
            "/search `키워드` — 노트 검색\n"
            "/list — 최근 5개 노트\n"
            "/today — 오늘 저장된 노트\n"
            "/stats — 통계 요약\n"
            "/help — 이 메시지\n\n"
            "명령어 없이 텍스트/링크/사진/음성을 보내면 AI가 자동 분류합니다."
        )
        await _send_telegram(chat_id, help_text)

    else:
        await _send_telegram(chat_id, "알 수 없는 명령어입니다. /help 로 명령어를 확인하세요.")


async def _download_telegram_file(file_id: str) -> tuple[bytes, str]:
    """
    Telegram file_id로 실제 파일을 다운로드.
    (파일 바이트, 파일 경로) 반환. 실패 시 (b"", "") 반환.
    """
    token = settings.TELEGRAM_BOT_TOKEN
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(
                f"https://api.telegram.org/bot{token}/getFile",
                params={"file_id": file_id},
            )
            r.raise_for_status()
            file_path: str = r.json()["result"]["file_path"]

            r2 = await client.get(
                f"https://api.telegram.org/file/bot{token}/{file_path}"
            )
            r2.raise_for_status()
            return r2.content, file_path
    except Exception as e:
        logger.error("Telegram 파일 다운로드 실패 (file_id=%s): %s", file_id, e)
        return b"", ""


async def _handle_photo(message: dict, chat_id: int | None) -> None:
    """사진 메시지: 다운로드 → Claude Vision 분석 → (신문이면 웹검색) → 저장"""
    # photo 배열의 마지막 요소가 최고 해상도
    photos = message.get("photo")
    if photos:
        file_id = photos[-1]["file_id"]
    else:
        # document(이미지 파일)인 경우
        file_id = message["document"]["file_id"]

    caption: str = message.get("caption", "")

    try:
        file_bytes, file_path = await _download_telegram_file(file_id)
        if not file_bytes:
            await _send_telegram(chat_id, "❌ 이미지 다운로드 실패")
            return

        ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else "jpg"
        mime_map = {
            "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "png": "image/png", "gif": "image/gif", "webp": "image/webp",
        }
        media_type = mime_map.get(ext, "image/jpeg")

        from services.classifier import analyze_image
        result = analyze_image(file_bytes, media_type)

        # 분석 완전 실패: summary·keywords 모두 비어있으면 사용자에게 경고
        analysis_failed = not result.get("summary") and not result.get("keywords")
        if analysis_failed:
            logger.warning("이미지 분석 결과 비어있음 (fallback). file_id=%s, media_type=%s", file_id, media_type)

        # raw_content: 캡션 → OCR 텍스트 → 요약 순 우선
        raw_content = caption or result.get("ocr_text") or result.get("summary") or "[이미지]"

        # Supabase Storage에 원본 사진 업로드
        file_url: str | None = None
        try:
            from services.storage import upload_file
            file_url = upload_file(file_bytes, "photos", ext, media_type)
        except Exception as up_err:
            logger.warning("사진 Storage 업로드 실패 (저장은 계속): %s", up_err)

        # 신문·기사 이미지이면 관련 링크·이미지 웹검색
        related_links: dict = {}
        is_news = result.get("is_newspaper") or result.get("content_type") in ("newspaper", "article")
        search_query = (
            result.get("search_query")
            or result.get("news_headline")
            or " ".join(result.get("keywords", [])[:4])
        )
        if is_news and search_query:
            try:
                from services.news_searcher import search_related_articles
                related_links = await search_related_articles(search_query)
                logger.info("관련 기사 검색 완료: %d건", len(related_links.get("articles", [])))
            except Exception as search_err:
                logger.error("관련 기사 검색 실패 (저장은 계속): %s", search_err)

        content_type = result.get("content_type", "image")
        if result.get("is_newspaper"):
            content_type = "newspaper"

        from db.notes import insert_note
        insert_note(
            source="telegram",
            raw_content=raw_content,
            summary=result.get("summary", ""),
            highlights=result.get("highlights", []),
            keywords=result.get("keywords", []),
            category=result.get("category", "기타"),
            content_type=content_type,
            related_links=related_links,
            file_url=file_url,
            metadata={
                "chat_id": chat_id,
                "message_id": message.get("message_id"),
                "caption": caption,
                "news_headline": result.get("news_headline", ""),
                "search_query": search_query if is_news else "",
            },
        )

        # 텔레그램 응답: 분석 실패 시 경고, 신문이면 요약 + 관련 링크, 일반이면 간단 확인
        if analysis_failed:
            await _send_telegram(
                chat_id,
                "⚠️ 이미지는 저장했지만 AI 해석에 실패했습니다. "
                f"(포맷: {media_type}, 크기: {len(file_bytes)//1024}KB)\n"
                "잠시 후 다시 보내거나, 다른 포맷(JPG·PNG)으로 시도해보세요.",
            )
            return

        if is_news:
            import html as html_lib
            lines: list[str] = ["📰 <b>신문 기사 저장 완료!</b>\n"]

            highlights = result.get("highlights", [])
            if highlights:
                lines.append("<b>요약</b>")
                for i, h in enumerate(highlights[:3], 1):
                    lines.append(f"{i}. {html_lib.escape(h[:90])}")

            articles = related_links.get("articles", [])
            if articles:
                lines.append("\n📰 <b>관련 기사</b>")
                for a in articles[:3]:
                    title = html_lib.escape((a.get("title") or "")[:50])
                    url = a.get("url", "")
                    if title and url:
                        lines.append(f'• <a href="{url}">{title}</a>')

            await _send_telegram(chat_id, "\n".join(lines), parse_mode="HTML")
        else:
            preview = (result.get("summary") or "")[:100]
            await _send_telegram(chat_id, f"🖼️ 이미지가 저장되었습니다!\n{preview}")

    except Exception as e:
        logger.error("이미지 처리 실패: %s", e)
        await _send_telegram(chat_id, "❌ 이미지 처리 중 오류가 발생했습니다.")


async def _handle_voice(message: dict, chat_id: int | None) -> None:
    """음성 메시지: 다운로드 → Whisper STT → 분류 저장"""
    voice_obj = message.get("voice") or message.get("audio")
    file_id = voice_obj["file_id"]

    try:
        file_bytes, file_path = await _download_telegram_file(file_id)
        if not file_bytes:
            await _send_telegram(chat_id, "❌ 음성 파일 다운로드 실패")
            return

        from services.transcriber import transcribe_voice
        transcribed = transcribe_voice(file_bytes, file_path)
        if not transcribed:
            await _send_telegram(chat_id, "❌ 음성 인식 실패 (OPENAI_API_KEY 확인 필요)")
            return

        # Supabase Storage에 원본 음성 업로드
        voice_file_url: str | None = None
        try:
            from services.storage import upload_file
            voice_ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else "ogg"
            voice_file_url = upload_file(
                file_bytes, "voices", voice_ext, f"audio/{voice_ext}"
            )
        except Exception as up_err:
            logger.warning("음성 Storage 업로드 실패 (저장은 계속): %s", up_err)

        await _run_router_agent(
            content=transcribed,
            chat_id=chat_id,
            metadata={
                "chat_id": chat_id,
                "message_id": message.get("message_id"),
                "type": "voice",
                "file_url": voice_file_url,
            },
        )

    except Exception as e:
        logger.error("음성 처리 실패: %s", e)
        await _send_telegram(chat_id, "❌ 음성 처리 중 오류가 발생했습니다.")


async def _handle_callback_query(callback_query: dict) -> None:
    """인라인 버튼 클릭 처리 (✅ 저장 / ❌ 취소)."""
    query_id = callback_query.get("id", "")
    data = callback_query.get("data", "")
    chat_id = callback_query.get("message", {}).get("chat", {}).get("id")

    from db.thoughts import get_pending_confirm_thought, update_thought_status

    if data == "confirm_yes":
        await _answer_callback_query(query_id, "저장합니다!")
        thought = get_pending_confirm_thought()
        if not thought:
            await _send_telegram(chat_id, "⚠️ 확인 대기 중인 메모가 없습니다.")
            return
        from services.classifier import classify_content
        from db.notes import insert_note
        from agents.pipeline import _schedule_sync
        from utils.trace_id import new_trace_id
        result = classify_content(thought["raw_input"])
        note = insert_note(
            source="telegram",
            raw_content=thought["raw_input"],
            summary=result.get("summary", ""),
            highlights=result.get("highlights", []),
            keywords=result.get("keywords", []),
            category=result.get("category", "기타"),
            content_type=result.get("content_type", "other"),
            metadata={"confirmed_by": "user"},
        )
        update_thought_status(thought["id"], "processed")
        if note:
            _schedule_sync(note, new_trace_id())
        await _send_telegram(chat_id, "✅ 저장 완료!")

    elif data == "confirm_no":
        await _answer_callback_query(query_id, "취소합니다.")
        thought = get_pending_confirm_thought()
        if thought:
            update_thought_status(thought["id"], "rejected")
        await _send_telegram(chat_id, "❌ 저장을 취소했습니다.")

    else:
        await _answer_callback_query(query_id)


async def _run_router_agent(
    content: str,
    chat_id: int | None,
    metadata: dict | None = None,
    source: str = "telegram",
) -> None:
    """AgentPipeline 실행 후 결과 텔레그램 전송. ask_user이면 인라인 버튼 포함."""
    from agents.pipeline import AgentPipeline
    from agents.base import AgentInput
    from utils.trace_id import new_trace_id

    trace_id = new_trace_id()
    out = AgentPipeline().run(
        inp=AgentInput(
            content=content,
            source=source,
            chat_id=chat_id,
            metadata=metadata or {},
        ),
        trace_id=trace_id,
    )

    if out.result.get("final_action") == "ask_user":
        await _send_telegram_with_keyboard(
            chat_id,
            out.reply_text or "⚠️ 확인이 필요합니다. 저장하시겠습니까?",
            [[
                {"text": "✅ 저장", "callback_data": "confirm_yes"},
                {"text": "❌ 취소", "callback_data": "confirm_no"},
            ]],
        )
    else:
        await _send_telegram(chat_id, out.reply_text or "✅ 처리 완료")
