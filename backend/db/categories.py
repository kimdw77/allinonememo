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
