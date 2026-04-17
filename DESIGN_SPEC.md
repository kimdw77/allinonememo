# DESIGN_SPEC.md — MyVault 설계지침서

> 개발자(또는 Claude Code)가 구현 시 참조하는 상세 설계 문서

---

## 1. 시스템 전체 흐름

```
입력 채널
┌─────────────────────────────────────────────┐
│  텔레그램 봇  ──▶  /webhook/telegram        │
│  카카오 채널  ──▶  /webhook/kakao           │
│  수동 입력    ──▶  POST /api/notes          │
│  YouTube URL  ──▶  fetcher 서비스           │
│  RSS/사이트   ──▶  scheduler (매일 09:00)   │
└────────────────────┬────────────────────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │  FastAPI (Railway)     │
        │  1. 원본 텍스트 저장   │
        │  2. Claude API 분류    │
        │  3. Supabase 업데이트  │
        └────────────┬───────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │  Supabase DB           │
        │  - notes 테이블        │
        │  - pgvector 임베딩     │
        └────────────┬───────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │  Next.js (Vercel)      │
        │  - 대시보드            │
        │  - 검색 / 필터         │
        │  - 설정 관리           │
        └────────────────────────┘
```

---

## 2. 백엔드 상세 설계

### 2-1. requirements.txt

```
fastapi==0.110.0
uvicorn[standard]==0.27.0
python-dotenv==1.0.0
supabase==2.3.0
anthropic==0.21.0
httpx==0.26.0
apscheduler==3.10.4
beautifulsoup4==4.12.3
youtube-transcript-api==0.6.2
feedparser==6.0.10
pydantic-settings==2.2.0
```

### 2-2. config.py

```python
"""
config.py — 환경변수 설정 관리
"""
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Supabase
    SUPABASE_URL: str
    SUPABASE_SERVICE_ROLE_KEY: str
    SUPABASE_ANON_KEY: str
    
    # Claude API
    ANTHROPIC_API_KEY: str
    
    # Telegram
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_ALLOWED_USER_ID: str
    
    # Kakao (선택)
    KAKAO_VERIFY_TOKEN: str = ""
    
    # Notion (Phase 2)
    NOTION_TOKEN: str = ""
    NOTION_DATABASE_ID: str = ""
    
    class Config:
        env_file = ".env"

settings = Settings()
```

### 2-3. main.py

```python
"""
main.py — FastAPI 앱 진입점
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import webhook, notes, subscriptions
from services.scheduler import start_scheduler

app = FastAPI(title="MyVault API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-vercel-app.vercel.app"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhook.router, prefix="/webhook", tags=["webhook"])
app.include_router(notes.router, prefix="/api/notes", tags=["notes"])
app.include_router(subscriptions.router, prefix="/api/subscriptions", tags=["subscriptions"])

@app.on_event("startup")
async def startup():
    start_scheduler()  # RSS/사이트 일일 수집 시작

@app.get("/health")
def health():
    return {"status": "ok"}
```

### 2-4. routers/webhook.py

```python
"""
webhook.py — 텔레그램·카카오 메시지 수신
"""
from fastapi import APIRouter, Request, HTTPException
from services.classifier import classify_content
from services.fetcher import fetch_url_content
from db.notes import create_note
from config import settings
import httpx, re

router = APIRouter()

# ── 텔레그램 ──────────────────────────────────
@router.post("/telegram")
async def telegram_webhook(request: Request):
    body = await request.json()
    
    # 메시지 파싱
    message = body.get("message", {})
    user_id = message.get("from", {}).get("id")
    text = message.get("text", "")
    
    # 화이트리스트 보안 체크
    if str(user_id) != settings.TELEGRAM_ALLOWED_USER_ID:
        return {"ok": True}  # 무시하되 200 반환
    
    # 처리
    await process_incoming(text, source="telegram")
    
    # 텔레그램에 확인 메시지 전송
    await send_telegram_reply(message["chat"]["id"], "✅ 저장되었습니다!")
    return {"ok": True}

# ── 카카오 ────────────────────────────────────
@router.post("/kakao")
async def kakao_webhook(request: Request):
    body = await request.json()
    text = body.get("userRequest", {}).get("utterance", "")
    await process_incoming(text, source="kakao")
    # 카카오 응답 형식
    return {
        "version": "2.0",
        "template": {
            "outputs": [{"simpleText": {"text": "✅ 저장되었습니다!"}}]
        }
    }

# ── 공통 처리 ─────────────────────────────────
async def process_incoming(text: str, source: str):
    """수신 텍스트 처리: URL 감지 → 크롤링, 텍스트 → 직접 분류"""
    
    url_pattern = r'https?://\S+'
    urls = re.findall(url_pattern, text)
    
    if urls:
        url = urls[0]
        # URL 내용 크롤링
        content = await fetch_url_content(url)
        raw = content or text
    else:
        raw = text
        url = None
    
    # Claude로 분류 (단일 API 호출)
    classified = classify_content(raw)
    
    # DB 저장
    await create_note({
        "source": source,
        "raw_content": raw,
        "url": url,
        "summary": classified.get("summary", ""),
        "keywords": classified.get("keywords", []),
        "category": classified.get("category", "기타"),
        "metadata": {"content_type": classified.get("content_type", "other")}
    })

async def send_telegram_reply(chat_id: int, text: str):
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(url, json={"chat_id": chat_id, "text": text})
```

### 2-5. services/fetcher.py

```python
"""
fetcher.py — URL/YouTube 내용 추출
"""
from youtube_transcript_api import YouTubeTranscriptApi
from bs4 import BeautifulSoup
import httpx, re

async def fetch_url_content(url: str) -> str:
    """URL 종류 감지 후 적합한 추출 방법 사용"""
    
    if "youtube.com" in url or "youtu.be" in url:
        return await fetch_youtube(url)
    else:
        return await fetch_webpage(url)

async def fetch_youtube(url: str) -> str:
    """YouTube 자막 추출 (토큰 절약: 앞 3000자만)"""
    
    video_id = extract_youtube_id(url)
    if not video_id:
        return ""
    
    try:
        # 한국어 우선, 없으면 영어
        transcript = YouTubeTranscriptApi.get_transcript(
            video_id, languages=["ko", "en"]
        )
        text = " ".join([t["text"] for t in transcript])
        return text[:3000]  # 토큰 절약
    except Exception:
        return ""

async def fetch_webpage(url: str) -> str:
    """웹페이지 본문 추출 (boilerplate 제거)"""
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, follow_redirects=True)
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # 불필요한 태그 제거
        for tag in soup(["script", "style", "nav", "footer", "aside"]):
            tag.decompose()
        
        text = soup.get_text(separator=" ", strip=True)
        return text[:3000]  # 토큰 절약
    except Exception:
        return ""

def extract_youtube_id(url: str) -> str | None:
    patterns = [
        r"youtube\.com/watch\?v=([^&]+)",
        r"youtu\.be/([^?]+)",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None
```

### 2-6. services/scheduler.py

```python
"""
scheduler.py — RSS/구독 사이트 일일 자동 수집
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from db.subscriptions import get_active_subscriptions
from db.notes import create_note
from services.fetcher import fetch_url_content, fetch_youtube
from services.classifier import classify_content
import feedparser

scheduler = AsyncIOScheduler()

def start_scheduler():
    scheduler.add_job(
        daily_collect,
        CronTrigger(hour=9, minute=0),  # 매일 오전 9시
        id="daily_collect",
        replace_existing=True
    )
    scheduler.start()

async def daily_collect():
    """구독 목록 순회 → 새 내용 수집 → 분류 → 저장"""
    
    subs = await get_active_subscriptions()
    
    for sub in subs:
        if sub["type"] == "rss":
            await collect_rss(sub)
        elif sub["type"] == "youtube_channel":
            await collect_youtube_channel(sub)
        elif sub["type"] == "url":
            await collect_url(sub)

async def collect_rss(sub: dict):
    feed = feedparser.parse(sub["target"])
    # 최신 3개 항목만 처리 (토큰 절약)
    for entry in feed.entries[:3]:
        content = entry.get("summary", entry.get("title", ""))
        classified = classify_content(content[:2000])
        await create_note({
            "source": "rss",
            "raw_content": content,
            "url": entry.get("link", ""),
            "summary": classified.get("summary", ""),
            "keywords": classified.get("keywords", []),
            "category": classified.get("category", "뉴스"),
            "metadata": {"feed_title": feed.feed.get("title", "")}
        })
```

---

## 3. 데이터베이스 마이그레이션 SQL

```sql
-- Supabase SQL Editor에서 실행

-- pgvector 확장 활성화
CREATE EXTENSION IF NOT EXISTS vector;

-- 카테고리 테이블
CREATE TABLE categories (
  id    SERIAL PRIMARY KEY,
  name  TEXT UNIQUE NOT NULL,
  color TEXT DEFAULT '#6366f1',
  icon  TEXT DEFAULT '📁'
);

INSERT INTO categories (name, color, icon) VALUES
  ('비즈니스', '#f59e0b', '💼'),
  ('기술', '#3b82f6', '⚙️'),
  ('무역수출', '#10b981', '🌏'),
  ('건강', '#ef4444', '❤️'),
  ('교육', '#8b5cf6', '📚'),
  ('뉴스', '#6b7280', '📰'),
  ('개인메모', '#ec4899', '📝'),
  ('기타', '#9ca3af', '📁');

-- 노트 핵심 테이블
CREATE TABLE notes (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID REFERENCES auth.users DEFAULT auth.uid(),
  source      TEXT NOT NULL,
  raw_content TEXT NOT NULL,
  summary     TEXT DEFAULT '',
  keywords    TEXT[] DEFAULT '{}',
  category    TEXT DEFAULT '기타',
  url         TEXT,
  metadata    JSONB DEFAULT '{}',
  embedding   VECTOR(1536),
  is_starred  BOOLEAN DEFAULT false,
  created_at  TIMESTAMPTZ DEFAULT now(),
  updated_at  TIMESTAMPTZ DEFAULT now()
);

-- RLS (Row Level Security) — 나만 접근
ALTER TABLE notes ENABLE ROW LEVEL SECURITY;
CREATE POLICY "본인 노트만 접근" ON notes
  USING (user_id = auth.uid());

-- 검색 인덱스
CREATE INDEX notes_keywords_idx ON notes USING GIN(keywords);
CREATE INDEX notes_category_idx ON notes(category);
CREATE INDEX notes_created_idx ON notes(created_at DESC);
CREATE INDEX notes_fts_idx ON notes USING GIN(
  to_tsvector('korean', coalesce(summary, '') || ' ' || coalesce(raw_content, ''))
);

-- 구독 테이블
CREATE TABLE subscriptions (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID REFERENCES auth.users DEFAULT auth.uid(),
  type         TEXT NOT NULL,
  target       TEXT NOT NULL,
  label        TEXT DEFAULT '',
  last_fetched TIMESTAMPTZ,
  active       BOOLEAN DEFAULT true,
  created_at   TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "본인 구독만 접근" ON subscriptions
  USING (user_id = auth.uid());
```

---

## 4. 프론트엔드 상세 설계

### 4-1. 페이지 구조

```
/ (대시보드)
  - 최근 노트 카드 그리드
  - 카테고리별 카운트 사이드바
  - 상단 검색바

/search
  - 키워드/카테고리/날짜 필터
  - 검색 결과 목록

/note/[id]
  - 노트 상세 보기
  - 원본 내용 + 요약 + 키워드 태그

/settings
  - 구독 사이트/채널 관리 (추가/삭제)
  - 카테고리 커스터마이즈
```

### 4-2. API 클라이언트 (lib/api.ts)

```typescript
const API_BASE = process.env.NEXT_PUBLIC_API_URL;

export async function getNotes(params?: {
  category?: string;
  keyword?: string;
  limit?: number;
  offset?: number;
}) {
  const query = new URLSearchParams(params as Record<string, string>);
  const res = await fetch(`${API_BASE}/api/notes?${query}`, {
    headers: { Authorization: `Bearer ${getToken()}` }
  });
  return res.json();
}
```

### 4-3. 환경변수 (frontend/.env.local)

```env
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
NEXT_PUBLIC_API_URL=https://your-railway-app.railway.app
```

---

## 5. 배포 설정

### Railway (Backend)
```toml
# railway.toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "uvicorn main:app --host 0.0.0.0 --port $PORT"
```

### Vercel (Frontend)
```json
// vercel.json
{
  "framework": "nextjs",
  "buildCommand": "npm run build",
  "outputDirectory": ".next"
}
```

### 텔레그램 Webhook 등록
```bash
# 배포 후 1회 실행
curl -X POST "https://api.telegram.org/bot{BOT_TOKEN}/setWebhook" \
  -d "url=https://your-railway-app.railway.app/webhook/telegram"
```

---

## 6. Notion 연동 설계 (Phase 2)

```python
# services/notion_sync.py
from notion_client import Client

def sync_note_to_notion(note: dict):
    """Supabase 노트 → Notion 데이터베이스 동기화"""
    client = Client(auth=settings.NOTION_TOKEN)
    
    client.pages.create(
        parent={"database_id": settings.NOTION_DATABASE_ID},
        properties={
            "제목": {"title": [{"text": {"content": note["summary"][:100]}}]},
            "카테고리": {"select": {"name": note["category"]}},
            "키워드": {"multi_select": [{"name": k} for k in note["keywords"]]},
            "출처": {"url": note.get("url", "")},
            "날짜": {"date": {"start": note["created_at"]}},
        },
        children=[{
            "paragraph": {"rich_text": [{"text": {"content": note["raw_content"][:2000]}}]}
        }]
    )
```

---

## 7. 개발 시작 체크리스트

```
환경 준비
  □ Python 3.11+ 설치
  □ Node.js 20+ 설치
  □ Supabase 프로젝트 생성 (supabase.com)
  □ Anthropic API 키 발급
  □ Telegram BotFather에서 봇 생성

백엔드 초기화
  □ cd backend && python -m venv venv && source venv/bin/activate
  □ pip install -r requirements.txt
  □ .env 파일 작성 (.env.example 복사)
  □ Supabase SQL Editor에서 마이그레이션 실행
  □ uvicorn main:app --reload 로컬 테스트

텔레그램 연동 테스트
  □ ngrok으로 로컬 서버 외부 노출
  □ Webhook 등록: curl 명령 실행
  □ 봇에게 메시지 전송 → Supabase에서 저장 확인

프론트엔드 초기화
  □ cd frontend && npm install
  □ .env.local 파일 작성
  □ npm run dev 로컬 확인

배포
  □ GitHub 리포지토리 생성 (private)
  □ Railway에 backend 연결
  □ Vercel에 frontend 연결
  □ 각 플랫폼에 환경변수 설정
  □ 텔레그램 Webhook URL을 Railway URL로 업데이트
```

---

*최종 업데이트: 2026-04 | 작성: KITA 제주지부 AI 인프라 프로젝트*
