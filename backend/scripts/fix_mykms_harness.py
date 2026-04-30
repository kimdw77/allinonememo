# -*- coding: utf-8 -*-
"""
scripts/fix_mykms_harness.py -- my-kms HARNESS check_frontmatter.py 패치
  - log.md 를 검사 대상에서 제외 (frontmatter 없는 시스템 로그 파일)

실행 방법:
  $env:GITHUB_TOKEN = "ghp_xxx"
  python backend/scripts/fix_mykms_harness.py
"""
import base64, difflib, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

TOKEN    = os.environ.get("GITHUB_TOKEN", "")
REPO     = os.environ.get("GITHUB_REPO",   "kimdw77/my-kms")
BRANCH   = os.environ.get("GITHUB_BRANCH", "main")
PATH     = "scripts/harness/check_frontmatter.py"

OLD_EXCLUDE = 'EXCLUDE_NAME_PREFIXES = ("SPEC-", "HARNESS-")'
NEW_EXCLUDE = (
    'EXCLUDE_NAME_PREFIXES = ("SPEC-", "HARNESS-")\n'
    'EXCLUDE_FILENAMES = {"log.md", "README.md"}  # frontmatter 없는 시스템 파일'
)

OLD_FILTER = (
    "    md_files = sorted(\n"
    "        f for f in vault_root.rglob(\"*.md\")\n"
    "        if not any(part in EXCLUDE_DIRS for part in f.parts)\n"
    "        and not any(f.name.startswith(p) for p in EXCLUDE_NAME_PREFIXES)\n"
    "    )"
)
NEW_FILTER = (
    "    md_files = sorted(\n"
    "        f for f in vault_root.rglob(\"*.md\")\n"
    "        if not any(part in EXCLUDE_DIRS for part in f.parts)\n"
    "        and not any(f.name.startswith(p) for p in EXCLUDE_NAME_PREFIXES)\n"
    "        and f.name not in EXCLUDE_FILENAMES\n"
    "    )"
)


def main():
    if not TOKEN:
        print("[ERROR] GITHUB_TOKEN 없음 -- $env:GITHUB_TOKEN = 'ghp_xxx'")
        sys.exit(1)

    from github import Auth, Github
    repo = Github(auth=Auth.Token(TOKEN)).get_repo(REPO)

    f = repo.get_contents(PATH, ref=BRANCH)
    current = base64.b64decode(f.content).decode("utf-8")

    if "EXCLUDE_FILENAMES" in current:
        print("[OK] 이미 패치됨 (EXCLUDE_FILENAMES 존재)")
        return

    if OLD_EXCLUDE not in current:
        print("[ERROR] 예상 패턴 없음 -- check_frontmatter.py 구조가 다릅니다")
        print("현재 파일 내용 (앞 30줄):")
        print("\n".join(current.splitlines()[:30]))
        sys.exit(1)

    patched = current.replace(OLD_EXCLUDE, NEW_EXCLUDE)

    if OLD_FILTER in patched:
        patched = patched.replace(OLD_FILTER, NEW_FILTER)
    else:
        # 필터 라인이 없으면 경고만
        print("[WARN] 파일 필터 패턴을 찾지 못했습니다. EXCLUDE_FILENAMES 선언만 추가합니다.")

    print("=== diff ===")
    diff = difflib.unified_diff(
        current.splitlines(), patched.splitlines(),
        fromfile="before", tofile="after", lineterm="", n=2,
    )
    print("\n".join(list(diff)))

    confirm = input("\nmy-kms 에 push 하겠습니까? [y/N] ").strip().lower()
    if confirm != "y":
        print("취소")
        sys.exit(0)

    repo.update_file(
        path=PATH,
        message="harness: log.md/README.md frontmatter 검사 제외 [auto-patch]",
        content=patched.encode("utf-8"),
        sha=f.sha,
        branch=BRANCH,
    )
    print("[OK] my-kms check_frontmatter.py 업데이트 완료")


if __name__ == "__main__":
    main()
