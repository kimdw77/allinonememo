"""
main.py — FastAPI 애플리케이션 진입점
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import webhook, notes

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
        "https://*.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(webhook.router, prefix="/webhook", tags=["webhook"])
app.include_router(notes.router, prefix="/api/notes", tags=["notes"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "MyVault API"}
