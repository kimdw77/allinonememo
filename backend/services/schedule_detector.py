"""
services/schedule_detector.py — 텔레그램 메시지에서 일정 정보 추출
Claude API를 사용하여 자연어 일정을 파싱 후 Google Calendar 형식으로 변환
"""
import json
import logging
import re
from datetime import datetime
from typing import Optional

import anthropic

from config import settings, KST

logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

# 일정 관련 키워드 사전 필터 (Claude 호출 전 빠른 검사)
_SCHEDULE_KEYWORDS = (
    "오전", "오후", "시", "분", "오늘", "내일", "모레", "다음주", "이번주",
    "월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일",
    "예약", "미팅", "회의", "약속", "일정", "스케줄", "meeting", "appointment",
)


SCHEDULE_PROMPT = """다음 메시지가 일정·약속·예약 내용인지 판단하고 JSON으로만 응답하라. 부가 설명 없이 JSON만.

메시지: {text}
현재 날짜(KST): {today}

{{
  "is_schedule": true 또는 false,
  "title": "일정 제목 (없으면 빈 문자열)",
  "start": "ISO8601 datetime (예: 2026-04-22T15:00:00+09:00, 시간 불명확 시 해당 날 09:00)",
  "end": "ISO8601 datetime (명시 없으면 start + 1시간)",
  "location": "장소 (없으면 빈 문자열)",
  "description": "추가 메모 (없으면 빈 문자열)"
}}

is_schedule=false이면 나머지 필드는 빈 값으로."""


def _has_schedule_keywords(text: str) -> bool:
    """사전 필터: 일정 관련 키워드가 없으면 Claude 호출 생략"""
    lower = text.lower()
    return any(kw in lower for kw in _SCHEDULE_KEYWORDS)


def detect_schedule(text: str) -> Optional[dict]:
    """
    텍스트에서 일정 정보 추출.
    일정이 아니거나 실패하면 None 반환.
    """
    if not _has_schedule_keywords(text):
        return None

    today_str = datetime.now(KST).strftime("%Y-%m-%d (%A)")

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": SCHEDULE_PROMPT.format(text=text, today=today_str),
            }],
        )
        raw = response.content[0].text if response.content else ""
        cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            return None

        result = json.loads(match.group())
        if not result.get("is_schedule"):
            return None

        return {
            "title": result.get("title", ""),
            "start": result.get("start", ""),
            "end": result.get("end", ""),
            "location": result.get("location", ""),
            "description": result.get("description", ""),
        }

    except Exception as e:
        logger.error("일정 감지 실패: %s", e)
        return None
