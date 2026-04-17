"""
fetcher.py — URL 본문 추출 서비스
링크를 보내면 해당 페이지의 제목·본문을 가져와 Claude 분류에 사용
"""
import logging
from typing import Optional

import httpx
from bs4 import BeautifulSoup

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


def fetch_url_content(url: str) -> Optional[str]:
    """
    URL에서 제목 + 본문 텍스트 추출.
    실패 시 None 반환 (데이터 손실 방지).
    """
    try:
        with httpx.Client(timeout=10, follow_redirects=True, headers=HEADERS) as client:
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
