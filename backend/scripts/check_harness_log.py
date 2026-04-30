# -*- coding: utf-8 -*-
"""scripts/check_harness_log.py -- 최근 HARNESS 실패 로그 확인"""
import base64, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

token = os.environ.get("GITHUB_TOKEN", "")
if not token:
    print("GITHUB_TOKEN 없음"); sys.exit(1)

from github import Auth, Github
repo = Github(auth=Auth.Token(token)).get_repo("kimdw77/my-kms")

# 1. 최근 workflow run 3개
print("=== 최근 Workflow Runs ===")
for run in list(repo.get_workflow_runs())[:5]:
    print(f"  sha={run.head_sha[:8]}  {run.conclusion or run.status:<10}  {run.head_commit.message[:60]}")

# 2. 가장 최근 실패 run의 job 로그 출력
print("\n=== 최근 실패 Run 상세 ===")
for run in list(repo.get_workflow_runs())[:5]:
    if run.conclusion == "failure":
        print(f"Run ID: {run.id}  sha={run.head_sha[:8]}")
        for job in run.jobs():
            print(f"  Job: {job.name}  status={job.conclusion}")
            for step in job.steps:
                if step.conclusion == "failure":
                    print(f"    FAIL step: {step.name}")
        # 변경된 파일 목록
        commit = repo.get_commit(run.head_sha)
        print(f"  변경 파일:")
        for f in commit.files:
            print(f"    {f.status:8} {f.filename}")
        break

# 3. 현재 my-kms 루트 md 파일 목록
print("\n=== 루트 레벨 .md 파일 ===")
try:
    items = repo.get_contents("", ref="main")
    if not isinstance(items, list): items = [items]
    for item in items:
        if item.name.endswith(".md"):
            content = base64.b64decode(item.content).decode("utf-8")
            has_fm = content.startswith("---")
            print(f"  {item.path}  frontmatter={'YES' if has_fm else 'NO'}")
except Exception as e:
    print(f"  err: {e}")
