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
from routers import webhook, notes, rss, categories

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
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

# 라우터 등록
app.include_router(webhook.router, prefix="/webhook", tags=["webhook"])
app.include_router(notes.router, prefix="/api/notes", tags=["notes"])
app.include_router(rss.router, prefix="/api/rss", tags=["rss"])
app.include_router(categories.router, prefix="/api/categories", tags=["categories"])


@app.on_event("startup")
def start_scheduler() -> None:
    """서버 시작 시 RSS 수집 스케줄러 실행 (30분마다)"""
    from services.rss_fetcher import fetch_all_feeds

    scheduler = BackgroundScheduler()
    scheduler.add_job(fetch_all_feeds, "interval", minutes=30, id="rss_fetch")
    scheduler.start()
    logger.info("RSS 스케줄러 시작 (30분 간격)")


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "MyVault API"}
