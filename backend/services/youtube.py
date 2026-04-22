"""
youtube.py — YouTube 영상 자막 추출 서비스
URL에서 영상 ID를 파싱하고, youtube-transcript-api로 자막을 가져온다.
자막 없는 영상은 None 반환 → fetcher.py가 일반 크롤링으로 폴백.
"""
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# YouTube URL 패턴 (youtu.be 단축 URL 포함)
_YT_PATTERNS = [
    r"(?:youtube\.com/watch\?(?:.*&)?v=|youtu\.be/)([A-Za-z0-9_-]{11})",
    r"youtube\.com/shorts/([A-Za-z0-9_-]{11})",
    r"youtube\.com/embed/([A-Za-z0-9_-]{11})",
]

# 자막 우선 언어 순서 (한국어 → 영어 → 자동 생성 순)
_LANG_PRIORITY = ["ko", "en", "ko-KR", "en-US"]


def extract_video_id(url: str) -> Optional[str]:
    """YouTube URL에서 11자리 영상 ID 추출"""
    for pattern in _YT_PATTERNS:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def is_youtube_url(url: str) -> bool:
    """YouTube 링크 여부 확인"""
    return extract_video_id(url) is not None


def fetch_youtube_transcript(url: str) -> Optional[str]:
    """
    YouTube 영상 자막을 텍스트로 반환.
    자막 없거나 비공개·지역 제한 시 None 반환.
    """
    video_id = extract_video_id(url)
    if not video_id:
        return None

    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        transcript = None

        for lang in _LANG_PRIORITY:
            try:
                transcript = transcript_list.find_manually_created_transcript([lang])
                break
            except Exception:
                continue

        if transcript is None:
            for lang in _LANG_PRIORITY:
                try:
                    transcript = transcript_list.find_generated_transcript([lang])
                    break
                except Exception:
                    continue

        if transcript is None:
            available = list(transcript_list)
            if available:
                transcript = available[0]

        if transcript is None:
            logger.info("YouTube 자막 없음: %s", video_id)
            return None

        entries = transcript.fetch()
        text = " ".join(entry["text"] for entry in entries if entry.get("text"))
        text = text[:5000].strip()

        if not text:
            return None

        logger.info("YouTube 자막 추출 성공: %s (%d자, 언어=%s)", video_id, len(text), transcript.language_code)
        return text

    except Exception as e:
        logger.info("YouTube 자막 추출 실패 (%s): %s", video_id, type(e).__name__)
        return None


def fetch_youtube_meta(url: str) -> Optional[str]:
    """
    YouTube oEmbed API로 영상 제목·채널명 조회.
    자막이 없을 때 폴백으로 사용 — 무인증 공개 API.
    """
    try:
        import httpx
        oembed_url = f"https://www.youtube.com/oembed?url={url}&format=json"
        resp = httpx.get(oembed_url, timeout=8, follow_redirects=True)
        if resp.status_code != 200:
            return None
        data = resp.json()
        title = data.get("title", "")
        author = data.get("author_name", "")
        if not title:
            return None
        meta = f"YouTube 영상 제목: {title}"
        if author:
            meta += f"\n채널: {author}"
        logger.info("YouTube oEmbed 조회 성공: %s", title)
        return meta
    except Exception as e:
        logger.info("YouTube oEmbed 실패 (%s): %s", url, e)
        return None
