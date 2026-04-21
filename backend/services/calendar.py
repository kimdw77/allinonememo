"""
services/calendar.py — Google Calendar API 연동
OAuth2 refresh_token 방식으로 액세스 토큰을 갱신하여 이벤트 생성
"""
import logging
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)


def _is_configured() -> bool:
    """Google Calendar 환경변수가 모두 설정되어 있는지 확인"""
    return bool(
        settings.GOOGLE_CLIENT_ID
        and settings.GOOGLE_CLIENT_SECRET
        and settings.GOOGLE_REFRESH_TOKEN
    )


def create_event(
    title: str,
    start: str,
    end: str,
    location: str = "",
    description: str = "",
) -> Optional[str]:
    """
    Google Calendar에 이벤트 생성.
    성공 시 이벤트 HTML 링크 반환, 실패 시 None.
    start/end는 ISO8601 형식 (예: 2026-04-22T15:00:00+09:00).
    """
    if not _is_configured():
        logger.warning("Google Calendar 환경변수 미설정 — 이벤트 생성 건너뜀")
        return None

    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = Credentials(
            token=None,
            refresh_token=settings.GOOGLE_REFRESH_TOKEN,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
        )

        service = build("calendar", "v3", credentials=creds, cache_discovery=False)

        event_body = {
            "summary": title,
            "start": {"dateTime": start, "timeZone": "Asia/Seoul"},
            "end": {"dateTime": end, "timeZone": "Asia/Seoul"},
        }
        if location:
            event_body["location"] = location
        if description:
            event_body["description"] = description

        event = service.events().insert(
            calendarId=settings.GOOGLE_CALENDAR_ID,
            body=event_body,
        ).execute()

        link = event.get("htmlLink", "")
        logger.info("Google Calendar 이벤트 생성 완료: %s", link)
        return link

    except Exception as e:
        logger.error("Google Calendar 이벤트 생성 실패: %s", e)
        return None
