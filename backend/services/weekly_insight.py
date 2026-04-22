"""
weekly_insight.py — 주간 AI 인사이트 생성 + 텔레그램 전송
매주 월요일 09:00 KST에 지난 7일 노트를 분석해 인사이트를 보낸다.
"""
import logging
from datetime import datetime, timedelta, timezone

import anthropic

from config import settings

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))

_INSIGHT_PROMPT = """지난 한 주 동안 저장된 노트들을 분석하여 한국어로 인사이트를 작성하라.

## 저장된 노트 목록 (최근 7일, {count}개):
{notes_text}

## 작성 규칙:
1. 반드시 한국어로 작성
2. 마크다운 없이 텔레그램 친화적 텍스트
3. 400자 이내로 간결하게
4. 아래 구조를 따를 것:

🗓 주간 인사이트 ({date_range})

📊 이번 주 요약
• 저장 노트: {count}개
• 주요 카테고리: (상위 3개)
• 핵심 키워드: (자주 등장한 키워드 5개)

💡 이번 주 핵심 트렌드
(노트 내용에서 발견한 주요 흐름이나 패턴을 2-3문장으로)

📌 주목할 인사이트
(가장 흥미롭거나 중요한 내용 1가지를 1-2문장으로)

다음 주도 꾸준히 기록해보세요! 💪"""


def _build_notes_text(notes: list[dict]) -> str:
    lines: list[str] = []
    for n in notes:
        summary = (n.get("summary") or "")[:100]
        cat = n.get("category", "기타")
        kw = ", ".join((n.get("keywords") or [])[:5])
        lines.append(f"[{cat}] {summary} (키워드: {kw})")
    return "\n".join(lines)


def generate_weekly_insight() -> str:
    """지난 7일 노트를 분석해 인사이트 문자열 반환. 실패 시 빈 문자열."""
    try:
        from db.notes import get_notes
        from datetime import datetime

        notes = get_notes(limit=100, offset=0)

        now = datetime.now(KST)
        week_ago = now - timedelta(days=7)

        recent = []
        for n in notes:
            try:
                created = datetime.fromisoformat(
                    n["created_at"].replace("Z", "+00:00")
                ).astimezone(KST)
                if created >= week_ago:
                    recent.append(n)
            except Exception:
                continue

        if not recent:
            return "📭 지난 주에는 저장된 노트가 없습니다. 이번 주도 활발히 기록해보세요!"

        notes_text = _build_notes_text(recent)
        date_range = f"{week_ago.strftime('%m/%d')}~{now.strftime('%m/%d')}"

        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": _INSIGHT_PROMPT.format(
                    count=len(recent),
                    notes_text=notes_text[:3000],
                    date_range=date_range,
                ),
            }],
        )
        return response.content[0].text.strip() if response.content else ""

    except Exception as e:
        logger.error("주간 인사이트 생성 실패: %s", e)
        return ""


async def send_weekly_insight() -> None:
    """주간 인사이트를 생성해 텔레그램으로 전송"""
    try:
        import httpx

        insight = generate_weekly_insight()
        if not insight:
            logger.warning("주간 인사이트 내용 없음, 전송 건너뜀")
            return

        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, json={
                "chat_id": settings.TELEGRAM_ALLOWED_USER_ID,
                "text": insight,
            })
        logger.info("주간 인사이트 전송 완료")

    except Exception as e:
        logger.error("주간 인사이트 전송 실패: %s", e)
