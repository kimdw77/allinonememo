# allinonememo — Phase 9 업그레이드 스펙

## Phase 9 목적

기존 MyVault(Phase 1~8)가 보유한 raw data를 **my-kms(LLM-Wiki + Obsidian) 합성층**으로 자동 동기화하는 파이프라인 추가.

## 작업 범위 (4개 트랙)

```
Phase 9-1: GitHub 동기화 워커 추가
Phase 9-2: Wiki Compiler Agent 추가 (멀티에이전트 부록 B 확장)
Phase 9-3: Wiki Linter / Wiki Reporter 추가
Phase 9-4: 텔레그램 명령어 확장 (/wiki, /lint, /report-wiki)
```

이 스펙은 **Phase 9-1만 우선 구현**. Phase 9-2 이후는 Phase 9-1 검증 후 별도 스펙으로 진행.

---

## Phase 9-1: GitHub 동기화 워커

### 목표
MyVault에서 노트가 저장되는 즉시(또는 N분 배치로) my-kms Repo의 `personal/notes/` 또는 `kita/notes/` 폴더에 마크다운 파일로 push.

### 트리거
`agents/pipeline.py`의 `⑦ 저장` 블록에서 `executor.save_memo()` 성공 직후.

**결정 근거**: `save_executor.py`는 순수 동기 함수이므로 `asyncio.create_task()` 호출을 위한
async context가 없다. `pipeline.py`는 `webhook.py`의 `async def _run_router_agent()`에서
호출되므로 이 시점에 이벤트 루프가 보장된다.

구현 방식:
- `asyncio.get_running_loop().create_task(enqueue_sync(note, trace_id))` — fire-and-forget
- `task.add_done_callback(_log_sync_task_result)` — 예외 silently 소멸 방지
- `save_memo()` 반환값이 `None`(저장 실패)이면 트리거하지 않음
- 이벤트 루프 없는 환경(테스트·RouterAgent 동기 래퍼)에서는 `RuntimeError` catch 후 건너뜀
- trace_id: 인자 명시적 전달 + ContextVar 자동 전파로 이중 보장

### 동작 흐름

```
[기존 5-에이전트 파이프라인]
  Router → Memo → Task → Critic → Save Executor (Supabase 저장 성공)
                                       │
                                       ▼
                            [신규] GitHub Sync Worker
                                       │
                                       ├─ 1. note → markdown 변환 (프론트매터 + 본문)
                                       ├─ 2. 폴더 결정 (personal vs kita)
                                       ├─ 3. 파일명 생성 (YYYY-MM-DD-slug.md)
                                       ├─ 4. PyGithub로 my-kms Repo에 push
                                       └─ 5. log.md에 ingest 항목 추가
```

### 신규 파일

```
backend/
├── services/
│   └── github_sync.py          ← 신규: GitHub push 로직
├── workers/                     ← 신규 디렉터리
│   └── sync_worker.py          ← 비동기 동기화 워커
├── templates/                   ← 신규 디렉터리
│   ├── note_template.md.j2     ← 노트 → 마크다운 Jinja2 템플릿
│   └── log_entry.md.j2         ← log.md 추가 항목 템플릿
└── utils/
    └── slug.py                 ← 한글 제목 → slug 변환
```

### 환경변수 (Railway에 추가)

```
GITHUB_TOKEN=ghp_xxx                    # Fine-grained PAT
GITHUB_REPO=kimdw77/my-kms
GITHUB_BRANCH=main
WIKI_DEFAULT_DOMAIN=personal           # 분류 안 된 노트의 기본 폴더
SYNC_MODE=realtime                     # realtime | batch
```

### 폴더 결정 로직

```python
def determine_domain(note: Note) -> str:
    """
    노트의 도메인을 personal / kita 중 하나로 결정.
    """
    # 1. 명시적 태그 우선
    if "kita" in note.keywords or "회원사" in note.keywords:
        return "kita"
    if "personal" in note.keywords or "개인" in note.keywords:
        return "personal"

    # 2. 카테고리 기반 (MyVault 카테고리 활용)
    kita_categories = {"무역정책", "회원사", "수출입동향", "교육"}
    if note.category in kita_categories:
        return "kita"

    # 3. 기본값
    return os.getenv("WIKI_DEFAULT_DOMAIN", "personal")
```

### 마크다운 변환 템플릿 (note_template.md.j2)

```jinja
---
title: "{{ note.title }}"
created: {{ note.created_at | date('YYYY-MM-DD') }}
updated: {{ note.updated_at | date('YYYY-MM-DD') }}
type: note
domain: {{ domain }}
confidentiality: {{ 'kita-internal' if domain == 'kita' else 'personal' }}
sources:
  - "note_id:{{ note.id }}"
{% if note.source %}  - "{{ note.source }}"{% endif %}
trace_ids:
  - "{{ note.trace_id }}"
tags: [{{ note.keywords | join(', ') }}]
category: {{ note.category }}
---

# {{ note.title }}

## 요약
{{ note.summary }}

## 본문
{{ note.raw_content }}

{% if note.related_links %}
## 관련 링크
{% for link in note.related_links %}
- [{{ link.title }}]({{ link.url }})
{% endfor %}
{% endif %}

{% if note.file_url %}
## 첨부
- [원본 파일]({{ note.file_url }})
{% endif %}

---
*MyVault에서 자동 동기화됨 ({{ now }})*
```

### log.md 업데이트 로직

매번 push 전에 `log.md`를 read → append → push (단일 commit으로 처리).

```python
def append_log(repo, entry_type: str, source: str, target: str):
    """
    log.md에 한 줄 추가.
    형식: ## [YYYY-MM-DD] {entry_type} | {source} → {target}
    """
    today = datetime.now(KST).strftime("%Y-%m-%d")
    line = f"## [{today}] {entry_type} | {source} → {target}\n"
    # GitHub API로 log.md read → 마지막 줄에 append → write
```

### 충돌 처리

- **동시 push 충돌**: GitHub API의 SHA 기반 낙관적 락 사용. 실패 시 최대 3회 재시도(지수 백오프).
- **사용자 직접 수정 충돌**: 동기화 워커는 **personal/notes/**, **kita/notes/** 폴더만 write. 다른 폴더는 절대 수정하지 않음.
- **재시도 큐**: 3회 실패 시 `sync_failed` 테이블에 기록 → 텔레그램으로 알림.

### Supabase 신규 테이블

```sql
-- 동기화 상태 추적
create table sync_status (
  id uuid primary key default gen_random_uuid(),
  note_id uuid references notes(id) on delete cascade,
  trace_id text,
  status text check (status in ('pending', 'synced', 'failed')),
  github_path text,           -- 예: "personal/notes/2026-04-30-AI전략.md"
  github_sha text,            -- 마지막 commit SHA
  attempts int default 0,
  last_error text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create index idx_sync_status_pending on sync_status(status) where status = 'pending';
```

### 신규 라우터 (테스트·관리용)

```
backend/routers/sync.py
- POST /api/sync/note/{note_id}     수동 재동기화
- GET  /api/sync/status              동기화 상태 조회
- GET  /api/sync/failed              실패 항목 목록
- POST /api/sync/retry/{sync_id}     실패 항목 재시도
```

### 검증 항목

- [ ] 새 텔레그램 노트 작성 → 5초 이내 my-kms Repo에 파일 생성 확인
- [ ] 한글 제목이 slug로 정상 변환 (예: "AI 에이전트 2트랙" → "ai-agent-2-track")
- [ ] 동일 note_id로 재저장 시 기존 파일 업데이트 (중복 생성 X)
- [ ] kita 카테고리 노트가 `kita/notes/`로, 그 외는 `personal/notes/`로 라우팅
- [ ] log.md에 ingest 항목 자동 추가
- [ ] sync_status 테이블에 상태 기록
- [ ] 실패 시 재시도 후 텔레그램 알림

### 의존성 추가 (requirements.txt)

```
PyGithub>=2.1.1
Jinja2>=3.1.2
python-slugify>=8.0.1
```

---

## Phase 9-2 ~ 9-4 (참고용 — 별도 스펙 예정)

### Phase 9-2: Wiki Compiler Agent

5-에이전트 파이프라인 끝에 추가. 새 노트가 push되면 관련 위키 페이지(entities/concepts)를 식별·업데이트.

```
입력: 새로 push된 노트 N개
출력: 영향받은 위키 페이지의 update PR 또는 직접 commit
모델: Claude Sonnet (Track A) → 추후 Qwen 로컬 (Track B)
```

### Phase 9-3: Wiki Linter / Wiki Reporter

- **Linter**: 매주 일요일 새벽, 모순·고아 페이지·낡은 주장 점검 → 텔레그램 알림
- **Reporter**: 매주 월요일 09:00, 누적 위키 합성한 주간 리포트 (기존 주간 보고서 대체)

### Phase 9-4: 텔레그램 명령어 확장

- `/wiki <주제>` — my-kms에서 관련 페이지 검색·요약
- `/lint` — 즉시 린트 실행
- `/report-wiki` — 즉시 위키 기반 리포트 생성

---

## 작업 순서

1. **로컬 개발**: 신규 파일 작성, 템플릿 작성, 라우터 작성
2. **Supabase 마이그레이션**: `migrations/007_sync_status.sql` 추가, Supabase Studio에서 적용
3. **환경변수 등록**: Railway 대시보드에서 `GITHUB_TOKEN` 등 추가
4. **로컬 테스트**: `pytest tests/test_github_sync.py` 통과
5. **Railway 배포**: `git push origin main` (Railway 자동 배포)
6. **운영 검증**: 텔레그램으로 테스트 노트 5건 작성 → my-kms Repo 확인

---

## 변경 이력

| 날짜 | 변경 내용 | 사유 |
|------|----------|------|
| 2026-04-30 | 파일명 슬러그를 `allow_unicode=True` 로 변경 (한글 보존, max_length=40) | LLM-Wiki 패턴에서 한글 파일명이 위키 링크·검색·합성에 필수; 음차 슬러그는 Obsidian 탐색 불가 |
