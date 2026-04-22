"""
routers/categories.py — 카테고리 CRUD API
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field

from dependencies.auth import require_api_key
from db.categories import get_categories, insert_category, delete_category, rename_category

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
