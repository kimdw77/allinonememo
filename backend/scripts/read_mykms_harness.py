# -*- coding: utf-8 -*-
"""scripts/read_mykms_harness.py -- my-kms harness 파일 내용 출력"""
import base64, os, sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

token = os.environ.get("GITHUB_TOKEN", "")
if not token:
    print("GITHUB_TOKEN 없음 -- $env:GITHUB_TOKEN = 'ghp_xxx' 설정 후 재실행")
    sys.exit(1)

from github import Auth, Github
repo = Github(auth=Auth.Token(token)).get_repo("kimdw77/my-kms")

for path in [
    "scripts/harness/check_frontmatter.py",
    "scripts/harness/check_domain_consistency.py",
]:
    try:
        f = repo.get_contents(path, ref="main")
        content = base64.b64decode(f.content).decode("utf-8")
        print(f"\n{'='*60}")
        print(f"FILE: {path}")
        print('='*60)
        print(content)
    except Exception as e:
        print(f"[ERR] {path}: {e}")
