"""
routers/notes.py — 노트 CRUD API
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File

from dependencies.auth import require_api_key
from models import NoteCreate, NoteUpdate, NoteResponse
from services.classifier import classify_content, analyze_image
from db.notes import (
    insert_note, update_note, get_notes, get_note_by_id, delete_note,
    vector_search_notes, get_related_notes, get_graph_data,
    get_duplicates, merge_notes, get_top_keywords, bulk_delete_notes, export_notes,
    get_keyword_stats, get_calendar_notes,
    get_unanalyzed_notes, count_unanalyzed_notes,
)

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_api_key)])


@router.get("", response_model=list[NoteResponse])
async def list_notes(
    q: Optional[str] = Query(None, description="키워드 검색", max_length=200),
    category: Optional[str] = Query(None, description="카테고리 필터", max_length=50),
    keyword: Optional[str] = Query(None, description="정확한 태그 필터", max_length=100),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """노트 목록 조회 (키워드 검색·카테고리·태그 필터 지원)"""
    return get_notes(query=q, category=category, keyword=keyword, limit=limit, offset=offset)


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
# 일괄 재분류
# ─────────────────────────────────────────

@router.post("/bulk-reclassify")
async def bulk_reclassify(
    limit: int = Query(30, ge=1, le=100, description="한 번에 처리할 최대 노트 수"),
):
    """
    미분석 이미지 노트(raw_content='[이미지]')를 Claude Vision으로 일괄 재분석.
    file_url에서 이미지를 다운로드하여 OCR·요약·분류를 수행한다.
    """
    import httpx, re as re_mod

    notes = get_unanalyzed_notes(limit=limit)
    ok, failed = 0, 0

    for note in notes:
        file_url = note.get("file_url")
        if not file_url:
            failed += 1
            continue
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.get(file_url)
                r.raise_for_status()
                image_bytes = r.content
            ct_header = r.headers.get("content-type", "image/jpeg").split(";")[0].strip()
            ext = re_mod.search(r"\.(jpe?g|png|gif|webp)$", file_url, re_mod.I)
            mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                        "gif": "image/gif", "webp": "image/webp"}
            media_type = (ct_header if ct_header.startswith("image/")
                          else mime_map.get((ext.group(1).lower() if ext else ""), "image/jpeg"))
            result = analyze_image(image_bytes, media_type)

            raw_content = result.get("ocr_text") or result.get("summary") or "[이미지]"
            content_type = "newspaper" if result.get("is_newspaper") else result.get("content_type", "image")
            updated = update_note(note["id"], {
                "raw_content": raw_content,
                "summary": result.get("summary", ""),
                "highlights": result.get("highlights", []),
                "keywords": result.get("keywords", []),
                "category": result.get("category", "기타"),
                "content_type": content_type,
            })
            if updated:
                ok += 1
            else:
                failed += 1
        except Exception as e:
            logger.error("배치 이미지 재분류 실패 (id=%s): %s", note["id"], e)
            failed += 1

    remaining = count_unanalyzed_notes()
    return {"reclassified": ok, "failed": failed, "total": len(notes), "remaining": remaining}


# ─────────────────────────────────────────
# 파일 업로드 (아이폰 노트 등)
# ─────────────────────────────────────────

ALLOWED_EXTENSIONS = {".txt", ".md", ".text", ".pdf", ".docx", ".doc"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
IMAGE_MEDIA_TYPES = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".png": "image/png", ".gif": "image/gif", ".webp": "image/webp",
}
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

        is_image = ext in IMAGE_EXTENSIONS
        if ext not in ALLOWED_EXTENSIONS and not is_image:
            errors.append(f"{filename}: 지원하지 않는 형식 ({ext})")
            continue

        content = await upload.read()
        if len(content) > MAX_FILE_SIZE:
            errors.append(f"{filename}: 파일 크기 초과 (최대 10MB)")
            continue

        if is_image:
            # Claude Vision으로 OCR + 분류
            media_type = IMAGE_MEDIA_TYPES.get(ext, "image/jpeg")
            classify_result = analyze_image(content, media_type)
            ocr_text = classify_result.pop("ocr_text", "")
            raw_content = ocr_text or f"[이미지 파일: {filename}]"
        else:
            text = extract_text(filename, content)
            if not text.strip():
                errors.append(f"{filename}: 텍스트를 추출할 수 없습니다")
                continue
            classify_result = classify_content(text)
            raw_content = text

        note = insert_note(
            source="upload",
            raw_content=raw_content,
            summary=classify_result.get("summary", ""),
            highlights=classify_result.get("highlights", []),
            keywords=classify_result.get("keywords", []),
            category=classify_result.get("category", "기타"),
            content_type=classify_result.get("content_type", "other"),
            metadata={"original_filename": filename, "file_ext": ext, "is_image": is_image},
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


# ─────────────────────────────────────────
# 키워드 자동완성 + 통계
# ─────────────────────────────────────────

@router.get("/keywords/stats")
async def keyword_stats(limit: int = Query(100, ge=1, le=300)):
    """키워드별 빈도수·주요 카테고리 반환 (워드클라우드용)"""
    return get_keyword_stats(limit=limit)


@router.get("/keywords")
async def keywords_autocomplete(limit: int = Query(50, ge=1, le=200)):
    """전체 노트 키워드 빈도 순 목록 (검색 자동완성용)"""
    return get_top_keywords(limit=limit)


# ─────────────────────────────────────────
# 캘린더
# ─────────────────────────────────────────

@router.get("/calendar")
async def calendar(
    year: int = Query(..., ge=2020, le=2035),
    month: int = Query(..., ge=1, le=12),
):
    """특정 월의 날짜별 노트 목록 반환 (KST 기준)"""
    return get_calendar_notes(year=year, month=month)


# ─────────────────────────────────────────
# 일괄 삭제
# ─────────────────────────────────────────

@router.post("/bulk-delete")
async def bulk_delete(note_ids: list[str]):
    """여러 노트 일괄 삭제. 삭제된 수 반환."""
    if not note_ids:
        raise HTTPException(status_code=400, detail="삭제할 노트 ID를 전달하세요")
    if len(note_ids) > 200:
        raise HTTPException(status_code=400, detail="한 번에 최대 200개까지 삭제 가능합니다")
    deleted = bulk_delete_notes(note_ids)
    return {"deleted": deleted}


# ─────────────────────────────────────────
# 내보내기
# ─────────────────────────────────────────

@router.get("/export")
async def export(
    fmt: str = Query("json", description="출력 형식: json | markdown"),
    category: Optional[str] = Query(None),
    ids: Optional[str] = Query(None, description="콤마 구분 note ID 목록"),
    limit: int = Query(1000, ge=1, le=5000),
):
    """노트 내보내기 (JSON 또는 Markdown)"""
    from fastapi.responses import Response

    note_ids = [i.strip() for i in ids.split(",")] if ids else None
    notes = export_notes(category=category, note_ids=note_ids, limit=limit)

    if fmt == "markdown":
        lines: list[str] = ["# MyVault 노트 내보내기\n"]
        for n in notes:
            lines.append(f"## {n.get('summary', '(요약 없음)')}")
            lines.append(f"- **카테고리**: {n.get('category', '')}")
            lines.append(f"- **날짜**: {n.get('created_at', '')[:10]}")
            kw = n.get("keywords") or []
            if kw:
                lines.append(f"- **키워드**: {', '.join(kw)}")
            if n.get("url"):
                lines.append(f"- **URL**: {n['url']}")
            lines.append(f"\n{n.get('raw_content', '')}\n")
            lines.append("---\n")
        md = "\n".join(lines)
        return Response(
            content=md.encode("utf-8"),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=myvault_notes.md"},
        )

    # JSON 기본
    import json as json_mod
    from fastapi.responses import Response as Resp
    return Resp(
        content=json_mod.dumps(notes, ensure_ascii=False, default=str).encode("utf-8"),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=myvault_notes.json"},
    )


@router.get("/unanalyzed/count")
async def unanalyzed_count():
    """미분석 이미지 노트(raw_content='[이미지]') 수 반환"""
    return {"count": count_unanalyzed_notes()}


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
    """기존 노트를 Claude로 재분류. 이미지 노트는 file_url에서 다시 Vision 분석."""
    note = get_note_by_id(note_id)
    if not note:
        raise HTTPException(status_code=404, detail="노트를 찾을 수 없습니다")

    IMAGE_CONTENT_TYPES = {"image", "newspaper", "article", "photo", "other"}
    file_url: str | None = note.get("file_url")
    is_image_note = (
        file_url
        and note.get("content_type") in IMAGE_CONTENT_TYPES
        and (not note.get("summary") or note.get("raw_content") in ("[이미지]", "", None))
    )

    if is_image_note:
        # file_url에서 이미지를 다운로드하여 Vision 재분석
        import httpx, re
        from services.classifier import analyze_image
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.get(file_url)
                r.raise_for_status()
                image_bytes = r.content
            # Content-Type 또는 URL 확장자로 미디어 타입 추정
            ct_header = r.headers.get("content-type", "image/jpeg").split(";")[0].strip()
            ext = re.search(r"\.(jpe?g|png|gif|webp)$", file_url, re.I)
            mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "gif": "image/gif", "webp": "image/webp"}
            media_type = ct_header if ct_header.startswith("image/") else mime_map.get((ext.group(1).lower() if ext else ""), "image/jpeg")
            result = analyze_image(image_bytes, media_type)
        except Exception as e:
            logger.error("이미지 재분류 다운로드 실패 (file_url=%s): %s", file_url, e)
            raise HTTPException(status_code=502, detail="이미지 다운로드 실패")

        raw_content = result.get("ocr_text") or result.get("summary") or note.get("raw_content") or "[이미지]"
        content_type = "newspaper" if result.get("is_newspaper") else result.get("content_type", "image")
        updated = update_note(note_id, {
            "raw_content": raw_content,
            "summary": result.get("summary", ""),
            "highlights": result.get("highlights", []),
            "keywords": result.get("keywords", []),
            "category": result.get("category", "기타"),
            "content_type": content_type,
        })
    else:
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
