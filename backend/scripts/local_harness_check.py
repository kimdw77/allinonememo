# -*- coding: utf-8 -*-
"""
scripts/local_harness_check.py
my-kms 전체 .md 파일을 GitHub API로 내려받아 로컬에서 HARNESS 1-1 검사 실행.
Actions 권한 불필요 — Contents: Read 만으로 동작.

실행: $env:GITHUB_TOKEN="ghp_xxx"; python backend/scripts/local_harness_check.py
"""
import base64, os, sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import yaml

TOKEN  = os.environ.get("GITHUB_TOKEN", "")
REPO   = os.environ.get("GITHUB_REPO",  "kimdw77/my-kms")
BRANCH = os.environ.get("GITHUB_BRANCH","main")

ALLOWED_TYPES           = {"entity", "concept", "note", "summary", "index"}
ALLOWED_DOMAINS         = {"personal", "kita", "shared"}
ALLOWED_CONFIDENTIALITY = {"public", "personal", "kita-internal"}

EXCLUDE_DIRS         = {".git", ".harness", ".obsidian", "node_modules", "__pycache__", ".pytest_cache"}
EXCLUDE_NAME_PREFIXES = ("SPEC-", "HARNESS-")
EXCLUDE_FILENAMES    = {"log.md", "README.md"}

REQUIRED_KEYS = {"title", "created", "updated", "type", "domain", "confidentiality", "tags"}


def collect_md_files(repo, branch):
    """repo 내 모든 .md 파일 (path, content) 반환."""
    results = []
    def recurse(path):
        try:
            items = repo.get_contents(path, ref=branch)
            if not isinstance(items, list): items = [items]
            for item in items:
                parts = item.path.split("/")
                if any(p in EXCLUDE_DIRS for p in parts):
                    continue
                if item.type == "dir":
                    recurse(item.path)
                elif item.name.endswith(".md"):
                    if item.name in EXCLUDE_FILENAMES:
                        continue
                    if any(item.name.startswith(p) for p in EXCLUDE_NAME_PREFIXES):
                        continue
                    content = base64.b64decode(item.content).decode("utf-8")
                    results.append((item.path, content))
        except Exception as e:
            print(f"  [err] {path}: {e}")
    recurse("")
    return results


def check_file(path, content):
    errors = []
    if not content.startswith("---"):
        return [f"{path} — 프론트매터 없음"]

    parts = content.split("---", 2)
    if len(parts) < 3:
        return [f"{path} — 프론트매터 닫힘(---) 없음"]

    try:
        fm = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as e:
        return [f"{path} — YAML 파싱 오류: {e}"]

    if not isinstance(fm, dict):
        return [f"{path} — 프론트매터가 dict가 아님"]

    # 필수 키
    for key in REQUIRED_KEYS:
        if key not in fm:
            errors.append(f"{path} — 필수 키 누락: '{key}'")

    # type 검증
    t = fm.get("type", "")
    if t and t not in ALLOWED_TYPES:
        errors.append(f"{path} — type='{t}' 허용값: {sorted(ALLOWED_TYPES)}")

    # domain 검증
    d = fm.get("domain", "")
    if d and d not in ALLOWED_DOMAINS:
        errors.append(f"{path} — domain='{d}' 허용값: {sorted(ALLOWED_DOMAINS)}")

    # confidentiality 검증
    c = fm.get("confidentiality", "")
    if c and c not in ALLOWED_CONFIDENTIALITY:
        errors.append(f"{path} — confidentiality='{c}' 허용값: {sorted(ALLOWED_CONFIDENTIALITY)}")

    # tags 타입
    tags = fm.get("tags", [])
    if not isinstance(tags, list):
        errors.append(f"{path} — tags가 list가 아님: {type(tags).__name__}")
    else:
        for i, tag in enumerate(tags):
            if not isinstance(tag, str):
                errors.append(f"{path} — tags[{i}]={tag!r} (str이어야 함)")

    # sources (index 아니면 1개 이상)
    is_index = path.endswith("index.md") or fm.get("type") == "index"
    if not is_index:
        srcs = fm.get("sources") or []
        if not srcs:
            errors.append(f"{path} — sources 없음 (index 타입 아닌 파일은 1개 이상 필요)")

    return errors


def main():
    if not TOKEN:
        print("[ERROR] GITHUB_TOKEN 없음"); sys.exit(1)

    from github import Auth, Github
    repo = Github(auth=Auth.Token(TOKEN)).get_repo(REPO)

    print(f"[INFO] {REPO} 파일 수집 중...")
    files = collect_md_files(repo, BRANCH)
    print(f"[INFO] 검사 대상: {len(files)}개 파일\n")

    all_errors = []
    for path, content in sorted(files):
        errs = check_file(path, content)
        if errs:
            for e in errs:
                print(f"  FAIL  {e}")
            all_errors.extend(errs)
        else:
            print(f"  OK    {path}")

    print(f"\n{'='*50}")
    if all_errors:
        print(f"[FAIL] {len(all_errors)}건 위반")
    else:
        print("[PASS] 모든 파일 통과")


if __name__ == "__main__":
    main()
