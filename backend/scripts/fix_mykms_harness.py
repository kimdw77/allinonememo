"""
scripts/fix_mykms_harness.py — my-kms HARNESS check_frontmatter.py 패치

실행 방법:
  1. Railway → allinonememo → Variables → GITHUB_TOKEN 값을 복사
  2. PowerShell: $env:GITHUB_TOKEN = "ghp_xxx"
  3. python backend/scripts/fix_mykms_harness.py
"""
import base64
import os
import re
import sys

def main():
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("❌ GITHUB_TOKEN 환경변수 없음")
        print("   $env:GITHUB_TOKEN = 'ghp_xxx' 설정 후 재실행")
        sys.exit(1)

    repo_name = os.environ.get("GITHUB_REPO", "kimdw77/my-kms")
    branch = os.environ.get("GITHUB_BRANCH", "main")

    from github import Github, GithubException
    g = Github(token)
    repo = g.get_repo(repo_name)

    path = ".github/scripts/check_frontmatter.py"
    try:
        f = repo.get_contents(path, ref=branch)
        current = base64.b64decode(f.content).decode("utf-8")
        sha = f.sha
    except GithubException as e:
        print(f"❌ 파일 읽기 실패: {e}")
        sys.exit(1)

    print("--- 현재 파일 (앞 40줄) ---")
    print("\n".join(current.splitlines()[:40]))
    print("---")

    # entity, concept 을 허용 타입에 추가
    # 패턴 1: {'note'} 또는 {"note"} → {'note', 'entity', 'concept'}
    patched = re.sub(
        r"['\"]note['\"]\s*[,}]",
        lambda m: m.group(0).replace(
            m.group(0),
            "'note', 'entity', 'concept'" + (m.group(0)[-1] if m.group(0)[-1] == "}" else ","),
        ),
        current,
    )

    # 패턴 2: type in ("note") 또는 allowed_types = {"note"}
    patched = re.sub(
        r'(allowed[_\s]?types?\s*=\s*[{(]\s*)["\']note["\'](\s*[})])',
        r'\1"note", "entity", "concept"\2',
        patched,
    )

    # 패턴 3: Literal["note"] (Pydantic)
    patched = re.sub(
        r'Literal\["note"\]',
        'Literal["note", "entity", "concept"]',
        patched,
    )

    # 패턴 4: type: str 검증 중 "note" 만 있는 집합
    patched = re.sub(
        r"(\{['\"])note(['\"])\}",
        r'{\1note\2, "entity", "concept"}',
        patched,
    )

    if patched == current:
        print("⚠️  패턴 자동 매칭 실패 — 현재 파일을 직접 확인하세요")
        print("    entity, concept 을 허용 타입에 수동으로 추가 필요")
        sys.exit(1)

    print("\n--- 변경 diff ---")
    import difflib
    diff = difflib.unified_diff(
        current.splitlines(), patched.splitlines(),
        lineterm="", n=2,
    )
    print("\n".join(list(diff)[:30]))

    confirm = input("\n이 변경을 my-kms에 push할까요? [y/N] ").strip().lower()
    if confirm != "y":
        print("취소")
        sys.exit(0)

    repo.update_file(
        path=path,
        message="harness: entity·concept 타입 허용 추가 [auto-patch]",
        content=patched.encode("utf-8"),
        sha=sha,
        branch=branch,
    )
    print("✅ my-kms check_frontmatter.py 업데이트 완료")


if __name__ == "__main__":
    main()
