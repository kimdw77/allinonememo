"""
main.py — FastAPI 애플리케이션 진입점
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from apscheduler.schedulers.background import BackgroundScheduler

from config import settings
from routers import webhook, notes, rss, categories, sync, stats, tasks

logger = logging.getLogger(__name__)

# Rate limiter (IP 기반)
limiter = Limiter(key_func=get_remote_address)

# 프로덕션에서는 API 문서 비활성화
_docs_url = None if settings.APP_ENV == "production" else "/docs"
_redoc_url = None if settings.APP_ENV == "production" else "/redoc"

app = FastAPI(
    title="MyVault API",
    description="개인 AI 지식저장소 백엔드",
    version="0.1.0",
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    openapi_url=None if settings.APP_ENV == "production" else "/openapi.json",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS 설정 — 명시적 도메인만 허용 (와일드카드 금지)
_allowed_origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
if settings.APP_ENV != "production":
    _allowed_origins.append("http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "PUT"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)

# 라우터 등록
app.include_router(webhook.router, prefix="/webhook", tags=["webhook"])
app.include_router(notes.router, prefix="/api/notes", tags=["notes"])
app.include_router(rss.router, prefix="/api/rss", tags=["rss"])
app.include_router(categories.router, prefix="/api/categories", tags=["categories"])
app.include_router(sync.router, prefix="/api/sync", tags=["sync"])
app.include_router(stats.router, prefix="/api/stats", tags=["stats"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])


@app.on_event("startup")
def start_scheduler() -> None:
    """서버 시작 시 스케줄러 실행"""
    from services.rss_fetcher import fetch_all_feeds
    from services.digest import send_daily_digest

    scheduler = BackgroundScheduler(timezone="Asia/Seoul")
    # RSS 수집: 비활성화 (API 비용 절감)
    # scheduler.add_job(fetch_all_feeds, "interval", minutes=30, id="rss_fetch")
    # 일일 요약: 매일 오전 8시 KST
    scheduler.add_job(send_daily_digest, "cron", hour=8, minute=0, id="daily_digest")
    # Google Drive 백업: 매주 일요일 새벽 2시 KST
    from services.gdrive_backup import backup_notes_to_drive
    scheduler.add_job(backup_notes_to_drive, "cron", day_of_week="sun", hour=2, minute=0, id="gdrive_backup")
    # 주간 보고서: 매주 월요일 오전 9시 KST (노트 + 태스크 통합)
    from agents.weekly_report import send_weekly_report
    import asyncio
    scheduler.add_job(
        lambda: asyncio.run(send_weekly_report()),
        "cron", day_of_week="mon", hour=9, minute=0, id="weekly_report",
    )
    # HARNESS 3-2: GitHub 동기화 실패율 점검 (매시간)
    from workers.sync_worker import check_fail_rate
    scheduler.add_job(
        lambda: asyncio.run(check_fail_rate()),
        "interval", hours=1, id="sync_fail_rate_check",
    )
    # Phase 9-3: 주간 wiki 보고서 (매주 월요일 09:30 KST)
    from agents.wiki_reporter import send_weekly_wiki_report
    scheduler.add_job(
        lambda: asyncio.run(send_weekly_wiki_report()),
        "cron", day_of_week="mon", hour=9, minute=30, id="weekly_wiki_report",
    )

    scheduler.start()
    from services.scheduler_instance import set_scheduler
    set_scheduler(scheduler)
    logger.info(
        "스케줄러 시작 (일일 요약 08:00, Drive 백업 일요일 02:00, "
        "주간 보고서 월요일 09:00, wiki 보고서 월요일 09:30, sync 실패율 매시간)"
    )


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "MyVault API"}


@app.get("/health/claude")
async def claude_health_check():
    """Claude API 연결 상태 진단 — 배포 후 직접 호출해서 에러 원인 파악"""
    import anthropic
    result: dict = {"api_key_set": bool(settings.ANTHROPIC_API_KEY)}
    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=20,
            messages=[{"role": "user", "content": "ping"}],
        )
        result["haiku_status"] = "ok"
        result["haiku_response"] = resp.content[0].text if resp.content else ""
    except Exception as e:
        result["haiku_status"] = "error"
        result["haiku_error"] = f"{type(e).__name__}: {e}"

    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=20,
            messages=[{"role": "user", "content": "ping"}],
        )
        result["sonnet_status"] = "ok"
        result["sonnet_response"] = resp.content[0].text if resp.content else ""
    except Exception as e:
        result["sonnet_status"] = "error"
        result["sonnet_error"] = f"{type(e).__name__}: {e}"

    return result
