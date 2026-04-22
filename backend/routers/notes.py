"""
routers/notes.py — 노트 CRUD API
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from dependencies.auth import require_api_key
from models import NoteCreate, NoteResponse
from services.classifier import classify_content
from db.notes import insert_note, get_notes, get_note_by_id, delete_note, vector_search_notes

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_api_key)])


@router.get("", response_model=list[NoteResponse])
async def list_notes(
    q: Optional[str] = Query(None, description="키워드 검색", max_length=200),
    category: Optional[str] = Query(None, description="카테고리 필터", max_length=50),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """노트 목록 조회 (키워드 검색·카테고리 필터 지원)"""
    return get_notes(query=q, category=category, limit=limit, offset=offset)


@router.get("/{note_id}", response_model=NoteResponse)
async def get_note(note_id: str):
    """노트 단건 조회"""
    note = get_note_by_id(note_id)
    if not note:
        raise HTTPException(status_code=404, detail="노트를 찾을 수 없습니다")
    return note


@router.post("", response_model=NoteResponse, status_code=201)
async def create_note(body: NoteCreate):
    """수동 노트 추가 (Claude 분류 포함)"""
    classify_result = classify_content(body.raw_content)

    note = insert_note(
        source=body.source or "manual",
        raw_content=body.raw_content,
        summary=classify_result.get("summary", ""),
        highlights=classify_result.get("highlights", []),
        keywords=classify_result.get("keywords", []),
        category=classify_result.get("category", "기타"),
        content_type=classify_result.get("content_type", "other"),
        url=body.url,
        metadata=body.metadata,
    )

    if not note:
        raise HTTPException(status_code=500, detail="노트 저장에 실패했습니다")
    return note


@router.get("/search/vector", response_model=list[NoteResponse])
async def semantic_search(
    q: str = Query(..., description="의미 기반 검색 쿼리", min_length=1, max_length=500),
    limit: int = Query(10, ge=1, le=50),
):
    """
    pgvector 의미 기반 검색.
    VOYAGE_API_KEY 미설정 시 일반 키워드 검색으로 폴백.
    """
    from services.embedder import embed_query
    from config import settings

    if not settings.VOYAGE_API_KEY:
        # 벡터 검색 불가 시 일반 검색으로 폴백
        return get_notes(query=q, limit=limit)

    query_vector = embed_query(q)
    if query_vector is None:
        return get_notes(query=q, limit=limit)

    results = vector_search_notes(query_vector=query_vector, limit=limit)
    return results


@router.delete("/{note_id}", status_code=204)
async def remove_note(note_id: str):
    """노트 삭제"""
    success = delete_note(note_id)
    if not success:
        raise HTTPException(status_code=404, detail="삭제할 노트를 찾을 수 없습니다")
