# -*- coding: utf-8 -*-
"""
scripts/delete_mykms_concepts.py
my-kms의 entities/concepts 폴더 파일을 삭제해 wiki_compiler가 재생성하게 함.
(깨진 wikilink 수정을 위한 1회성 정리)
"""
import base64, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

TOKEN  = os.environ.get("GITHUB_TOKEN", "")
REPO   = os.environ.get("GITHUB_REPO",  "kimdw77/my-kms")
BRANCH = os.environ.get("GITHUB_BRANCH","main")

if not TOKEN:
    print("GITHUB_TOKEN 없음"); sys.exit(1)

from github import Auth, Github, GithubException
repo = Github(auth=Auth.Token(TOKEN)).get_repo(REPO)

targets = []
for prefix in ["personal/entities", "personal/concepts", "kita/entities", "kita/concepts"]:
    try:
        items = repo.get_contents(prefix, ref=BRANCH)
        if not isinstance(items, list): items = [items]
        for item in items:
            if item.name.endswith(".md") and item.name != ".gitkeep":
                targets.append((item.path, item.sha))
    except GithubException as e:
        if e.status != 404:
            print(f"[WARN] {prefix}: {e}")

if not targets:
    print("[INFO] 삭제할 wiki 페이지 없음"); sys.exit(0)

print(f"삭제 대상 {len(targets)}개:")
for path, _ in targets:
    print(f"  {path}")

confirm = input("\n삭제하겠습니까? [y/N] ").strip().lower()
if confirm != "y":
    print("취소"); sys.exit(0)

for path, sha in targets:
    repo.delete_file(
        path=path,
        message=f"chore: broken wikilink 수정을 위한 wiki 페이지 재생성 준비 [{path}]",
        sha=sha,
        branch=BRANCH,
    )
    print(f"  [DEL] {path}")

print(f"\n[OK] {len(targets)}개 삭제 완료. 다음 노트 sync 시 wiki_compiler가 재생성합니다.")
