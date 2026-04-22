"""
routers/stats.py — 대시보드 통계 API
"""
from fastapi import APIRouter, Depends
from dependencies.auth import require_api_key
from db.notes import get_stats

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.get("")
async def dashboard_stats():
    """카테고리별 분포, 소스별 분포, 일별 추이, 오늘/이번주 노트 수"""
    return get_stats()
