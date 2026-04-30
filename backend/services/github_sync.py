"""
services/github_sync.py — PyGithub 기반 my-kms Repo push 로직 (Phase 9-1)

이 모듈만이 GitHub API를 호출한다. workers/sync_worker.py 가 이 모듈을 import한다.
personal/notes/ 또는 kita/notes/ 폴더에만 write — 다른 폴더는 절대 수정하지 않는다.
"""
import base64
import logging
import os
import time
from datetime import datetime
from typing import Optional

from config import KST, settings

logger = logging.getLogger(__name__)

# Jinja2 환경: backend/templates/ 디렉터리 기준
_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")

# HARNESS 3-3: kita-internal 민감정보 감지 키워드
_KITA_INTERNAL_KEYWORDS: frozenset[str] = frozenset({
    "kita-internal", "내부문서", "기밀", "대외비", "임원회의", "이사회",
    "내부정보", "비공개",
})


def _get_jinja_env():
    from jinja2 import Environment, FileSystemLoader
    return Environment(loader=FileSystemLoader(_TEMPLATE_DIR), autoescape=False)


def _get_repo():
    """GitHub Repo 객체 반환 (호출 시마다 새 연결 — 토큰 갱신 대응)."""
    from github import Github
    return Github(settings.GITHUB_TOKEN).get_repo(settings.GITHUB_REPO)


# ── 도메인 결정 ────────────────────────────────────────────────────────


def determine_domain(note: dict) -> str:
    """
    노트의 저장 도메인을 personal / kita 로 결정.

    우선순위:
    1. 명시적 태그 (kita / 회원사 / personal / 개인)
    2. 카테고리 (무역정책·회원사·수출입동향·교육 → kita)
    3. 환경변수 WIKI_DEFAULT_DOMAIN (기본 personal)
    """
    keywords: list[str] = note.get("keywords") or []
    category: str = note.get("category") or ""

    if "kita" in keywords or "회원사" in keywords:
        return "kita"
    if "personal" in keywords or "개인" in keywords:
        return "personal"

    kita_categories = {"무역정책", "회원사", "수출입동향", "교육"}
    if category in kita_categories:
        return "kita"

    return settings.WIKI_DEFAULT_DOMAIN or "personal"


# ── HARNESS 3-3: 오라우팅 검증 ────────────────────────────────────────


def validate_routing(note: dict, target_domain: str) -> dict:
    """
    민감정보 오라우팅 검증 (HARNESS Layer 3-3).

    kita-internal 키워드가 non-kita 폴더로 라우팅되려 하면 즉시 차단.
    반환: {"blocked": bool, "reason": str, "detected_keywords": list[str]}
    """
    keywords: set[str] = set(note.get("keywords") or [])
    text = " ".join([
        note.get("raw_content") or "",
        note.get("summary") or "",
        note.get("title") or "",
    ]).lower()

    detected: set[str] = set(_KITA_INTERNAL_KEYWORDS & keywords)
    if not detected:
        for kw in _KITA_INTERNAL_KEYWORDS:
            if kw in text:
                detected.add(kw)

    if detected and target_domain != "kita":
        reason = (
            f"kita-internal 키워드({', '.join(detected)})가 "
            f"{target_domain} 폴더로 라우팅 시도"
        )
        return {"blocked": True, "reason": reason, "detected_keywords": list(detected)}

    return {"blocked": False, "reason": "", "detected_keywords": []}


# ── 마크다운 렌더링 ────────────────────────────────────────────────────


def render_note_markdown(note: dict, domain: str, trace_id: str = "") -> str:
    """note dict → Jinja2 템플릿 → 마크다운 문자열."""
    env = _get_jinja_env()
    template = env.get_template("note_template.md.j2")
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")

    related_links: list[dict] = []
    if note.get("related_links"):
        related_links = (note["related_links"].get("articles") or [])

    return template.render(
        note=note,
        domain=domain,
        now=now,
        related_links=related_links,
        trace_id=trace_id,
    )


# ── 파일 경로 생성 ─────────────────────────────────────────────────────


def make_filepath(note: dict, domain: str) -> str:
    """
    {domain}/notes/YYYY-MM-DD-{slug}.md 형식의 경로 반환.
    동일 note_id 재저장 시 동일 경로를 반환하므로 중복 생성 없음.
    """
    from utils.slug import to_slug

    raw_date = note.get("created_at") or datetime.now(KST).isoformat()
    try:
        dt = datetime.fromisoformat(str(raw_date).replace("Z", "+00:00"))
    except ValueError:
        dt = datetime.now(KST)

    date_str = dt.strftime("%Y-%m-%d")
    title = (
        note.get("title")
        or note.get("summary")
        or note.get("id")
        or "untitled"
    )
    slug = to_slug(str(title))
    return f"{domain}/notes/{date_str}-{slug}.md"


# ── GitHub push (낙관적 락 + 3회 재시도) ──────────────────────────────


def push_note(note: dict, domain: str, trace_id: str) -> dict:
    """
    노트를 마크다운으로 GitHub에 push.
    - 파일 미존재: create_file
    - 파일 존재:   update_file (SHA 기반 낙관적 락)
    - 충돌 시 최대 3회 재시도 (지수 백오프 2s, 4s)

    반환: {"path": str, "sha": str, "action": "created"|"updated"}
    Raises: GithubException — 3회 모두 실패 시
    """
    from github import GithubException

    repo = _get_repo()
    branch = settings.GITHUB_BRANCH or "main"
    filepath = make_filepath(note, domain)
    content = render_note_markdown(note, domain, trace_id)
    commit_msg = (
        f"sync: {(note.get('title') or note.get('id') or filepath)[:60]}"
        f" [trace:{trace_id[:8]}]"
    )

    last_exc: Optional[Exception] = None
    for attempt in range(1, 4):
        try:
            try:
                existing = repo.get_contents(filepath, ref=branch)
                result = repo.update_file(
                    path=filepath,
                    message=commit_msg,
                    content=content.encode("utf-8"),
                    sha=existing.sha,
                    branch=branch,
                )
                action = "updated"
            except GithubException as e:
                if e.status != 404:
                    raise
                result = repo.create_file(
                    path=filepath,
                    message=commit_msg,
                    content=content.encode("utf-8"),
                    branch=branch,
                )
                action = "created"

            sha: str = result["commit"].sha
            logger.info(
                "GitHub push 성공 | path=%s action=%s sha=%s trace=%s",
                filepath, action, sha[:8], trace_id[:8],
            )
            _append_log(repo, branch, note, filepath, trace_id)
            return {"path": filepath, "sha": sha, "action": action}

        except GithubException as exc:
            last_exc = exc
            if attempt < 3:
                wait = 2 ** attempt
                logger.warning(
                    "GitHub push 실패 (시도 %d/3), %ds 후 재시도: %s trace=%s",
                    attempt, wait, exc, trace_id[:8],
                )
                time.sleep(wait)
            else:
                logger.error(
                    "GitHub push 3회 실패: %s trace=%s", exc, trace_id[:8],
                )

    raise last_exc  # type: ignore[misc]


# ── log.md 업데이트 ────────────────────────────────────────────────────


def _append_log(repo, branch: str, note: dict, filepath: str, trace_id: str) -> None:
    """
    log.md 에 ingest 한 줄 추가 (read → append → push 단일 commit).
    실패해도 노트 push 결과에 영향 없음.
    """
    try:
        from github import GithubException

        env = _get_jinja_env()
        template = env.get_template("log_entry.md.j2")
        today = datetime.now(KST).strftime("%Y-%m-%d")
        new_line = template.render(
            today=today, note=note, filepath=filepath, trace_id=trace_id,
        )

        log_path = "log.md"
        commit_msg = (
            f"log: {(note.get('title') or note.get('id') or 'note')[:40]}"
            f" ingest [trace:{trace_id[:8]}]"
        )

        try:
            log_file = repo.get_contents(log_path, ref=branch)
            current = base64.b64decode(log_file.content).decode("utf-8")
            updated = current.rstrip("\n") + "\n" + new_line
            repo.update_file(
                path=log_path,
                message=commit_msg,
                content=updated.encode("utf-8"),
                sha=log_file.sha,
                branch=branch,
            )
        except GithubException as e:
            if e.status == 404:
                repo.create_file(
                    path=log_path,
                    message="log: 초기 ingest log 생성",
                    content=("# Ingest Log\n\n" + new_line).encode("utf-8"),
                    branch=branch,
                )
            else:
                raise
    except Exception as e:
        logger.warning("log.md 업데이트 실패 (무시): %s trace=%s", e, trace_id[:8])
