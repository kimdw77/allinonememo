"""
services/rss_fetcher.py — RSS 피드 수집 서비스
등록된 RSS URL에서 새 글을 가져와 분류 후 notes 테이블에 저장
"""
import logging

import feedparser

from db.notes import insert_note
from db.subscriptions import get_active_subscriptions, update_last_fetched, url_already_saved
from services.classifier import classify_content

logger = logging.getLogger(__name__)

# 피드 항목당 전달할 최대 텍스트 길이
MAX_CONTENT_LENGTH = 2000


def fetch_all_feeds() -> None:
    """모든 활성 RSS 구독을 순회하며 새 항목 수집. 스케줄러에서 호출."""
    subscriptions = get_active_subscriptions()
    if not subscriptions:
        logger.info("활성 RSS 구독 없음")
        return

    logger.info("RSS 수집 시작: %d개 구독", len(subscriptions))
    for sub in subscriptions:
        try:
            _fetch_single_feed(sub)
        except Exception as e:
            logger.error("RSS 피드 수집 실패 (%s): %s", sub.get("url"), e)


def _fetch_single_feed(subscription: dict) -> None:
    """단일 RSS 피드 수집 및 저장"""
    url = subscription["url"]
    sub_id = subscription["id"]

    feed = feedparser.parse(url)
    if feed.bozo and not feed.entries:
        logger.warning("RSS 파싱 오류 (%s): %s", url, feed.bozo_exception)
        return

    new_count = 0
    for entry in feed.entries[:20]:  # 최신 20개만 처리
        entry_url = entry.get("link", "")
        if not entry_url:
            continue

        # 중복 확인
        if url_already_saved(entry_url):
            continue

        # 제목 + 요약 텍스트 추출
        title = entry.get("title", "")
        summary = entry.get("summary", "") or entry.get("description", "")
        raw_content = f"{title}\n\n{summary}".strip()[:MAX_CONTENT_LENGTH]

        if not raw_content:
            continue

        # Claude로 분류
        classify_result = classify_content(raw_content)

        insert_note(
            source="rss",
            raw_content=raw_content,
            summary=classify_result.get("summary", ""),
            keywords=classify_result.get("keywords", []),
            category=classify_result.get("category", "기타"),
            content_type=classify_result.get("content_type", "article"),
            url=entry_url,
            metadata={"feed_url": url, "feed_title": feed.feed.get("title", "")},
        )
        new_count += 1
        logger.info("RSS 새 항목 저장: %s", entry_url)

    update_last_fetched(sub_id)
    logger.info("RSS 수집 완료 (%s): 신규 %d개", url, new_count)
