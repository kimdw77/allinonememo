"""
agents/wiki_reporter.py — Wiki Linter & Weekly Reporter (Phase 9-3)

두 가지 역할:
  1. lint_wiki(): my-kms wiki 페이지 프론트매터 + 품질 검증 (즉시 실행)
  2. send_weekly_wiki_report(): 주간 wiki 변경 통계 텔레그램 보고
"""
import logging
import re
from datetime import datetime, timedelta
from typing import Optional

from config import KST, settings

logger = logging.getLogger(__name__)

# 필수 프론트매터 키 (entity/concept 공통)
_REQUIRED_KEYS = {"title", "created", "updated", "type", "domain", "tags"}

# 빈 섹션 감지 패턴 (## 헤딩 직후 바로 다음 헤딩 or EOF)
_EMPTY_SECTION_RE = re.compile(r"(##[^\n]+)\n+(?=##|---|\Z)", re.MULTILINE)


# ── Lint ─────────────────────────────────────────────────────────────


async def lint_wiki(domain: Optional[str] = None) -> dict:
    """
    my-kms wiki 페이지 전체 lint.
    domain 지정 시 해당 도메인만, None이면 전체.
    반환: {"total": N, "errors": [...], "warnings": [...]}
    """
    if not settings.GITHUB_TOKEN or not settings.GITHUB_REPO:
        return {"error": "GITHUB_TOKEN/GITHUB_REPO 미설정"}

    import asyncio
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _lint_wiki_sync, domain)


def _lint_wiki_sync(domain: Optional[str]) -> dict:
    from services.github_sync import _get_repo
    from github import GithubException

    branch = settings.GITHUB_BRANCH or "main"
    repo = _get_repo()
    errors: list[dict] = []
    warnings: list[dict] = []
    total = 0

    # 검색 경로: domain/{entities,concepts}/ 또는 */entities|concepts/
    prefixes = []
    if domain:
        prefixes = [f"{domain}/entities", f"{domain}/concepts"]
    else:
        # 루트 수준 디렉토리 목록으로 도메인 탐색
        try:
            root_contents = repo.get_contents("", ref=branch)
            for item in root_contents:
                if item.type == "dir" and not item.name.startswith("."):
                    prefixes.append(f"{item.name}/entities")
                    prefixes.append(f"{item.name}/concepts")
        except GithubException:
            return {"error": "repo 루트 접근 실패"}

    for prefix in prefixes:
        try:
            files = repo.get_contents(prefix, ref=branch)
        except GithubException as e:
            if e.status == 404:
                continue
            raise

        for f in (files if isinstance(files, list) else [files]):
            if not f.name.endswith(".md") or f.name == ".gitkeep":
                continue
            total += 1
            import base64
            content = base64.b64decode(f.content).decode("utf-8")
            file_errors, file_warnings = _lint_file(f.path, content)
            errors.extend(file_errors)
            warnings.extend(file_warnings)

    return {"total": total, "errors": errors, "warnings": warnings}


def _lint_file(path: str, content: str) -> tuple[list, list]:
    errors: list[dict] = []
    warnings: list[dict] = []

    # 1. 프론트매터 파싱
    if not content.startswith("---"):
        errors.append({"path": path, "msg": "프론트매터 없음"})
        return errors, warnings

    parts = content.split("---", 2)
    if len(parts) < 3:
        errors.append({"path": path, "msg": "프론트매터 닫힘 없음"})
        return errors, warnings

    fm_text = parts[1]
    try:
        import yaml
        fm = yaml.safe_load(fm_text) or {}
    except Exception as e:
        errors.append({"path": path, "msg": f"YAML 파싱 오류: {e}"})
        return errors, warnings

    # 2. 필수 키 검사
    for key in _REQUIRED_KEYS:
        if key not in fm:
            errors.append({"path": path, "msg": f"필수 키 누락: {key}"})

    # 3. 태그 타입 검사 (int 혼입 방지)
    tags = fm.get("tags") or []
    if not isinstance(tags, list):
        errors.append({"path": path, "msg": "tags가 list가 아님"})
    else:
        for i, t in enumerate(tags):
            if not isinstance(t, str):
                errors.append({"path": path, "msg": f"tags[{i}]={t!r} — str이어야 함"})

    # 4. 빈 섹션 경고
    body = parts[2]
    empty_sections = _EMPTY_SECTION_RE.findall(body)
    for sec in empty_sections:
        warnings.append({"path": path, "msg": f"빈 섹션: {sec.strip()}"})

    # 5. 본문 길이 경고 (너무 짧으면 stub)
    if len(body.strip()) < 100:
        warnings.append({"path": path, "msg": "본문 너무 짧음 (<100자) — stub 의심"})

    return errors, warnings


# ── Weekly Report ─────────────────────────────────────────────────────


async def send_weekly_wiki_report() -> None:
    """
    주간 wiki 변경 통계 집계 → 텔레그램 전송.
    main.py APScheduler에서 매주 월요일 09:30 KST 호출.
    """
    if not settings.GITHUB_TOKEN or not settings.GITHUB_REPO:
        logger.warning("wiki_reporter: GitHub 환경변수 미설정 — 보고 건너뜀")
        return

    try:
        import asyncio
        loop = asyncio.get_running_loop()
        stats = await loop.run_in_executor(None, _collect_weekly_stats)
        msg = _format_report(stats)
        await _send_telegram(msg)
        logger.info("주간 wiki 보고서 전송 완료")
    except Exception as e:
        logger.error("주간 wiki 보고서 실패: %s", e)


def _collect_weekly_stats() -> dict:
    """지난 7일간 wiki 파일 커밋 통계."""
    from services.github_sync import _get_repo

    repo = _get_repo()
    branch = settings.GITHUB_BRANCH or "main"
    since = datetime.now(KST) - timedelta(days=7)

    created: list[str] = []
    updated: list[str] = []
    seen: set[str] = set()

    try:
        commits = repo.get_commits(sha=branch, since=since)
        for commit in commits:
            msg = commit.commit.message or ""
            if not msg.startswith("wiki:"):
                continue
            for f in commit.files:
                path = f.filename
                if not (path.endswith(".md") and ("/entities/" in path or "/concepts/" in path)):
                    continue
                if path in seen:
                    continue
                seen.add(path)
                if f.status == "added":
                    created.append(path)
                elif f.status == "modified":
                    updated.append(path)
    except Exception as e:
        logger.warning("wiki 통계 수집 실패: %s", e)

    return {"created": created, "updated": updated, "since": since}


def _format_report(stats: dict) -> str:
    created = stats.get("created") or []
    updated = stats.get("updated") or []
    since: datetime = stats["since"]

    lines = [
        f"📖 *주간 Wiki 보고서* ({since.strftime('%m/%d')} ~ 오늘)",
        f"신규 페이지: {len(created)}개  |  업데이트: {len(updated)}개",
    ]

    if created:
        lines.append("\n*신규*")
        for p in created[:10]:
            name = p.split("/")[-1].replace(".md", "")
            lines.append(f"  ＋ {name}")
        if len(created) > 10:
            lines.append(f"  … 외 {len(created) - 10}개")

    if updated:
        lines.append("\n*업데이트*")
        for p in updated[:10]:
            name = p.split("/")[-1].replace(".md", "")
            lines.append(f"  ～ {name}")
        if len(updated) > 10:
            lines.append(f"  … 외 {len(updated) - 10}개")

    if not created and not updated:
        lines.append("이번 주 wiki 변경 없음.")

    return "\n".join(lines)


# ── 내부 유틸 ─────────────────────────────────────────────────────────


async def _send_telegram(message: str) -> None:
    try:
        import httpx
        token = settings.TELEGRAM_BOT_TOKEN
        chat_id = settings.TELEGRAM_ALLOWED_USER_ID
        if not token or not chat_id:
            return
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"},
            )
    except Exception as e:
        logger.warning("텔레그램 전송 실패 (무시): %s", e)
