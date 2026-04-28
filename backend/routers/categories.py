"""
routers/categories.py — 카테고리 CRUD API
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field

from dependencies.auth import require_api_key
from db.categories import get_categories, insert_category, delete_category, rename_category, merge_category

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_api_key)])


class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=30)
    icon: str = Field("📁", max_length=10)
    color: str = Field("#6366f1", pattern=r"^#[0-9a-fA-F]{6}$")


@router.get("")
async def list_categories():
    """카테고리 목록 조회"""
    return get_categories()


@router.post("", status_code=201)
async def create_category(body: CategoryCreate):
    """카테고리 추가"""
    result = insert_category(name=body.name, icon=body.icon, color=body.color)
    if not result:
        raise HTTPException(status_code=409, detail="이미 존재하거나 추가에 실패한 카테고리입니다")
    return result


@router.delete("/{name}", status_code=204)
async def remove_category(name: str = Path(..., max_length=30)):
    """카테고리 삭제 ('기타'는 삭제 불가)"""
    if name == "기타":
        raise HTTPException(status_code=400, detail="'기타' 카테고리는 삭제할 수 없습니다")
    success = delete_category(name)
    if not success:
        raise HTTPException(status_code=404, detail="카테고리를 찾을 수 없습니다")


class CategoryUpdate(BaseModel):
    new_name: str = Field(..., min_length=1, max_length=30)
    icon: str | None = Field(None, max_length=10)


@router.patch("/{name}")
async def update_category(body: CategoryUpdate, name: str = Path(..., max_length=30)):
    """카테고리 이름·아이콘 변경 (연결된 노트 category도 자동 업데이트)"""
    if name == "기타":
        raise HTTPException(status_code=400, detail="'기타' 카테고리는 변경할 수 없습니다")
    result = rename_category(old_name=name, new_name=body.new_name, new_icon=body.icon)
    if not result:
        raise HTTPException(status_code=404, detail="카테고리를 찾을 수 없거나 변경 실패")
    return result


class CategoryMerge(BaseModel):
    source: str = Field(..., min_length=1, max_length=30, description="통합할 카테고리 (삭제됨)")
    target: str = Field(..., min_length=1, max_length=30, description="남길 카테고리")


@router.post("/merge", status_code=200)
async def merge_categories(body: CategoryMerge):
    """source 카테고리의 노트를 target으로 이동 후 source 삭제. '/'가 포함된 이름도 처리 가능."""
    if body.source == body.target:
        raise HTTPException(status_code=400, detail="source와 target이 같습니다")
    success = merge_category(source_name=body.source, target_name=body.target)
    if not success:
        raise HTTPException(status_code=400, detail="카테고리 통합 실패")
    return {"merged": True, "source": body.source, "target": body.target}


class CategoryDelete(BaseModel):
    name: str = Field(..., min_length=1, max_length=30)


@router.post("/delete", status_code=204)
async def remove_category_by_body(body: CategoryDelete):
    """카테고리 삭제 (이름을 body로 전달 — '/'가 포함된 이름도 처리 가능)"""
    if body.name == "기타":
        raise HTTPException(status_code=400, detail="'기타' 카테고리는 삭제할 수 없습니다")
    success = delete_category(body.name)
    if not success:
        raise HTTPException(status_code=404, detail="카테고리를 찾을 수 없습니다")


class CategoryUpdateByBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=30, description="현재 이름")
    new_name: str = Field(..., min_length=1, max_length=30)
    icon: str | None = Field(None, max_length=10)


@router.post("/update", status_code=200)
async def update_category_by_body(body: CategoryUpdateByBody):
    """카테고리 이름·아이콘 변경 (body 전달 — '/'가 포함된 이름도 처리 가능)"""
    if body.name == "기타":
        raise HTTPException(status_code=400, detail="'기타' 카테고리는 변경할 수 없습니다")
    result = rename_category(old_name=body.name, new_name=body.new_name, new_icon=body.icon)
    if not result:
        raise HTTPException(status_code=404, detail="카테고리를 찾을 수 없거나 변경 실패")
    return result
