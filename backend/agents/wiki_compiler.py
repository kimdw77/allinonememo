"""
agents/wiki_compiler.py — Wiki Compiler Agent (Phase 9-2)

노트가 my-kms에 push된 후 실행.
entity/concept 추출 → wiki 페이지 생성·업데이트.

HARNESS Layer 2:
  2-1. 출처 추적성: 프롬프트에서 source note 외 정보 사용 금지
  2-2. 모순 감지: 기존 페이지와 LLM 비교 (최대 2회 재시도)
  2-5. 변경 최소성: 최대 5페이지, 50% 이상 재작성 → 사용자 큐
"""
import asyncio
import base64
import json
import logging
import os
from datetime import datetime
from typing import Optional

from config import KST, settings

logger = logging.getLogger(__name__)

_MAX_PAGES = 5        # HARNESS 2-5: 노트 1건당 최대 수정 페이지
_MAX_REWRITE = 0.5    # HARNESS 2-5: 재작성 비율 임계치

_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")

_EXTRACT_PROMPT = """\
다음 노트에서 독립적인 위키 페이지를 만들 가치가 있는 항목만 추출하라.

기준:
- entity: 고유 명사 (사람·기관·제품·서비스)
- concept: 개념·기술·전략·방법론 (일반 명사)
- 너무 일반적인 단어(예: AI, 한국, 회사)는 제외
- 최대 5개

노트:
제목: {title}
요약: {summary}
본문: {content}

JSON으로만 응답. 부가 설명 없이:
{{"items": [{{"type": "entity" 또는 "concept", "name": "정확한 이름", "summary": "1문장 설명"}}]}}"""

_ENTITY_PROMPT = """\
다음 노트를 바탕으로 '{name}' 엔티티의 위키 페이지 내용을 작성하라.

[HARNESS 2-1 규칙]
1. 소스 노트에 있는 정보만 사용할 것
2. 소스 노트에 없는 사실은 절대 추가하지 말 것
3. 불확실하면 해당 필드를 빈 문자열로 두기

소스 노트:
제목: {title}
요약: {summary}
본문: {content}
{existing_section}
JSON으로만 응답:
{{"affiliation": "소속", "role": "역할", "summary": "2-3문장 요약", \
"related_pages": "관련 페이지 마크다운 (없으면 빈 문자열)", "tags": ["태그1"]}}"""

_CONCEPT_PROMPT = """\
다음 노트를 바탕으로 '{name}' 개념의 위키 페이지 내용을 작성하라.

[HARNESS 2-1 규칙]
1. 소스 노트에 있는 정보만 사용할 것
2. 소스 노트에 없는 사실은 절대 추가하지 말 것
3. 불확실하면 해당 필드를 빈 문자열로 두기

소스 노트:
제목: {title}
요약: {summary}
본문: {content}
{existing_section}
JSON으로만 응답:
{{"overview": "개요 2-3문장", "key_content": "핵심 내용 마크다운", \
"related_pages": "관련 페이지 마크다운 (없으면 빈 문자열)", \
"references": "출처 마크다운 (없으면 빈 문자열)", "tags": ["태그1"]}}"""

_CONTRADICTION_PROMPT = """\
기존 위키 페이지와 새 내용 사이에 사실적 모순이 있는지 검토하라.

기존:
{existing}

새 내용:
{new_content}

모순이 있으면 "CONTRADICTION: (설명)"으로, 없으면 "OK"만 응답하라."""


async def compile_wiki(note: dict, domain: str, trace_id: str) -> dict:
    """
    노트 → entity/concept 추출 → wiki 페이지 생성·업데이트.
    fire-and-forget: 예외 전파 없음.
    """
    if not settings.GITHUB_TOKEN or not settings.GITHUB_REPO:
        return {"skipped": True}

    try:
        loop = asyncio.get_running_loop()

        # 1. entity/concept 추출 (Haiku — 비용 절감)
        items = await loop.run_in_executor(None, _extract_items, note, trace_id)
        if not items:
            logger.info("wiki_compiler: 추출 항목 없음 trace=%s", trace_id[:8])
            return {"pages_created": 0, "pages_updated": 0}

        items = items[:_MAX_PAGES]  # HARNESS 2-5
        results = {"pages_created": 0, "pages_updated": 0, "pages_rejected": 0, "pages_queued": 0}

        # 2. 순차 처리 (동시 SHA 충돌 방지)
        for item in items:
            r = await loop.run_in_executor(None, _process_item, note, domain, item, trace_id)
            for k in results:
                results[k] += r.get(k, 0)

        logger.info(
            "wiki_compiler 완료 | +%d ~%d -%d Q%d trace=%s",
            results["pages_created"], results["pages_updated"],
            results["pages_rejected"], results["pages_queued"], trace_id[:8],
        )
        return results

    except Exception as e:
        logger.error("wiki_compiler 실패: %s trace=%s", e, trace_id[:8])
        return {"error": str(e)}


# ── entity/concept 추출 ───────────────────────────────────────────────


def _extract_items(note: dict, trace_id: str) -> list[dict]:
    """Claude Haiku로 entity/concept 목록 추출."""
    import anthropic
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    prompt = _EXTRACT_PROMPT.format(
        title=note.get("title") or note.get("summary") or "",
        summary=note.get("summary") or "",
        content=(note.get("raw_content") or "")[:800],
    )
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        # JSON 블록 추출
        if "```" in raw:
            raw = raw.split("```")[1].lstrip("json").strip()
        data = json.loads(raw)
        return data.get("items") or []
    except Exception as e:
        logger.warning("entity 추출 실패: %s trace=%s", e, trace_id[:8])
        return []


# ── 단일 항목 처리 ────────────────────────────────────────────────────


def _process_item(note: dict, domain: str, item: dict, trace_id: str) -> dict:
    """단일 entity/concept wiki 페이지 생성·업데이트."""
    from github import GithubException
    from services.github_sync import _get_repo
    from utils.slug import to_slug

    name = (item.get("name") or "").strip()
    item_type = item.get("type", "concept")
    if not name:
        return {"pages_rejected": 1}

    folder = "entities" if item_type == "entity" else "concepts"
    filepath = f"{domain}/{folder}/{to_slug(name)}.md"
    branch = settings.GITHUB_BRANCH or "main"

    try:
        repo = _get_repo()

        # 기존 페이지 조회
        existing_content: Optional[str] = None
        existing_sha: Optional[str] = None
        try:
            ef = repo.get_contents(filepath, ref=branch)
            existing_content = base64.b64decode(ef.content).decode("utf-8")
            existing_sha = ef.sha
        except GithubException as e:
            if e.status != 404:
                raise

        # wiki 페이지 생성
        new_content = _generate_page(note, domain, item, existing_content, trace_id)
        if not new_content:
            return {"pages_rejected": 1}

        # HARNESS 2-5: 재작성 비율 검사
        if existing_content:
            ratio = _change_ratio(existing_content, new_content)
            if ratio > _MAX_REWRITE:
                logger.warning(
                    "HARNESS 2-5: 재작성 %.0f%% > 50%% → 사용자 큐 %s trace=%s",
                    ratio * 100, filepath, trace_id[:8],
                )
                return {"pages_queued": 1}

        commit_msg = f"wiki: {name} [trace:{trace_id[:8]}]"
        encoded = new_content.encode("utf-8")
        if existing_sha:
            repo.update_file(filepath, commit_msg, encoded, existing_sha, branch=branch)
            return {"pages_updated": 1}
        else:
            repo.create_file(filepath, commit_msg, encoded, branch=branch)
            return {"pages_created": 1}

    except Exception as e:
        logger.error("wiki 처리 실패 name=%s: %s trace=%s", name, e, trace_id[:8])
        return {"pages_rejected": 1}


# ── wiki 페이지 생성 (HARNESS 2-1 + 2-2) ─────────────────────────────


def _generate_page(
    note: dict,
    domain: str,
    item: dict,
    existing_content: Optional[str],
    trace_id: str,
) -> Optional[str]:
    """Claude Sonnet으로 wiki 페이지 생성. HARNESS 2-1 provenance + 2-2 모순 감지."""
    import anthropic
    from jinja2 import Environment, FileSystemLoader

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    item_type = item.get("type", "concept")
    name = item.get("name", "")
    now_date = datetime.now(KST).strftime("%Y-%m-%d")

    existing_section = ""
    if existing_content:
        existing_section = f"\n기존 페이지 (참고·모순 주의):\n{existing_content[:500]}\n"

    base_prompt = (_ENTITY_PROMPT if item_type == "entity" else _CONCEPT_PROMPT).format(
        name=name,
        title=note.get("title") or note.get("summary") or "",
        summary=note.get("summary") or "",
        content=(note.get("raw_content") or "")[:1000],
        existing_section=existing_section,
    )

    prompt = base_prompt
    for attempt in range(1, 3):
        try:
            resp = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = resp.content[0].text.strip()
            if "```" in raw:
                raw = raw.split("```")[1].lstrip("json").strip()
            data = json.loads(raw)
        except Exception as e:
            logger.warning("wiki 생성 실패 (시도 %d/%d): %s", attempt, 2, e)
            return None

        # HARNESS 2-2: 모순 감지 (기존 페이지 있을 때 첫 시도에서만)
        if existing_content and attempt == 1:
            contradiction = _check_contradiction(client, existing_content, str(data))
            if contradiction:
                logger.warning(
                    "HARNESS 2-2 모순 감지 → 재작성: %s trace=%s",
                    contradiction[:80], trace_id[:8],
                )
                prompt = base_prompt + (
                    f"\n\n[재작성 요청] 이전 생성에서 모순 발견: {contradiction}\n"
                    "기존 페이지 내용과 충돌하지 않게 재작성하라."
                )
                continue

        # 템플릿 렌더링
        try:
            env = Environment(loader=FileSystemLoader(_TEMPLATE_DIR), autoescape=False)
            tpl = env.get_template(
                "entity_template.md.j2" if item_type == "entity" else "concept_template.md.j2"
            )
            note_title = note.get("title") or note.get("summary") or "노트"
            note_ref = f"- {now_date} {note_title} (note_id:{(note.get('id') or '')[:8]})"
            return tpl.render(
                name=name,
                created=now_date,
                updated=now_date,
                domain=domain,
                sources=[f"note_id:{note.get('id', '')}"],
                tags=data.get("tags") or note.get("keywords") or [],
                # entity 전용
                affiliation=data.get("affiliation", ""),
                role=data.get("role", ""),
                summary=data.get("summary", ""),
                # concept 전용
                overview=data.get("overview", ""),
                key_content=data.get("key_content", ""),
                references=data.get("references", ""),
                # 공통
                related_notes=note_ref,
                related_pages=data.get("related_pages", ""),
                now=datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
                trace_id=trace_id,
            )
        except Exception as e:
            logger.error("템플릿 렌더링 실패: %s", e)
            return None

    return None


# ── HARNESS 2-2: 모순 감지 ───────────────────────────────────────────


def _check_contradiction(client, existing: str, new_content: str) -> Optional[str]:
    """모순이 있으면 설명 반환, 없으면 None."""
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            messages=[{
                "role": "user",
                "content": _CONTRADICTION_PROMPT.format(
                    existing=existing[:400],
                    new_content=new_content[:400],
                ),
            }],
        )
        result = resp.content[0].text.strip()
        if result.upper().startswith("CONTRADICTION"):
            return result[len("CONTRADICTION:"):].strip()
        return None
    except Exception:
        return None


# ── HARNESS 2-5: 변경 비율 ───────────────────────────────────────────


def _change_ratio(old: str, new: str) -> float:
    """줄 기반 변경 비율 (0.0 ~ 1.0)."""
    old_lines = set(old.splitlines())
    new_lines = set(new.splitlines())
    if not old_lines:
        return 0.0
    changed = len(old_lines.symmetric_difference(new_lines))
    return changed / (len(old_lines) + len(new_lines))
