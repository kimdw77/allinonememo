# DESIGN_SPEC.md — MyVault 설계지침서

> 개발자(또는 Claude Code)가 구현 시 참조하는 상세 설계 문서  
> 최종 업데이트: 2026-04-26 | Phase 8 (에이전트 운영체계 + 하네스 신뢰성) 완료

---

## 1. 시스템 전체 흐름

```
입력 채널
┌──────────────────────────────────────────────────────┐
│  텔레그램 봇  ──▶  /webhook/telegram                 │
│  수동 입력    ──▶  POST /api/notes                   │
│  YouTube URL  ──▶  fetcher 서비스                    │
│  RSS/사이트   ──▶  scheduler (30분마다)              │
└────────────────────┬─────────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │  AgentPipeline         │  ← Phase 8 핵심
        │  ① Router (의도분류)   │
        │  ② Memo (분석)         │
        │  ③ Task Extractor      │
        │  ④ Critic (품질 게이트)│
        │  ⑤ Save Executor       │
        └────────────┬───────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │  Supabase DB           │
        │  - notes               │
        │  - tasks               │
        │  - agent_runs          │
        │  - thoughts (staging)  │
        │  - pgvector 임베딩     │
        └────────────┬───────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │  Next.js (Vercel)      │
        │  - 대시보드            │
        │  - 검색 / 필터         │
        │  - 그래프 시각화       │
        └────────────────────────┘
```

---

## 2. 배포 현황

| 항목 | 주소 |
|------|------|
| GitHub | kimdw77/allinonememo |
| Backend | allinonememo-production.up.railway.app (Railway, Dockerfile) |
| Frontend | allinonememo.vercel.app (Vercel, Next.js 14) |
| DB | Supabase (PostgreSQL 15 + pgvector + Auth) |
| Telegram Webhook | https://allinonememo-production.up.railway.app/webhook/telegram |

---

## 3. 기술 스택

| 영역 | 선택 |
|------|------|
| Backend | FastAPI (Python 3.11+) |
| DB | Supabase (PostgreSQL + pgvector) |
| AI 분류·요약·비판 | Claude Sonnet 4.6 |
| AI 의도분류·태스크추출 | Claude Haiku 4.5 |
| AI 이미지 OCR | Claude Vision (Sonnet) |
| STT | OpenAI Whisper API |
| Frontend | Next.js 14 (App Router, TypeScript, Tailwind) |
| Auth | 이메일+비밀번호 → myv-access-token httpOnly 쿠키 |
| 배포 | Vercel (FE) + Railway Dockerfile (BE) |

---

## 4. Phase별 완료 현황

### Phase 1 — MVP 핵심 ✅

- 텔레그램 Webhook → Claude 분류 → Supabase 저장
- URL 자동 크롤링 (httpx + BeautifulSoup)
- Claude 요약 / 키워드(5~7개) / 카테고리 / 하이라이트 단일 API 호출
- 노트 CRUD API (목록/조회/생성/수정/삭제)
- 이메일+비밀번호 로그인 (httpOnly 쿠키)
- 카테고리 필터 + 키워드 검색
- 모바일 반응형 UI, 하이라이트 형광펜 표시
- 보안: API_SECRET_KEY, SSRF 방어, 텔레그램 서명 검증, slowapi Rate Limit

### Phase 2 — 고급 기능 ✅

- YouTube 자막 추출 (youtube-transcript-api, 한국어/영어 우선)
- YouTube Shorts 폴백 — 자막 없으면 oEmbed API로 제목·채널명 추출
- RSS 피드 수집기 (30분마다 자동)
- RSS 일일 요약 Digest (매일 08:00 KST 텔레그램 전송)
- 벡터 검색 (Voyage AI voyage-large-2, 1536차원, HNSW 인덱스)
- 카테고리 동적 관리 (DB 기반, Claude 프롬프트에 동적 주입)
- Notion 동기화 (POST /api/sync/notion)
- Google Drive 자동 백업 (매주 일요일 02:00 KST)

### Phase 3 — 시각화 / PWA ✅

- 노트 그래프 시각화 (/graph, 키워드 기반 엣지 연결)
- PWA 설정 (manifest, 오프라인 지원)
- 연관 노트 패널 (벡터 유사도 우선 → 키워드 폴백)

### Phase 4 — 편집 / 재분류 ✅

- 노트 인라인 편집 (PATCH /api/notes/{id})
- 노트 재분류 버튼 (POST /api/notes/{id}/reclassify)

### Phase 5 — 생산성 확장 ✅

- 파일 업로드 (txt/md/pdf/docx, 최대 10개·10MB)
- 통계 대시보드 (/stats)
- 중복 노트 감지 및 병합
- 텔레그램 명령어 강화
- 무한 스크롤, 카테고리 드래그앤드롭

### Phase 6 — 고급 UX / AI 자동화 ✅

- 핀 고정, 다중선택 삭제, 검색 자동완성, 노트 내보내기
- OCR 이미지 업로드 (Claude Vision)
- 주간 AI 인사이트 (매주 월요일 09:00 KST)

### Phase 7 — 미디어·캘린더 연동 ✅

- 텔레그램 사진 → Claude Vision → MyVault 저장 (document 포함)
- 텔레그램 음성 → OpenAI Whisper STT → Claude 분류 → 저장
- `/cal` 명령어 → Claude 자연어 파싱 → Google Calendar 등록 (OAuth2 refresh_token)

### Phase 8 — 에이전트 운영체계 + 하네스 신뢰성 ✅

→ 아래 섹션 5, 6에서 상세 기술

---

## 5. Phase 8: 에이전트 파이프라인 설계

### 5-1. 파이프라인 흐름

```
텔레그램 / 웹 입력
    ↓
① insert_thought (status=pending)   ← thoughts 스테이징 테이블
    ↓
② Router Agent   — Haiku, 의도 분류 (7가지)
    ├─ search / question / command → "🚧 준비 중" 즉시 반환 (thoughts 기록 없음)
    └─ memo / task / project / unknown → 파이프라인 계속
    ↓
③ Memo Agent.analyze()    — 분류·요약 (DB 저장 없음)
    ↓
④ Task Extractor.analyze() — 태스크 추출 (DB 저장 없음)
    ↓
⑤ Critic Agent.review()   — 규칙 기반 품질 게이트 (LLM 호출 없음)
    ├─ "reject"          → thoughts(manual_review) + ❌ 거부 메시지
    ├─ "ask_user"        → thoughts(pending_user_confirm) + ⚠️ 확인 요청
    ├─ "save"            → Save Executor (메모만)
    └─ "save_with_tasks" → Save Executor (메모 + 태스크)
    ↓
⑥ Save Executor
    - save_memo()       필수 (실패 시 None)
    - save_tasks()      실패해도 무시
    - save_agent_run()  실패해도 무시
    ↓
⑦ update_thought (status=processed)
    ↓
텔레그램 응답 + 🔎 trace: {trace_id[:8]}
```

### 5-2. 에이전트 상세

#### Router Agent (`agents/router.py`)
- 의도 분류: `memo | task | project | search | question | command | unknown`
- `classify_intent(content)` — 핵심 공개 API (Haiku, ~100 tokens)
- `run(inp)` — 하위 호환용, 내부에서 `AgentPipeline.run()` 위임
- `search / question / command` → "🚧 준비 중" 즉시 반환 (파이프라인에서 차단)
- `unknown` → Critic까지 전달되어 `reject` 처리

#### Memo Agent (`agents/memo.py`)
- `analyze(inp)` — 분류만, DB 저장 없음 (파이프라인 전용)
- `run(inp)` — 분류 + 저장 (직접 호출용, 하위 호환)
- 반환: `{title, summary, category, keywords, highlights, content_type, importance, raw_text, url}`
- `importance` 추론: 카테고리·키워드 기반 규칙 (high/medium/low, LLM 없음)
  - high: 비즈니스·AI·기술·무역/수출 또는 긴급/마감 키워드
  - low: 개인메모
  - medium: 그 외

#### Task Extractor Agent (`agents/task_extractor.py`)
- `analyze(inp)` — 추출만, DB 저장 없음 (파이프라인 전용)
- `run(inp)` — 추출 + 저장 (직접 호출, `/task` 명령어 전용)
- 반환: `{has_tasks: bool, tasks: [{title, description, priority, project, due_hint}]}`
- Haiku 사용
- "해야 함", "확인", "보내기", "작성", "예약", "준비", "알아보기", "검토" → 태스크 후보

#### Critic Agent (`agents/critic.py`)
- `review(inp, memo_result, task_result, intent_data)` — 규칙 기반 품질 게이트
  | 규칙 | final_action |
  |------|-------------|
  | 빈 내용 또는 len < 5 | reject |
  | intent == unknown | reject |
  | confidence < 0.35 | reject |
  | 모호한 날짜 표현 | ask_user |
  | 위험한 작업 표현 | ask_user |
  | confidence < 0.6 | ask_user |
  | high priority 태스크에 기한 없음 | ask_user |
  | has_tasks == True (문제 없음) | save_with_tasks |
  | 정상 메모 | save |
- `run(inp)` — LLM 기반 상세 비판 (`/critique` 명령어 전용, Sonnet 사용)
  - 강점·약점·개선안·총평·점수(1~10) 반환

#### Save Executor (`executors/save_executor.py`)
- `save_memo(memo_result, inp, trace_id)` — 메모 저장 (필수, 실패 시 None 반환)
- `save_tasks(note_id, tasks, source, trace_id)` — 태스크 저장 (실패해도 무시)
- `save_agent_run(...)` — agent_runs 로깅 (실패해도 무시)
- 모든 함수에 `trace_id` 수신 → 동일 파이프라인 실행을 하나의 trace로 묶음

#### Weekly Report Agent (`agents/weekly_report.py`)
- 지난 7일 노트 + 태스크 통합 주간 보고서
- 완료 태스크 통계, 미완료 기반 다음 주 추천 포함
- `send_weekly_report()` — 매주 월요일 09:00 KST 스케줄러 연동

#### Agent Pipeline (`agents/pipeline.py`)
- 단일 오케스트레이터, 모든 입력의 진입점
- thoughts 스테이징 → Router → Memo → Task → Critic → 분기 → Save → thoughts 갱신
- 각 응답 끝에 `🔎 trace: {trace_id[:8]}` 추가

---

## 6. Phase 8: 하네스 신뢰성 (사·아 요구사항)

### 6-1. trace_id 전파

모든 DB 테이블(thoughts → agent_runs → notes → tasks)이 동일 `trace_id`(UUID v4)를 공유한다.

```python
# utils/trace_id.py
from contextvars import ContextVar
import uuid

_trace_var: ContextVar[str | None] = ContextVar("trace_id", default=None)

def new_trace_id() -> str: return str(uuid.uuid4())
def get_current_trace_id() -> str | None: return _trace_var.get()
def set_trace_id(trace_id: str) -> None: _trace_var.set(trace_id)

@contextmanager
def with_trace(trace_id: str):
    token = _trace_var.set(trace_id)
    try: yield
    finally: _trace_var.reset(token)
```

전체 파이프라인 추적 쿼리:
```sql
SELECT t.created_at, t.status, t.raw_input,
       ar.intent, ar.confidence, ar.final_action,
       n.summary, n.category,
       COUNT(tk.id) AS task_count
FROM thoughts t
LEFT JOIN agent_runs ar ON ar.trace_id = t.trace_id
LEFT JOIN notes n ON n.trace_id = t.trace_id
LEFT JOIN tasks tk ON tk.trace_id = t.trace_id
WHERE t.trace_id = '<UUID>'
GROUP BY t.created_at, t.status, t.raw_input,
         ar.intent, ar.confidence, ar.final_action,
         n.summary, n.category;
```

### 6-2. thoughts 스테이징 테이블

Critic 결과에 따른 status 라이프사이클:

```
pending → processed          (정상 save / save_with_tasks)
pending → manual_review      (Critic reject)
pending → pending_user_confirm (Critic ask_user)
pending_user_confirm → processed  (TODO: /yes 구현 후)
pending_user_confirm → rejected   (TODO: /no 구현 후)
```

### 6-3. 텔레그램 응답 형식

| final_action | 응답 형식 |
|-------------|-----------|
| save / save_with_tasks | `✅ 저장 완료: {title}` (태스크 있으면 `(할 일 N건 추가)`) |
| ask_user | `⚠️ 확인 필요: {issue}\n저장하시겠습니까? /yes /no` |
| reject | `❌ 자동 처리 불가: {issue}\n수동 검토로 표시했습니다.` |
| 미지원 의도 | `🚧 *{라벨}* 기능은 아직 지원 준비 중입니다.` |
| 모든 응답 공통 | `\n🔎 trace: {trace_id[:8]}` |

---

## 7. DB 스키마 (Phase 8 기준 전체)

### notes (기존 + trace_id 추가)
```sql
id, user_id, source, raw_content, summary, keywords[], category,
url, metadata(jsonb), embedding(vector(1536)), is_starred, highlights[],
content_type, importance, pinned, trace_id(uuid), created_at, updated_at
```

### categories
```sql
id(serial), name(unique), color, icon, position, created_at
```

### subscriptions
```sql
id, user_id, type, target, label, last_fetched, active, created_at
```

### tasks (Phase 8 신규)
```sql
id(uuid), note_id(FK→notes), title, description,
status CHECK('todo','in_progress','done'),
priority CHECK('low','medium','high'),
project, source, trace_id(uuid), created_at, updated_at
```

### agent_runs (Phase 8 신규)
```sql
id(uuid), input_text, intent, confidence(numeric 4,3), final_action,
needs_user_confirmation(bool), issues(text[]), note_id(FK→notes),
has_tasks(bool), task_count(int), source, trace_id(uuid), created_at
```

### thoughts (Phase 8 신규)
```sql
id(uuid), trace_id(uuid NOT NULL), raw_input, source,
status CHECK('pending','processed','pending_user_confirm','manual_review','rejected'),
critic_issues(jsonb), critic_suggested_fixes(jsonb),
created_at, updated_at
```

---

## 8. Supabase 마이그레이션

`supabase/migrations/run_all.sql` — 단일 통합 파일 (Phase 8 전체, 2026-04-26 실행 완료)

| 섹션 | 내용 |
|------|------|
| 001 | tasks 테이블 + set_updated_at() 트리거 함수 |
| 002 | agent_runs 테이블 |
| 003 | thoughts 테이블 + 트리거 |
| 004 | agent_runs/notes/tasks에 trace_id 컬럼·인덱스 추가 |

모든 구문은 `IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS`로 멱등성 보장.

---

## 9. Backend 파일 구조

```
backend/
├── main.py                     앱 진입점, 라우터 등록, 스케줄러 시작
├── config.py                   환경변수 (pydantic-settings)
├── Dockerfile                  Railway 배포용
├── requirements.txt
├── agents/
│   ├── base.py                 AgentInput, AgentOutput, BaseAgent
│   ├── pipeline.py             AgentPipeline (오케스트레이터)  ← Phase 8
│   ├── router.py               RouterAgent (의도 분류만)
│   ├── memo.py                 MemoAgent (analyze / run)
│   ├── task_extractor.py       TaskExtractorAgent (analyze / run)
│   ├── critic.py               CriticAgent (review / run)
│   └── weekly_report.py        WeeklyReportAgent
├── executors/
│   └── save_executor.py        SaveExecutor (trace_id 연동)  ← Phase 8
├── db/
│   ├── client.py               Supabase 싱글톤 클라이언트
│   ├── notes.py                notes CRUD
│   ├── tasks.py                tasks CRUD  ← Phase 8
│   ├── agent_runs.py           agent_runs CRUD  ← Phase 8
│   ├── thoughts.py             thoughts CRUD  ← Phase 8
│   ├── categories.py           categories CRUD
│   └── subscriptions.py        subscriptions CRUD
├── routers/
│   ├── webhook.py              텔레그램 Webhook + 명령어 처리
│   ├── notes.py                /api/notes REST API
│   ├── tasks.py                /api/tasks REST API  ← Phase 8
│   └── subscriptions.py        /api/subscriptions REST API
├── services/
│   ├── classifier.py           Claude 단일 API 분류
│   ├── fetcher.py              URL/YouTube 크롤링
│   ├── embedder.py             Voyage AI 벡터 임베딩
│   ├── transcriber.py          OpenAI Whisper STT
│   ├── schedule_detector.py    자연어 → ISO8601 일정 파싱
│   ├── calendar.py             Google Calendar API
│   ├── rss_fetcher.py          RSS 피드 수집
│   ├── digest.py               일일 요약 Digest
│   └── scheduler.py            APScheduler 등록
└── utils/
    └── trace_id.py             trace_id ContextVar 유틸  ← Phase 8
```

---

## 10. 전체 Backend API 엔드포인트

```
노트
GET    /api/notes                       목록 (카테고리/키워드 필터, 페이지네이션)
POST   /api/notes                       생성 (Claude 분류)
POST   /api/notes/upload                파일·이미지 업로드 → 분류 저장
GET    /api/notes/keywords              키워드 빈도 목록 (자동완성용)
GET    /api/notes/export                노트 내보내기 (JSON/Markdown)
GET    /api/notes/graph                 그래프 데이터
GET    /api/notes/search/vector         벡터 유사도 검색
GET    /api/notes/duplicates            중복 노트 감지
POST   /api/notes/merge                 두 노트 병합
POST   /api/notes/bulk-delete           다중 노트 일괄 삭제
POST   /api/notes/bulk-reclassify       기타 카테고리 일괄 재분류
GET    /api/notes/{id}                  단일 조회
PATCH  /api/notes/{id}                  수정
POST   /api/notes/{id}/reclassify       AI 재분류
GET    /api/notes/{id}/related          연관 노트
DELETE /api/notes/{id}                  삭제

카테고리
GET    /api/categories                  목록
POST   /api/categories                  추가
PATCH  /api/categories/{name}           이름·아이콘 변경
DELETE /api/categories/{name}           삭제

태스크 (Phase 8 신규)
GET    /api/tasks                       목록 (status/project 필터)
GET    /api/tasks/stats                 통계
PATCH  /api/tasks/{id}                  수정
DELETE /api/tasks/{id}                  삭제

기타
GET    /api/stats                       대시보드 통계
POST   /api/sync/notion                 Notion 동기화
POST   /api/rss/...                     RSS 관리
POST   /webhook/telegram                텔레그램 수신
GET    /health                          헬스체크
```

---

## 11. 텔레그램 명령어 전체 목록 (Phase 8 최종)

| 명령어 | 에이전트 | 기능 |
|--------|----------|------|
| 일반 텍스트 | AgentPipeline | 자동 분류·저장 (Critic 게이트 통과) |
| `/cal 내용` | 직접 처리 | Google Calendar 일정 등록 |
| `/task 내용` | Task Extractor | 태스크 강제 추출·저장 |
| `/critique 내용` | Critic (LLM) | 비판적 검토·점수·개선안 |
| `/report` | Weekly Report | 주간 보고서 즉시 생성 |
| `/search 키워드` | 직접 처리 | 노트 검색 |
| `/list` | 직접 처리 | 최근 5개 노트 |
| `/today` | 직접 처리 | 오늘 저장된 노트 |
| `/stats` | 직접 처리 | 통계 요약 |
| `/help` | 직접 처리 | 도움말 |

---

## 12. 스케줄러 (APScheduler, Asia/Seoul)

| 주기 | 작업 |
|------|------|
| 30분마다 | RSS 피드 수집 |
| 매일 08:00 | 일일 요약 Digest → 텔레그램 전송 |
| 매주 일요일 02:00 | Google Drive 노트 백업 |
| 매주 월요일 09:00 | 주간 보고서 → 텔레그램 전송 (태스크 통계 포함) |

---

## 13. 테스트

`backend/tests/scenarios.py` — CriticAgent 규칙 로직 단위 검증 (DB·API 불필요)

```bash
python -X utf8 backend/tests/scenarios.py
```

| 시나리오 | 입력 | 예상 결과 |
|---------|------|-----------|
| 1 | "내일 오전 10시 김부장 미팅, 회의록 박과장 송부" | save_with_tasks |
| 2 | "조만간 보고서 보내기" | ask_user |
| 3 | "오늘 환율 알려줘" | 파이프라인 즉시 차단 (question) |
| 4 | "ㅁㄴㅇㄹ" | reject |

---

## 14. Phase 8 추가 기능 (2026-04-26)

### 할일 대시보드 (`/tasks` 페이지)

```
frontend/app/tasks/page.tsx           태스크 목록·상태변경·삭제 UI
frontend/app/api/tasks/route.ts       GET /api/tasks 프록시
frontend/app/api/tasks/[id]/route.ts  PATCH·DELETE 프록시
frontend/app/page.tsx                 헤더 ☑️ → /tasks 링크 추가
```

- 전체 / 할 일 / 진행 중 / 완료 탭 필터 + 요약 카드
- 우선순위 자동 정렬 (🔴높음 → 🟡보통 → 🟢낮음)
- 원형 버튼 클릭 → 상태 순환 (todo → in_progress → done)
- × 버튼 삭제

### Google Calendar 자동 감지 (파이프라인 통합)

`agents/pipeline.py` — save 성공 직후 실행:
- `detect_schedule(inp.content)` — 일정 키워드 사전 필터 → Claude 파싱
- 일정 감지 시 `create_event()` 호출 → 응답에 `📅 캘린더 등록: {title}` 추가
- Google Calendar 환경변수 미설정 or 실패 시 조용히 무시 (파이프라인 중단 없음)

### PWA 아이콘 + iOS 설치

```
frontend/public/apple-touch-icon.png  180×180 iPhone 홈 화면 아이콘
frontend/public/icon-192.png          192×192 manifest 아이콘
frontend/public/icon-512.png          512×512 manifest 아이콘
```

디자인: 인디고(#6366f1) 배경 + 흰색 MV 텍스트  
iOS 설치: Safari → `allinonememo.vercel.app` → 공유(□↑) → 홈 화면에 추가  
iOS 위젯: PWA 불가, Scriptable 앱($6.99)으로 JavaScript 위젯 대체 가능

---

## 15. 추후 과제

| 우선순위 | 과제 |
|----------|------|
| 🔴 | `/yes /no` 명령 핸들러 — thoughts(pending_user_confirm) → 저장 또는 폐기 |
| 🔴 | `/cal` 일정 알림 — 등록된 일정 시간 전 텔레그램 알림 |
| 🔴 | 사진·음성 원본 파일 저장 (Supabase Storage / Google Drive) |
| 🟡 | Router `search` 의도 구현 — 벡터 검색 연동 |
| 🟡 | Router `question` 의도 구현 — RAG 기반 Q&A |
| 🟡 | Critic `ask_user` — 텔레그램 인라인 버튼으로 사용자 확인 요청 |
| 🟡 | Todoist 연동 — Apple Reminders 간접 연동 |
| 🟡 | Scriptable 위젯 스크립트 — iPhone 홈 화면 할일 위젯 |
| 🟡 | 커스텀 도메인 연결 (myvault.kr 등) |
| 🟢 | Router `command` 의도 구현 — 자연어 명령 처리 |
| 🟢 | 카카오톡 연동 |
| 🟢 | 비용 최적화 — 캐싱·배치 처리 전략 |

---

## 16. 주요 의존성 (backend)

```
fastapi, uvicorn, supabase, anthropic, openai, httpx,
beautifulsoup4, apscheduler, feedparser, slowapi,
youtube-transcript-api, voyageai, notion-client,
google-auth, google-api-python-client,
python-multipart, pdfplumber, python-docx,
pydantic-settings
```

## 17. Railway 배포 특이사항

- Railpack ENV 캐싱 버그 → Dockerfile 방식으로 전환
- CMD: `${PORT:-8000}` (Railway 동적 포트 대응)
- `APP_ENV` 사용 (`ENV`는 Railway 예약어 충돌)
