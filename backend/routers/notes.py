"""
routers/notes.py — 노트 CRUD API
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File

from dependencies.auth import require_api_key
from models import NoteCreate, NoteUpdate, NoteResponse
from services.classifier import classify_content
from db.notes import insert_note, update_note, get_notes, get_note_by_id, delete_note, vector_search_notes, get_related_notes, get_graph_data, get_duplicates, merge_notes

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


# ─────────────────────────────────────────
# 파일 업로드 (아이폰 노트 등)
# ─────────────────────────────────────────

ALLOWED_EXTENSIONS = {".txt", ".md", ".text", ".pdf", ".docx", ".doc"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


@router.post("/upload", response_model=list[NoteResponse], status_code=201)
async def upload_files(files: list[UploadFile] = File(...)):
    """
    파일 업로드 → 텍스트 추출 → Claude 분류 → 저장.
    txt/md/pdf/docx 지원. 최대 10개, 파일당 10MB.
    """
    import os
    from pathlib import Path
    from services.file_parser import extract_text

    if len(files) > 10:
        raise HTTPException(status_code=400, detail="한 번에 최대 10개 파일만 업로드 가능합니다")

    created: list[dict] = []
    errors: list[str] = []

    for upload in files:
        filename = upload.filename or "unknown"
        ext = Path(filename).suffix.lower()

        if ext not in ALLOWED_EXTENSIONS:
            errors.append(f"{filename}: 지원하지 않는 형식 ({ext})")
            continue

        content = await upload.read()
        if len(content) > MAX_FILE_SIZE:
            errors.append(f"{filename}: 파일 크기 초과 (최대 10MB)")
            continue

        text = extract_text(filename, content)
        if not text.strip():
            errors.append(f"{filename}: 텍스트를 추출할 수 없습니다")
            continue

        classify_result = classify_content(text)
        note = insert_note(
            source="upload",
            raw_content=text,
            summary=classify_result.get("summary", ""),
            highlights=classify_result.get("highlights", []),
            keywords=classify_result.get("keywords", []),
            category=classify_result.get("category", "기타"),
            content_type=classify_result.get("content_type", "other"),
            metadata={"original_filename": filename, "file_ext": ext},
        )
        if note:
            created.append(note)
        else:
            errors.append(f"{filename}: 저장 실패")

    if not created and errors:
        raise HTTPException(status_code=422, detail="; ".join(errors))

    return created


# ─────────────────────────────────────────
# 중복 노트 감지 및 병합
# ─────────────────────────────────────────

@router.get("/duplicates")
async def find_duplicates(threshold: int = Query(3, ge=2, le=10, description="공통 키워드 최소 개수")):
    """키워드 기반 중복 노트 후보 쌍 반환"""
    pairs = get_duplicates(threshold=threshold)
    return {"pairs": pairs, "count": len(pairs)}


@router.post("/merge")
async def merge_two_notes(keep_id: str, remove_id: str):
    """두 노트를 병합 (keep_id 유지, remove_id 삭제)"""
    result = merge_notes(keep_id=keep_id, remove_id=remove_id)
    if not result:
        raise HTTPException(status_code=404, detail="노트를 찾을 수 없거나 병합 실패")
    return result


# 고정 경로는 반드시 /{note_id} 앞에 위치해야 FastAPI가 올바르게 라우팅함
@router.get("/graph")
async def graph_data(limit: int = Query(200, ge=10, le=500)):
    """그래프 시각화용 노드·엣지 데이터 반환"""
    return get_graph_data(limit=limit)


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
        return get_notes(query=q, limit=limit)

    query_vector = embed_query(q)
    if query_vector is None:
        return get_notes(query=q, limit=limit)

    return vector_search_notes(query_vector=query_vector, limit=limit)


@router.get("/{note_id}", response_model=NoteResponse)
async def get_note(note_id: str):
    """노트 단건 조회"""
    note = get_note_by_id(note_id)
    if not note:
        raise HTTPException(status_code=404, detail="노트를 찾을 수 없습니다")
    return note


@router.patch("/{note_id}", response_model=NoteResponse)
async def edit_note(note_id: str, body: NoteUpdate):
    """노트 부분 수정 (summary, keywords, category 등)"""
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="수정할 항목이 없습니다")
    note = update_note(note_id, fields)
    if not note:
        raise HTTPException(status_code=404, detail="노트를 찾을 수 없습니다")
    return note


@router.post("/{note_id}/reclassify", response_model=NoteResponse)
async def reclassify_note(note_id: str):
    """기존 노트를 Claude로 재분류 (요약·키워드·카테고리 갱신)"""
    note = get_note_by_id(note_id)
    if not note:
        raise HTTPException(status_code=404, detail="노트를 찾을 수 없습니다")

    result = classify_content(note["raw_content"])
    updated = update_note(note_id, {
        "summary": result.get("summary", ""),
        "highlights": result.get("highlights", []),
        "keywords": result.get("keywords", []),
        "category": result.get("category", "기타"),
        "content_type": result.get("content_type", "other"),
    })
    if not updated:
        raise HTTPException(status_code=500, detail="재분류 저장 실패")
    return updated


@router.get("/{note_id}/related", response_model=list[NoteResponse])
async def related_notes(note_id: str, limit: int = Query(5, ge=1, le=20)):
    """키워드 기반 연관 노트 조회"""
    return get_related_notes(note_id=note_id, limit=limit)


@router.delete("/{note_id}", status_code=204)
async def remove_note(note_id: str):
    """노트 삭제"""
    success = delete_note(note_id)
    if not success:
        raise HTTPException(status_code=404, detail="삭제할 노트를 찾을 수 없습니다")
