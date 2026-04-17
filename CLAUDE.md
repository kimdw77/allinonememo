# CLAUDE.md — MyVault 프로젝트 전역 지침

> Claude Code가 이 프로젝트 작업 시 항상 참조하는 규칙과 맥락 정의 파일

---

## 프로젝트 정체성

**MyVault**는 개인용 AI 지식저장소다.  
카카오톡/텔레그램으로 보낸 메모·링크를 자동으로 분류·요약하여 나만 접근 가능한 웹 대시보드에 축적한다.

---

## 절대 규칙

1. **보안 최우선**: `.env` 파일 내 값을 절대 하드코딩하지 않는다
2. **토큰 절약**: Claude API 호출은 요약+분류를 단일 요청으로 처리한다
3. **단순하게 시작**: MVP 범위 외 기능은 `# TODO(phase2):` 주석으로 표시만 한다
4. **한국어 주석**: 코드 주석과 커밋 메시지는 한국어로 작성한다
5. **타입 명시**: Python은 타입 힌트, TypeScript는 엄격한 타입을 사용한다

---

## 기술 선택 확정

```
Backend  : FastAPI (Python 3.11+)
Database : Supabase (PostgreSQL 15 + pgvector)
AI       : Anthropic Claude claude-sonnet-4-20250514
Frontend : Next.js 14 (App Router, TypeScript)
Auth     : Supabase Auth (Magic Link)
배포     : Vercel (frontend) + Railway (backend)
```

변경 시 반드시 PLAN_MODE.md 의사결정 로그에 기록할 것.

---

## 코드 스타일

### Python (Backend)
```python
# 파일 상단에 항상 모듈 목적 주석
"""
webhook.py — 카카오톡/텔레그램 메시지 수신 및 저장 처리
"""
from typing import Optional
from pydantic import BaseModel

# 환경변수는 반드시 설정 모듈에서 로드
from config import settings
```

### TypeScript (Frontend)
```typescript
// 컴포넌트 파일: 기능 단위로 분리
// Props는 interface로 명시
interface NoteCardProps {
  id: string;
  summary: string;
  keywords: string[];
  category: string;
  createdAt: string;
}
```

---

## Claude API 호출 표준 패턴

```python
# services/classifier.py 에서만 Claude API 호출
# 다른 모듈은 classifier.py를 import해서 사용

import anthropic
from config import settings

client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

def classify_content(content: str) -> dict:
    """텍스트 내용을 요약·분류·키워드 추출 (단일 API 호출)"""
    
    # 토큰 절약: 2000자 초과 시 잘라서 처리
    truncated = content[:2000] if len(content) > 2000 else content
    
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=300,  # JSON 응답이므로 충분
        messages=[{
            "role": "user",
            "content": CLASSIFY_PROMPT.format(content=truncated)
        }]
    )
    
    # JSON 파싱 및 반환
    import json
    return json.loads(response.content[0].text)

CLASSIFY_PROMPT = """다음 내용을 분석하여 JSON으로만 응답하라. 부가 설명 없이 JSON만.

{content}

{{"summary":"2-3문장 핵심 요약","keywords":["키1","키2","키3"],"category":"카테고리","content_type":"article|video|memo|link|other"}}

카테고리: 비즈니스|기술|무역수출|건강|교육|뉴스|개인메모|기타"""
```

---

## Supabase 클라이언트 표준

```python
# db/client.py — 싱글톤 패턴
from supabase import create_client, Client
from config import settings

_client: Client | None = None

def get_db() -> Client:
    global _client
    if _client is None:
        _client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    return _client
```

---

## 텔레그램 보안 처리

```python
# 나의 Telegram User ID만 처리 (화이트리스트)
def is_allowed_user(user_id: int) -> bool:
    return str(user_id) == settings.TELEGRAM_ALLOWED_USER_ID
```

---

## 에러 처리 원칙

- 외부 API 실패: `try/except` + 로그 기록, 사용자에게 실패 메시지 반환
- Claude API 실패: 분류 없이 raw_content만 저장 (데이터 손실 방지)
- Webhook 수신 실패: 항상 200 반환 (재시도 루프 방지)

---

## 디렉토리별 책임

| 경로 | 역할 |
|------|------|
| `backend/routers/` | HTTP 요청 처리만 (비즈니스 로직 없음) |
| `backend/services/` | 비즈니스 로직 (classifier, fetcher, scheduler) |
| `backend/db/` | DB 쿼리 함수 |
| `frontend/app/` | 페이지 라우팅 |
| `frontend/components/` | 재사용 UI 컴포넌트 |

---

## MVP 완료 기준

- [ ] 텔레그램 메시지 → Supabase 자동 저장
- [ ] Claude로 요약·키워드·카테고리 자동 추출
- [ ] 웹 대시보드 로그인 (Magic Link)
- [ ] 노트 목록 조회 + 키워드 검색
- [ ] 카테고리 필터링

**MVP 완료 후 Phase 2 작업 시작**

---

## 참고 문서

- [Supabase Docs](https://supabase.com/docs)
- [FastAPI Docs](https://fastapi.tiangolo.com)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [Anthropic API](https://docs.anthropic.com)
- [Next.js 14 App Router](https://nextjs.org/docs/app)
