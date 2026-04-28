"""
db/categories.py — categories 테이블 CRUD 함수
"""
import logging
from typing import Optional

from db.client import get_db

logger = logging.getLogger(__name__)


def get_categories() -> list[dict]:
    """카테고리 전체 목록 조회 (name 오름차순)"""
    try:
        db = get_db()
        result = db.table("categories").select("*").order("name").execute()
        return result.data or []
    except Exception as e:
        logger.error("카테고리 조회 실패: %s", e)
        return []


def get_category_names() -> list[str]:
    """분류 프롬프트용 카테고리 이름 목록만 반환"""
    return [cat["name"] for cat in get_categories()]


def insert_category(name: str, icon: str = "📁", color: str = "#6366f1") -> Optional[dict]:
    """카테고리 추가. 성공 시 생성된 레코드 반환, 실패(중복 포함) 시 None"""
    try:
        db = get_db()
        result = db.table("categories").insert({
            "name": name,
            "icon": icon,
            "color": color,
        }).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error("카테고리 추가 실패 (name=%s): %s", name, e)
        return None


def delete_category(name: str) -> bool:
    """카테고리 삭제. '기타'는 삭제 불가. 성공 시 True"""
    if name == "기타":
        return False
    try:
        db = get_db()
        db.table("categories").delete().eq("name", name).execute()
        return True
    except Exception as e:
        logger.error("카테고리 삭제 실패 (name=%s): %s", name, e)
        return False


def merge_category(source_name: str, target_name: str) -> bool:
    """
    source 카테고리의 모든 노트를 target으로 이동 후 source 카테고리 삭제.
    '기타' → 다른 곳으로 이동도 가능. source == target이면 False.
    """
    if source_name == target_name:
        return False
    try:
        db = get_db()
        db.table("notes").update({"category": target_name}).eq("category", source_name).execute()
        db.table("categories").delete().eq("name", source_name).execute()
        return True
    except Exception as e:
        logger.error("카테고리 통합 실패 (%s → %s): %s", source_name, target_name, e)
        return False


def rename_category(old_name: str, new_name: str, new_icon: Optional[str] = None) -> Optional[dict]:
    """
    카테고리 이름·아이콘 변경.
    categories 테이블과 notes 테이블(category 컬럼)을 동시에 업데이트.
    '기타' 이름 변경 불가.
    """
    if old_name == "기타":
        return None
    try:
        db = get_db()
        update_fields: dict = {"name": new_name}
        if new_icon is not None:
            update_fields["icon"] = new_icon

        result = db.table("categories").update(update_fields).eq("name", old_name).execute()
        if not result.data:
            return None

        # notes 테이블의 category도 동기화
        db.table("notes").update({"category": new_name}).eq("category", old_name).execute()
        return result.data[0]
    except Exception as e:
        logger.error("카테고리 이름 변경 실패 (%s → %s): %s", old_name, new_name, e)
        return None
