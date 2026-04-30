# -*- coding: utf-8 -*-
"""
scripts/fix_mykms_harness.py -- my-kms HARNESS check_frontmatter.py 패치

실행 방법:
  1. Railway -> allinonememo -> Variables -> GITHUB_TOKEN 값 복사
  2. PowerShell: $env:GITHUB_TOKEN = "ghp_xxx"
  3. python backend/scripts/fix_mykms_harness.py
"""
import base64
import difflib
import os
import re
import sys

# Windows cp949 콘솔 인코딩 문제 방지
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stdin  = io.TextIOWrapper(sys.stdin.buffer,  encoding="utf-8", errors="replace")


def main():
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("[ERROR] GITHUB_TOKEN 환경변수가 없습니다.")
        print("  PowerShell: $env:GITHUB_TOKEN = 'ghp_xxx'")
        sys.exit(1)

    repo_name = os.environ.get("GITHUB_REPO", "kimdw77/my-kms")
    branch    = os.environ.get("GITHUB_BRANCH", "main")

    from github import Github, GithubException
    repo = Github(token).get_repo(repo_name)

    path = ".github/scripts/check_frontmatter.py"
    try:
        f = repo.get_contents(path, ref=branch)
        current = base64.b64decode(f.content).decode("utf-8")
        sha = f.sha
    except GithubException as e:
        print(f"[ERROR] 파일 읽기 실패: {e}")
        sys.exit(1)

    print("=== 현재 파일 (앞 50줄) ===")
    print("\n".join(current.splitlines()[:50]))
    print("=" * 40)

    patched = current

    # 패턴 1: Literal["note"] (Pydantic v1/v2)
    patched = re.sub(
        r'Literal\[(["\'])note\1\]',
        r'Literal[\g<1>note\g<1>, "entity", "concept"]',
        patched,
    )

    # 패턴 2: allowed_types = {"note"} 또는 allowed = {"note"}
    patched = re.sub(
        r'(allowed\w*\s*=\s*\{)\s*(["\'])note\2\s*(\})',
        r'\1"note", "entity", "concept"\3',
        patched,
    )

    # 패턴 3: if v not in {"note"} 또는 if t not in {"note"}
    patched = re.sub(
        r'(not\s+in\s+\{)\s*(["\'])note\2\s*(\})',
        r'\1"note", "entity", "concept"\3',
        patched,
    )

    # 패턴 4: ["note"] 단독 리스트
    patched = re.sub(
        r'(\[)\s*(["\'])note\2\s*(\])',
        r'\1"note", "entity", "concept"\3',
        patched,
    )

    if patched == current:
        print("[WARN] 자동 패턴 매칭 실패. 현재 파일을 확인하세요.")
        print("  check_frontmatter.py 에서 'note' 허용 타입 부분을 찾아")
        print("  'entity', 'concept' 을 직접 추가해야 합니다.")
        sys.exit(1)

    print("\n=== 변경 diff ===")
    diff = list(difflib.unified_diff(
        current.splitlines(), patched.splitlines(),
        fromfile="before", tofile="after",
        lineterm="", n=3,
    ))
    print("\n".join(diff[:40]))
    print("=" * 40)

    confirm = input("\nmy-kms 에 push 하겠습니까? [y/N] ").strip().lower()
    if confirm != "y":
        print("취소")
        sys.exit(0)

    repo.update_file(
        path=path,
        message="harness: entity/concept 타입 허용 추가 [auto-patch]",
        content=patched.encode("utf-8"),
        sha=sha,
        branch=branch,
    )
    print("[OK] my-kms check_frontmatter.py 업데이트 완료")


if __name__ == "__main__":
    main()
