"""
dependencies/auth.py — 백엔드 API 인증 의존성
프론트엔드에서 X-API-Key 헤더로 API_SECRET_KEY를 전달해야 함
"""
import hmac
from fastapi import Header, HTTPException, status

from config import settings


async def require_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> None:
    """API 시크릿 키 검증 — 상수 시간 비교(타이밍 공격 방지)"""
    if not hmac.compare_digest(x_api_key, settings.API_SECRET_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 API 키",
        )
