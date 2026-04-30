# -*- coding: utf-8 -*-
"""
scripts/fix_mykms_harness.py -- my-kms HARNESS entity/concept 타입 허용 패치

실행 방법:
  PowerShell:
    $env:GITHUB_TOKEN = "ghp_xxx"   # Railway Variables 에서 복사
    python backend/scripts/fix_mykms_harness.py
"""
import base64
import difflib
import os
import re
import sys

# Windows cp949 콘솔 인코딩 대응
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def gh_repo(token, repo_name):
    from github import Auth, Github
    return Github(auth=Auth.Token(token)).get_repo(repo_name)


def list_github_dir(repo, path, branch, depth=0, max_depth=4):
    """재귀적으로 디렉터리 목록 출력."""
    try:
        items = repo.get_contents(path, ref=branch)
        if not isinstance(items, list):
            items = [items]
        for item in sorted(items, key=lambda x: (x.type != "dir", x.path)):
            indent = "  " * depth
            print(f"{indent}{'[DIR] ' if item.type == 'dir' else '      '}{item.path}")
            if item.type == "dir" and depth < max_depth:
                list_github_dir(repo, item.path, branch, depth + 1, max_depth)
    except Exception as e:
        print(f"{'  '*depth}[err] {path}: {e}")


def find_python_files(repo, branch):
    """repo 내 .py 파일 경로 목록 반환."""
    results = []
    def recurse(path):
        try:
            items = repo.get_contents(path, ref=branch)
            if not isinstance(items, list):
                items = [items]
            for item in items:
                if item.type == "dir":
                    recurse(item.path)
                elif item.path.endswith(".py"):
                    results.append((item.path, item.sha))
        except Exception:
            pass
    recurse("")
    return results


def patch_content(content):
    """check_frontmatter.py 에서 허용 타입에 entity/concept 추가."""
    patched = content

    # Literal["note"] -> Literal["note", "entity", "concept"]
    patched = re.sub(
        r'Literal\[(["\'])note\1\]',
        'Literal["note", "entity", "concept"]',
        patched,
    )
    # {"note"} 단독 집합
    patched = re.sub(
        r'\{(["\'])note\1\}',
        '{"note", "entity", "concept"}',
        patched,
    )
    # ["note"] 단독 리스트
    patched = re.sub(
        r'\[(["\'])note\1\]',
        '["note", "entity", "concept"]',
        patched,
    )
    # allowed_types = ... "note" ...
    patched = re.sub(
        r'(allowed\w*\s*=\s*[{\[]\s*)(["\'])note\2(\s*[}\]])',
        r'\1"note", "entity", "concept"\3',
        patched,
    )
    # not in {"note"} 또는 not in ["note"]
    patched = re.sub(
        r'(not\s+in\s+[{\[]\s*)(["\'])note\2(\s*[}\]])',
        r'\1"note", "entity", "concept"\3',
        patched,
    )
    # == "note" 단독 비교 -> in {"note", "entity", "concept"}
    patched = re.sub(
        r'(type\s*==\s*)(["\'])note\2(?!\s*["\'])',
        r'type in {"note", "entity", "concept"}',
        patched,
    )
    return patched


def main():
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("[ERROR] GITHUB_TOKEN 이 설정되지 않았습니다.")
        print("  PowerShell: $env:GITHUB_TOKEN = 'ghp_xxxx'")
        sys.exit(1)

    repo_name = os.environ.get("GITHUB_REPO", "kimdw77/my-kms")
    branch    = os.environ.get("GITHUB_BRANCH", "main")

    print(f"[INFO] repo={repo_name}  branch={branch}")
    repo = gh_repo(token, repo_name)

    # 1. .github 디렉터리 구조 출력
    print("\n=== .github 디렉터리 구조 ===")
    list_github_dir(repo, ".github", branch)

    # 2. .py 파일 검색
    print("\n=== repo 내 Python 파일 ===")
    py_files = find_python_files(repo, branch)
    for p, _ in py_files:
        print(f"  {p}")

    if not py_files:
        print("[WARN] Python 파일 없음 -- HARNESS 가 workflow 인라인일 수 있음")
        print("  .github/workflows/harness.yml 을 직접 확인하세요.")
        sys.exit(0)

    # 3. frontmatter 검증 관련 파일 자동 선택
    candidates = [
        (p, sha) for p, sha in py_files
        if "frontmatter" in p or "check" in p or "harness" in p or "lint" in p
    ]
    if not candidates:
        print("[WARN] frontmatter 검증 파일을 자동 감지하지 못했습니다.")
        print("  위 목록에서 파일 경로를 확인 후 스크립트를 수정하세요.")
        sys.exit(1)

    print(f"\n[INFO] 패치 대상: {[p for p,_ in candidates]}")

    changed_any = False
    for path, _ in candidates:
        f = repo.get_contents(path, ref=branch)
        current = base64.b64decode(f.content).decode("utf-8")
        sha = f.sha

        patched = patch_content(current)
        if patched == current:
            print(f"[SKIP] {path} -- 변경 불필요 (이미 패치됐거나 패턴 없음)")
            continue

        print(f"\n=== diff: {path} ===")
        diff = list(difflib.unified_diff(
            current.splitlines(), patched.splitlines(),
            fromfile="before", tofile="after",
            lineterm="", n=2,
        ))
        print("\n".join(diff[:50]))

        confirm = input(f"\n[{path}] my-kms 에 push 하겠습니까? [y/N] ").strip().lower()
        if confirm != "y":
            print("  -> 건너뜀")
            continue

        repo.update_file(
            path=path,
            message="harness: entity/concept 타입 허용 추가 [auto-patch]",
            content=patched.encode("utf-8"),
            sha=sha,
            branch=branch,
        )
        print(f"  -> [OK] {path} 업데이트 완료")
        changed_any = True

    if not changed_any:
        print("\n[INFO] 변경된 파일 없음.")


if __name__ == "__main__":
    main()
