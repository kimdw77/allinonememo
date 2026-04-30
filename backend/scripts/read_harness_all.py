# -*- coding: utf-8 -*-
import base64, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

token = os.environ.get("GITHUB_TOKEN", "")
if not token:
    print("GITHUB_TOKEN 없음"); sys.exit(1)

from github import Auth, Github
repo = Github(auth=Auth.Token(token)).get_repo("kimdw77/my-kms")

for path in [
    ".github/workflows/harness.yml",
    "scripts/harness/check_wikilinks.py",
    "scripts/harness/check_orphan_pages.py",
]:
    try:
        f = repo.get_contents(path, ref="main")
        content = base64.b64decode(f.content).decode("utf-8")
        sep = "=" * 60
        print(f"\n{sep}\nFILE: {path}\n{sep}")
        print(content)
    except Exception as e:
        print(f"ERR {path}: {e}")
