"""
notion_sync.py — Notion 데이터베이스 동기화 서비스
MyVault 노트를 Notion 데이터베이스 페이지로 내보내기
NOTION_TOKEN, NOTION_DATABASE_ID 환경변수 필요
"""
import logging
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)

_NOTION_API = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"

# 캐시: 데이터베이스 title 속성명 (매번 API 호출 방지)
_title_prop_name: Optional[str] = None


def _format_database_id(raw_id: str) -> str:
    """32자리 hex ID를 Notion API 하이픈 형식으로 변환"""
    clean = raw_id.replace("-", "")
    if len(clean) == 32:
        return f"{clean[0:8]}-{clean[8:12]}-{clean[12:16]}-{clean[16:20]}-{clean[20:32]}"
    return raw_id


def _get_database_id() -> str:
    return _format_database_id(settings.NOTION_DATABASE_ID)


def _get_headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.NOTION_TOKEN}",
        "Notion-Version": _NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _get_title_property_name() -> str:
    """
    데이터베이스 스키마를 조회해서 title 타입 속성명 반환.
    실패 시 기본값 '이름' 반환.
    """
    global _title_prop_name
    if _title_prop_name:
        return _title_prop_name

    try:
        import httpx
        resp = httpx.get(
            f"{_NOTION_API}/databases/{_get_database_id()}",
            headers=_get_headers(),
            timeout=10,
        )
        resp.raise_for_status()
        props = resp.json().get("properties", {})
        for name, prop in props.items():
            if prop.get("type") == "title":
                _title_prop_name = name
                logger.info("Notion title 속성명 감지: '%s'", name)
                return name
    except Exception as e:
        logger.warning("Notion 스키마 조회 실패, 기본값 사용: %s", e)

    _title_prop_name = "이름"
    return _title_prop_name


def _build_page_body(note: dict) -> dict:
    """
    노트 → Notion 페이지 payload.
    title 속성만 properties로 설정하고,
    나머지 메타데이터는 본문 블록으로 삽입 (속성 불일치 오류 방지).
    """
    title_text = (note.get("summary") or note.get("raw_content", ""))[:100].strip()
    title_prop = _get_title_property_name()

    properties = {
        title_prop: {
            "title": [{"text": {"content": title_text}}]
        }
    }

    # 메타데이터를 본문 블록으로 구성
    children = []

    def _para(text: str) -> dict:
        return {
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": text[:2000]}}]},
        }

    # 메타 정보 헤더
    meta_lines = []
    if note.get("category"):
        meta_lines.append(f"카테고리: {note['category']}")
    if note.get("content_type"):
        meta_lines.append(f"유형: {note['content_type']}")
    if note.get("source"):
        meta_lines.append(f"출처: {note['source']}")
    if note.get("keywords"):
        meta_lines.append(f"키워드: {', '.join(note['keywords'])}")
    if note.get("url"):
        meta_lines.append(f"URL: {note['url']}")
    if note.get("created_at"):
        meta_lines.append(f"저장일시: {note['created_at'][:19]}")
    if note.get("id"):
        meta_lines.append(f"MyVault ID: {note['id']}")

    if meta_lines:
        children.append(_para("\n".join(meta_lines)))
        children.append({
            "object": "block",
            "type": "divider",
            "divider": {},
        })

    # 본문
    raw = (note.get("raw_content") or "")[:4000]
    if raw:
        for i in range(0, len(raw), 2000):
            children.append(_para(raw[i:i + 2000]))

    return {
        "parent": {"database_id": _get_database_id()},
        "properties": properties,
        "children": children,
    }


def sync_note_to_notion(note: dict) -> bool:
    """
    단일 노트를 Notion에 동기화.
    성공 시 True 반환.
    """
    if not settings.NOTION_TOKEN or not settings.NOTION_DATABASE_ID:
        logger.debug("Notion 설정 없음, 동기화 건너뜀")
        return False

    try:
        import httpx
        body = _build_page_body(note)

        resp = httpx.post(
            f"{_NOTION_API}/pages",
            headers=_get_headers(),
            json=body,
            timeout=10,
        )

        if not resp.is_success:
            logger.error("Notion 동기화 실패 (id=%s): %s", note.get("id"), resp.text[:500])
            return False

        logger.info("Notion 동기화 성공: %s", note.get("id"))
        return True

    except Exception as e:
        logger.error("Notion 동기화 실패 (id=%s): %s", note.get("id"), e)
        return False


def bulk_sync_to_notion(limit: int = 100) -> dict:
    """
    최근 노트를 Notion에 일괄 동기화.
    결과: {"synced": int, "failed": int}
    """
    if not settings.NOTION_TOKEN or not settings.NOTION_DATABASE_ID:
        return {"synced": 0, "failed": 0, "error": "Notion 환경변수 미설정"}

    try:
        from db.notes import get_notes
        notes = get_notes(limit=limit)
    except Exception as e:
        logger.error("노트 조회 실패: %s", e)
        return {"synced": 0, "failed": 0}

    synced = failed = 0
    for note in notes:
        if sync_note_to_notion(note):
            synced += 1
        else:
            failed += 1

    logger.info("Notion 일괄 동기화 완료: 성공 %d, 실패 %d", synced, failed)
    return {"synced": synced, "failed": failed}
