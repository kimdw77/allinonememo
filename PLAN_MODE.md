# PLAN_MODE.md — 개인 지식저장소 (MyVault) 프로젝트

> Claude Code Plan Mode 전용. 이 파일은 구현 전 아키텍처 검토와 의사결정 기록에 사용한다.

---

## 프로젝트 개요

**프로젝트명**: MyVault (개인 AI 지식저장소)  
**목표**: 카카오톡/텔레그램으로 보낸 메모·링크를 자동 분류·요약하여 나만의 검색 가능한 지식 베이스로 축적  
**비유**: 아이폰 메모 + Readwise + Obsidian + KakaoTalk 나에게 보내기  

---

## 핵심 기능 (MVP → 확장)

### Phase 1 — MVP
- [ ] 카카오톡 나에게 보내기 → Webhook 수신
- [ ] 텔레그램 봇 → Webhook 수신
- [ ] 수신된 텍스트/링크 자동 저장 (Supabase)
- [ ] Claude API로 키워드 추출 + 카테고리 자동 분류
- [ ] 비공개 웹 대시보드 (검색·태그 필터)

### Phase 2 — 확장
- [ ] YouTube 링크 → 자막 추출 → 번역/요약 저장
- [ ] 구독 사이트 RSS/URL 자동 수집 및 일일 요약
- [ ] Notion 양방향 동기화
- [ ] Google Drive 백업
- [ ] 텔레그램 -> Gollgel Calendar 일정생성하기 

### Phase 3 — 고도화
- [ ] 벡터 검색 (의미 기반 검색)
- [ ] 연관 노트 자동 링크 (Obsidian-style graph)
- [ ] 모바일 PWA

---

## 기술 스택

| 영역 | 선택 | 이유 |
|------|------|------|
| Backend | **FastAPI** (Python) | 경량, Webhook 처리에 최적 |
| DB | **Supabase** (PostgreSQL) | 무료 tier, REST API 내장 |
| 벡터DB | Supabase pgvector | 추가 인프라 불필요 |
| AI | **Claude claude-sonnet-4-20250514** | 요약·분류·키워드 추출 |
| Frontend | **Next.js 14** (App Router) | SSR, 빠른 검색 |
| 인증 | Supabase Auth (Magic Link) | 패스워드리스, 나만 접근 |
| 배포 | **Vercel** (Frontend) + **Railway** (Backend) | 무료 tier 활용 |
| 스케줄러 | APScheduler (FastAPI 내장) | RSS/사이트 일일 수집 |
| 메시지 수신 | KakaoTalk i-Message API / Telegram Bot API | 공식 채널 |

---

## 아키텍처 다이어그램

```
[카카오톡 나에게 보내기]──┐
[텔레그램 봇]────────────┤
[유튜브/RSS 스케줄러]─────┤──▶ FastAPI Webhook/Scheduler
                          │        │
                          │        ▼
                          │   Claude API (요약·분류·키워드)
                          │        │
                          │        ▼
                          │   Supabase (PostgreSQL + pgvector)
                          │        │
                          └────────▼
                           Next.js Dashboard (나만 접근)
                                   │
                          ┌────────┴────────┐
                     Notion Sync      Google Drive Backup
```

---

## 데이터 모델

```sql
-- 메모/노트 핵심 테이블
CREATE TABLE notes (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID REFERENCES auth.users,
  source      TEXT,        -- 'kakao' | 'telegram' | 'youtube' | 'rss' | 'manual'
  raw_content TEXT,        -- 원본 내용
  summary     TEXT,        -- Claude 요약
  keywords    TEXT[],      -- 자동 추출 키워드
  category    TEXT,        -- 자동 분류 카테고리
  url         TEXT,        -- 링크 (있을 경우)
  metadata    JSONB,       -- 유튜브 제목, RSS 출처 등
  embedding   VECTOR(1536),-- 벡터 검색용
  created_at  TIMESTAMPTZ DEFAULT now(),
  updated_at  TIMESTAMPTZ DEFAULT now()
);

-- 카테고리 마스터
CREATE TABLE categories (
  id    SERIAL PRIMARY KEY,
  name  TEXT UNIQUE,
  color TEXT,
  icon  TEXT
);

-- 구독 사이트/채널
CREATE TABLE subscriptions (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  type         TEXT,  -- 'youtube_channel' | 'rss' | 'url'
  target       TEXT,  -- URL 또는 채널ID
  last_fetched TIMESTAMPTZ,
  active       BOOLEAN DEFAULT true
);
```

---

## API 엔드포인트 설계

```
POST /webhook/kakao          카카오 메시지 수신
POST /webhook/telegram       텔레그램 메시지 수신
POST /api/notes              수동 노트 추가
GET  /api/notes              노트 목록 (검색·필터)
GET  /api/notes/{id}         노트 상세
DELETE /api/notes/{id}       노트 삭제
POST /api/subscriptions      구독 추가
GET  /api/subscriptions      구독 목록
POST /api/search/semantic    의미 기반 검색 (Phase 2)
POST /api/sync/notion        Notion 동기화 트리거
```

---

## Claude API 활용 전략 (토큰 절약)

```python
# 요약·분류를 단일 API 호출로 처리 (토큰 절약 핵심)
CLASSIFY_PROMPT = """
다음 내용을 분석하여 JSON으로만 응답하라. 설명 금지.

{content}

응답형식:
{
  "summary": "2-3문장 핵심 요약",
  "keywords": ["키워드1", "키워드2", "키워드3"],
  "category": "카테고리명",
  "content_type": "article|video|memo|link|other"
}

카테고리는 다음 중 하나: 비즈니스, 기술, 무역/수출, 건강, 교육, 뉴스, 개인메모, 기타
"""
```

**토큰 절약 원칙**:
1. 요약+분류를 1회 API 호출로 통합
2. YouTube: 전체 자막 대신 앞 3000자만 추출
3. 긴 기사: HTML 파싱 후 본문만 추출 (boilerplate 제거)
4. max_tokens: 300으로 제한 (JSON 응답)
5. 캐싱: 동일 URL 재처리 방지

---

## 카카오톡 연동 방법

> 카카오 공식 API는 기업 인증 필요 → **대안 방법** 사용

**권장 방법**: KakaoTalk → IFTTT/Zapier → Webhook
1. IFTTT "KakaoTalk 새 메시지" 트리거 설정
2. Webhook URL로 FastAPI 엔드포인트 연결
3. 또는: 카카오 채널 챗봇 API (무료, 개인 사용 가능)

**대안**: 텔레그램 봇 (설정 용이, 즉시 사용 가능 - 권장)
```
BotFather → 봇 생성 → Token 발급 → Webhook 등록
```

---

## 텔레그램 봇 설정 절차

```bash
# 1. BotFather에서 봇 생성
#    /newbot → 이름 설정 → TOKEN 발급

# 2. Webhook 등록
curl -X POST "https://api.telegram.org/bot{TOKEN}/setWebhook" \
  -d "url=https://your-railway-app.railway.app/webhook/telegram"

# 3. .env에 저장
TELEGRAM_BOT_TOKEN=your_token_here
```

---

## 폴더 구조

```
myvault/
├── PLAN_MODE.md          ← 이 파일
├── CLAUDE.md             ← Claude Code 전역 지침
├── README.md
├── .env.example
│
├── backend/              ← FastAPI
│   ├── main.py
│   ├── routers/
│   │   ├── webhook.py    카카오·텔레그램 수신
│   │   ├── notes.py      CRUD
│   │   └── subscriptions.py
│   ├── services/
│   │   ├── classifier.py  Claude API 분류
│   │   ├── fetcher.py     URL/YouTube 크롤링
│   │   └── scheduler.py   APScheduler 일일 수집
│   ├── models.py
│   └── requirements.txt
│
└── frontend/             ← Next.js 14
    ├── app/
    │   ├── page.tsx       대시보드 홈
    │   ├── search/        검색 페이지
    │   └── settings/      구독 관리
    ├── components/
    │   ├── NoteCard.tsx
    │   ├── SearchBar.tsx
    │   └── TagFilter.tsx
    └── package.json
```

---

## 구현 순서 (Claude Code 작업 지시 순서)

```
1단계: 프로젝트 초기화
  → backend/ FastAPI 보일러플레이트
  → frontend/ Next.js 14 초기화
  → Supabase 테이블 마이그레이션 SQL

2단계: 텔레그램 Webhook (빠른 MVP)
  → routers/webhook.py
  → services/classifier.py (Claude API)
  → Supabase 저장 연동

3단계: 프론트엔드 대시보드
  → Supabase Auth (Magic Link 로그인)
  → 노트 목록 + 검색 + 태그 필터

4단계: YouTube/RSS 수집기
  → services/fetcher.py
  → services/scheduler.py

5단계: Notion/Google Drive 연동
  → Notion API 동기화
  → Google Drive 주간 백업
```

---

## 환경변수 (.env.example)

```env
# Supabase
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_ANON_KEY=

# Claude API
ANTHROPIC_API_KEY=

# Telegram
TELEGRAM_BOT_TOKEN=
TELEGRAM_ALLOWED_USER_ID=   # 나의 Telegram User ID (보안)

# Kakao (선택)
KAKAO_VERIFY_TOKEN=

# Notion (Phase 2)
NOTION_TOKEN=
NOTION_DATABASE_ID=

# Google (Phase 2)
GOOGLE_DRIVE_FOLDER_ID=
```

---

## 보안 원칙

- Supabase Auth로 나만 접근 (Magic Link)
- Telegram: ALLOWED_USER_ID 화이트리스트로 나만 처리
- 모든 API는 Bearer Token 인증
- 환경변수는 절대 Git 커밋 금지 (.gitignore)
- Vercel/Railway 환경변수로만 관리

---

## 의사결정 로그

| 날짜 | 결정 | 이유 |
|------|------|------|
| 2026-04 | 카카오 직접 API 대신 텔레그램 우선 | 카카오는 기업인증 필요, 텔레그램은 즉시 개인 사용 가능 |
| 2026-04 | Railway + Vercel 무료 tier | 개인 프로젝트, 비용 최소화 |
| 2026-04 | Claude 요약+분류 단일 호출 | 토큰 비용 절감 |
| 2026-04 | Supabase pgvector | 별도 벡터DB 없이 의미 검색 가능 |
