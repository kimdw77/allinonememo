"""
digest.py — RSS 일일 요약 서비스
어제 수집된 RSS 노트를 Claude로 카테고리별 요약 후 텔레그램으로 전송
"""
import logging
from datetime import datetime, timedelta, timezone

import anthropic

from config import settings
from db.client import get_db

logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

# KST = UTC+9
KST = timezone(timedelta(hours=9))

DIGEST_PROMPT = """다음은 오늘 수집된 RSS 뉴스/기사 목록이다. 카테고리별로 핵심 내용을 간결하게 요약하라.

{articles}

응답 형식 (마크다운):
## 📰 오늘의 요약 ({date})

### [카테고리명]
- 핵심 내용 1
- 핵심 내용 2

### [카테고리명]
...

마지막에 한 줄 총평을 추가하라. 없는 카테고리는 생략."""


def _get_yesterday_rss_notes() -> list[dict]:
    """어제 하루 동안 수집된 RSS 노트 조회"""
    try:
        db = get_db()
        now_kst = datetime.now(KST)
        # 어제 00:00 ~ 오늘 00:00 (UTC 기준)
        today_start = now_kst.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today_start - timedelta(days=1)

        result = db.table("notes").select(
            "id, summary, category, url, raw_content"
        ).eq(
            "source", "rss"
        ).gte(
            "created_at", yesterday_start.astimezone(timezone.utc).isoformat()
        ).lt(
            "created_at", today_start.astimezone(timezone.utc).isoformat()
        ).order(
            "category"
        ).execute()

        return result.data or []

    except Exception as e:
        logger.error("어제 RSS 노트 조회 실패: %s", e)
        return []


def _build_articles_text(notes: list[dict]) -> str:
    """노트 목록을 프롬프트용 텍스트로 변환"""
    lines = []
    for i, note in enumerate(notes, 1):
        category = note.get("category", "기타")
        summary = note.get("summary") or note.get("raw_content", "")[:200]
        url = note.get("url", "")
        lines.append(f"{i}. [{category}] {summary}")
        if url:
            lines.append(f"   링크: {url}")
    return "\n".join(lines)


def _send_telegram_message(text: str) -> bool:
    """텔레그램으로 메시지 전송"""
    try:
        import httpx
        bot_token = settings.TELEGRAM_BOT_TOKEN
        user_id = settings.TELEGRAM_ALLOWED_USER_ID
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

        # 텔레그램 메시지 4096자 제한
        if len(text) > 4000:
            text = text[:4000] + "\n\n...(생략)"

        resp = httpx.post(url, json={
            "chat_id": user_id,
            "text": text,
            "parse_mode": "Markdown",
        }, timeout=10)
        resp.raise_for_status()
        logger.info("텔레그램 일일 요약 전송 성공")
        return True

    except Exception as e:
        logger.error("텔레그램 전송 실패: %s", e)
        return False


def _save_digest_note(digest_text: str, article_count: int) -> None:
    """일일 요약을 노트로도 저장"""
    try:
        from db.notes import insert_note
        today_str = datetime.now(KST).strftime("%Y-%m-%d")
        insert_note(
            source="digest",
            raw_content=digest_text,
            summary=f"{today_str} RSS 일일 요약 ({article_count}건)",
            keywords=["일일요약", "RSS", today_str],
            category="뉴스",
            content_type="memo",
        )
    except Exception as e:
        logger.error("일일 요약 노트 저장 실패: %s", e)


def send_daily_digest() -> None:
    """
    어제 RSS 수집 내용을 Claude로 요약 후 텔레그램 전송.
    매일 아침 스케줄러에서 호출.
    """
    notes = _get_yesterday_rss_notes()
    today_str = datetime.now(KST).strftime("%Y년 %m월 %d일")

    if not notes:
        logger.info("어제 수집된 RSS 노트 없음, 일일 요약 건너뜀")
        _send_telegram_message(f"📭 {today_str} — 어제 수집된 RSS 기사가 없습니다.")
        return

    logger.info("일일 요약 생성 시작: %d개 노트", len(notes))
    articles_text = _build_articles_text(notes)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": DIGEST_PROMPT.format(
                    articles=articles_text[:4000],
                    date=today_str,
                ),
            }],
        )
        digest_text = response.content[0].text.strip() if response.content else ""

        if not digest_text:
            logger.error("Claude 일일 요약 응답 비어있음")
            return

        _send_telegram_message(digest_text)
        _save_digest_note(digest_text, len(notes))
        logger.info("일일 요약 완료 (%d건)", len(notes))

    except anthropic.APIError as e:
        logger.error("Claude API 오류 (일일 요약): %s", e)
    except Exception as e:
        logger.error("일일 요약 중 오류: %s", e)
