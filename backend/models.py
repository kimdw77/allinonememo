"""
models.py — Pydantic 데이터 모델 정의
"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class NoteCreate(BaseModel):
    source: str  # 'kakao' | 'telegram' | 'youtube' | 'rss' | 'manual'
    raw_content: str
    url: Optional[str] = None
    metadata: Optional[dict] = None


class NoteResponse(BaseModel):
    id: str
    source: str
    raw_content: str
    summary: Optional[str] = None
    highlights: Optional[list[str]] = None
    keywords: Optional[list[str]] = None
    category: Optional[str] = None
    content_type: Optional[str] = None
    url: Optional[str] = None
    metadata: Optional[dict] = None
    created_at: datetime


class NoteListParams(BaseModel):
    query: Optional[str] = None       # 키워드 검색
    category: Optional[str] = None   # 카테고리 필터
    limit: int = 20
    offset: int = 0


class ClassifyResult(BaseModel):
    summary: str
    keywords: list[str]
    category: str
    content_type: str
