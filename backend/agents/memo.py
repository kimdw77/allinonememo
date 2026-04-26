"""
agents/memo.py — 메모 저장 에이전트 (분류·요약·Supabase 저장)
"""
import logging

from agents.base import AgentInput, AgentOutput, BaseAgent

logger = logging.getLogger(__name__)

_HIGH_IMPORTANCE_CATEGORIES = {"비즈니스", "AI", "기술", "무역/수출"}
_LOW_IMPORTANCE_CATEGORIES = {"개인메모"}
_URGENT_KEYWORDS = {"긴급", "urgent", "asap", "마감", "데드라인", "중요"}


def _infer_importance(classify_result: dict) -> str:
    """카테고리·키워드 기반 중요도 추론. LLM 호출 없음."""
    category = classify_result.get("category", "기타")
    kw_lower = {k.lower() for k in (classify_result.get("keywords") or [])}
    if _URGENT_KEYWORDS & kw_lower:
        return "high"
    if category in _HIGH_IMPORTANCE_CATEGORIES:
        return "high"
    if category in _LOW_IMPORTANCE_CATEGORIES:
        return "low"
    return "medium"


class MemoAgent(BaseAgent):
    name = "memo"

    def analyze(self, inp: AgentInput) -> dict:
        """
        분류·요약만 수행. DB 저장 없음.
        파이프라인(RouterAgent)에서 SaveExecutor 호출 전 단계로 사용.
        반환: {title, summary, category, keywords, highlights, content_type, importance, raw_text, url}
        """
        from services.classifier import classify_content
        from services.fetcher import fetch_url_content

        content = inp.content
        url: str | None = inp.metadata.get("url") if inp.metadata else None

        if url:
            fetched = fetch_url_content(url)
            if fetched:
                content = fetched
                logger.info("URL 본문 추출 성공: %s (%d자)", url, len(fetched))

        classify_result = classify_content(content)
        importance = _infer_importance(classify_result)

        return {
            "title": (classify_result.get("summary") or "")[:50],
            "summary": classify_result.get("summary", ""),
            "category": classify_result.get("category", "기타"),
            "keywords": classify_result.get("keywords", []),
            "highlights": classify_result.get("highlights", []),
            "content_type": classify_result.get("content_type", "other"),
            "importance": importance,
            "raw_text": inp.content,
            "url": url,
        }

    def run(self, inp: AgentInput) -> AgentOutput:
        try:
            from services.classifier import classify_content
            from services.fetcher import fetch_url_content
            from db.notes import insert_note

            content = inp.content
            url: str | None = inp.metadata.get("url") if inp.metadata else None

            # URL이 있으면 본문 크롤링 후 분류에 활용
            if url:
                fetched = fetch_url_content(url)
                if fetched:
                    content = fetched
                    logger.info("URL 본문 추출 성공: %s (%d자)", url, len(fetched))

            classify_result = classify_content(content)

            note = insert_note(
                source=inp.source,
                raw_content=inp.content,
                summary=classify_result.get("summary", ""),
                highlights=classify_result.get("highlights", []),
                keywords=classify_result.get("keywords", []),
                category=classify_result.get("category", "기타"),
                content_type=classify_result.get("content_type", "other"),
                url=url,
                metadata=inp.metadata,
            )

            note_id = note["id"] if note else None
            cat = classify_result.get("category", "기타")
            summary_preview = (classify_result.get("summary") or inp.content)[:80]
            reply = f"✅ 노트 저장\n📂 [{cat}] {summary_preview}"

            return AgentOutput(
                agent_name=self.name,
                success=note is not None,
                result={"note_id": note_id, "classify": classify_result},
                reply_text=reply,
            )

        except Exception as e:
            logger.error("MemoAgent 실패: %s", e)
            return AgentOutput(
                agent_name=self.name,
                success=False,
                result={},
                reply_text="❌ 노트 저장 실패",
            )
