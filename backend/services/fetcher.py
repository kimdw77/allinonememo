"""
fetcher.py — URL 본문 추출 서비스
링크를 보내면 해당 페이지의 제목·본문을 가져와 Claude 분류에 사용
YouTube URL은 자막 추출 우선, 실패 시 일반 크롤링으로 폴백
"""
import ipaddress
import logging
import socket
from typing import Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from services.youtube import is_youtube_url, fetch_youtube_transcript

logger = logging.getLogger(__name__)

# 요청 헤더 (봇 차단 우회)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
}

# SSRF 차단: 허용된 스킴만 허용
_ALLOWED_SCHEMES = {"http", "https"}


def _is_private_ip(hostname: str) -> bool:
    """내부망·루프백·링크로컬 등 SSRF 위험 IP 여부 확인"""
    try:
        ip = ipaddress.ip_address(socket.gethostbyname(hostname))
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
    except Exception:
        return True  # 해석 불가 호스트는 차단


def _is_safe_url(url: str) -> bool:
    """SSRF 공격에 악용될 수 없는 URL인지 검증"""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in _ALLOWED_SCHEMES:
            return False
        hostname = parsed.hostname or ""
        if not hostname:
            return False
        return not _is_private_ip(hostname)
    except Exception:
        return False


def fetch_url_content(url: str) -> Optional[str]:
    """
    URL에서 텍스트 추출.
    YouTube URL은 자막 추출 우선 시도, 실패 시 일반 크롤링 폴백.
    실패 시 None 반환 (데이터 손실 방지).
    """
    # YouTube URL: 자막 추출 우선
    if is_youtube_url(url):
        transcript = fetch_youtube_transcript(url)
        if transcript:
            return transcript
        logger.info("YouTube 자막 없음, 일반 크롤링으로 폴백: %s", url)

    if not _is_safe_url(url):
        logger.warning("SSRF 차단: 허용되지 않은 URL — %s", url)
        return None

    try:
        with httpx.Client(
            timeout=10,
            follow_redirects=True,
            headers=HEADERS,
            max_redirects=3,
        ) as client:
            response = client.get(url)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")

        # 불필요한 태그 제거
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "iframe"]):
            tag.decompose()

        # 제목 추출
        title = ""
        if soup.title:
            title = soup.title.get_text(strip=True)
        elif soup.find("h1"):
            title = soup.find("h1").get_text(strip=True)

        # 본문 추출 (article > main > body 순서로 시도)
        body_tag = (
            soup.find("article")
            or soup.find("main")
            or soup.find("div", class_=lambda c: c and "content" in c.lower() if c else False)
            or soup.body
        )

        body_text = body_tag.get_text(separator=" ", strip=True) if body_tag else ""

        # 제목 + 본문 합치기 (3000자 제한)
        combined = f"{title}\n\n{body_text}".strip()
        return combined[:3000] if combined else None

    except httpx.TimeoutException:
        logger.warning("URL 요청 타임아웃: %s", url)
        return None
    except Exception as e:
        logger.error("URL 본문 추출 실패 (%s): %s", url, e)
        return None
