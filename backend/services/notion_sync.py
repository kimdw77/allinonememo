"""
notion_sync.py — Notion 데이터베이스 동기화 서비스
MyVault 노트를 Notion 데이터베이스 페이지로 내보내기
NOTION_TOKEN, NOTION_DATABASE_ID 환경변수 필요
"""
import logging
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)

# Notion API 기본 URL
_NOTION_API = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"


def _format_database_id(raw_id: str) -> str:
    """32자리 hex ID를 Notion API 요구 형식(하이픈 포함)으로 변환"""
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


def _build_page_body(note: dict) -> dict:
    """노트 dict → Notion 페이지 생성 payload"""
    title = (note.get("summary") or note.get("raw_content", ""))[:100].strip()
    keywords = note.get("keywords") or []
    # Notion multi-select는 name 필드 필요
    keyword_options = [{"name": kw[:100]} for kw in keywords[:10]]

    properties: dict = {
        "이름": {
            "title": [{"text": {"content": title}}]
        },
        "카테고리": {
            "select": {"name": note.get("category", "기타")}
        },
        "유형": {
            "select": {"name": note.get("content_type", "other")}
        },
        "출처": {
            "select": {"name": note.get("source", "manual")}
        },
        "키워드": {
            "multi_select": keyword_options
        },
    }

    url = note.get("url")
    if url:
        properties["URL"] = {"url": url}

    created_at = note.get("created_at")
    if created_at:
        # 마이크로초 제거 후 Notion date 형식으로 전달
        date_str = created_at[:19] + "+00:00" if len(created_at) >= 19 else created_at
        properties["저장일시"] = {"date": {"start": date_str}}

    # note_id를 외부 ID로 저장 (중복 방지용)
    note_id = note.get("id", "")
    if note_id:
        properties["MyVault ID"] = {"rich_text": [{"text": {"content": note_id}}]}

    # 본문: raw_content를 Notion paragraph 블록으로
    raw = note.get("raw_content", "")[:2000]
    children = []
    if raw:
        # 2000자 → 2000자씩 블록 분할 (Notion 블록 한도)
        for i in range(0, len(raw), 2000):
            chunk = raw[i:i + 2000]
            children.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": chunk}}]
                },
            })

    return {
        "parent": {"database_id": _get_database_id()},
        "properties": properties,
        "children": children,
    }


def _find_existing_page(note_id: str) -> Optional[str]:
    """
    MyVault ID로 이미 동기화된 Notion 페이지 검색.
    기존 페이지 ID 반환, 없으면 None.
    """
    try:
        import httpx
        resp = httpx.post(
            f"{_NOTION_API}/databases/{_get_database_id()}/query",
            headers=_get_headers(),
            json={
                "filter": {
                    "property": "MyVault ID",
                    "rich_text": {"equals": note_id},
                }
            },
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        return results[0]["id"] if results else None
    except Exception as e:
        try:
            logger.warning("Notion 페이지 조회 실패: %s | 응답: %s", e, resp.text[:300])
        except Exception:
            logger.warning("Notion 페이지 조회 실패: %s", e)
        return None


def sync_note_to_notion(note: dict) -> bool:
    """
    단일 노트를 Notion에 동기화.
    이미 존재하면 업데이트, 없으면 신규 생성.
    성공 시 True 반환.
    """
    if not settings.NOTION_TOKEN or not settings.NOTION_DATABASE_ID:
        logger.debug("Notion 설정 없음, 동기화 건너뜀")
        return False

    try:
        import httpx
        note_id = note.get("id", "")
        existing_page_id = _find_existing_page(note_id) if note_id else None
        body = _build_page_body(note)

        if existing_page_id:
            # 기존 페이지 properties만 업데이트 (본문 변경은 별도 API 필요)
            resp = httpx.patch(
                f"{_NOTION_API}/pages/{existing_page_id}",
                headers=_get_headers(),
                json={"properties": body["properties"]},
                timeout=10,
            )
        else:
            resp = httpx.post(
                f"{_NOTION_API}/pages",
                headers=_get_headers(),
                json=body,
                timeout=10,
            )

        resp.raise_for_status()
        logger.info("Notion 동기화 성공: %s", note_id)
        return True

    except Exception as e:
        try:
            logger.error("Notion 동기화 실패 (id=%s): %s | 응답: %s", note.get("id"), e, resp.text[:500])
        except Exception:
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
