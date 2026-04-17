"""
main.py — FastAPI 애플리케이션 진입점
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler

from routers import webhook, notes, rss

logger = logging.getLogger(__name__)

app = FastAPI(
    title="MyVault API",
    description="개인 AI 지식저장소 백엔드",
    version="0.1.0",
)

# CORS 설정 (Vercel 프론트엔드 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://allinonememo.vercel.app",
        "https://*.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(webhook.router, prefix="/webhook", tags=["webhook"])
app.include_router(notes.router, prefix="/api/notes", tags=["notes"])
app.include_router(rss.router, prefix="/api/rss", tags=["rss"])


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
