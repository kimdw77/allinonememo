# my-kms — HARNESS 명세

## 개요

LLM이 직접 위키 파일을 편집·재작성하는 시스템에서 **사일런트 실패**(조용한 데이터 오염)를 막는 자동 검증 그물.
모든 검증은 사람이 눈으로 확인하지 않아도 자동 작동해야 한다.

## 검증 계층 (3-Layer)

### Layer 1 — 정적 검증 (Pre-commit / CI)

`.github/workflows/harness.yml`로 GitHub Actions에서 모든 push 시 실행.
**하나라도 실패하면 push reject 또는 PR merge 차단.**

#### 1-1. 프론트매터 스키마 검증

`scripts/harness/check_frontmatter.py`

모든 마크다운 파일이 다음 필드를 가지는지 검증:
- `title` (str, 필수)
- `created` (date, 필수)
- `updated` (date, 필수)
- `type` (enum: entity | concept | note | summary | index)
- `domain` (enum: personal | kita | shared)
- `confidentiality` (enum: public | personal | kita-internal)
- `sources` (list of str, 최소 1개 — index.md 제외)
- `tags` (list of str)

Pydantic 모델로 검증, 위반 시 위반 파일 목록과 사유 출력.

#### 1-2. 위키 링크 무결성

`scripts/harness/check_wikilinks.py`

모든 `[[페이지명]]` 또는 `[[페이지명|alias]]` 링크가 실제 존재하는 마크다운 파일을 가리키는지 검증.
깨진 링크 발견 시 파일·줄번호·링크명 출력.

#### 1-3. 도메인-폴더 일치성

`scripts/harness/check_domain_consistency.py`

다음 규칙 위반 시 실패:
- `domain: kita` 페이지가 `personal/` 또는 `shared/` 하위에 있으면 안 됨
- `domain: personal` 페이지가 `kita/` 또는 `shared/` 하위에 있으면 안 됨
- `confidentiality: kita-internal` 페이지가 `kita/` 외부에 있으면 안 됨

이 검증이 **민감정보 오라우팅을 차단하는 핵심 게이트**.

#### 1-4. 비밀정보 스캔

`gitleaks` 사용 (https://github.com/gitleaks/gitleaks).

탐지 대상:
- API 키 패턴 (sk-, ghp_, AKIA, 등)
- 한국 주민등록번호 패턴 (000000-0000000)
- 신용카드 번호 패턴
- 텔레그램 봇 토큰 패턴

`.gitleaks.toml`에 한국 특화 정규식 추가.

#### 1-5. 마크다운 문법 (경고만)

`markdownlint-cli2` 사용.
실패해도 push는 통과시키되, PR 코멘트로 경고.

### Layer 2 — 의미 검증 (Wiki Compiler 실행 후)

allinonememo 백엔드의 Phase 9-2 Wiki Compiler Agent가 페이지를 컴파일·갱신한 후 실행.
**Critic Agent가 LLM-as-judge로 검증, 실패 시 컴파일 결과를 commit하지 않고 재작성 또는 사용자 검토 큐로 회송.**

#### 2-1. 출처 추적성 (Provenance)

페이지 본문의 모든 사실 주장(claim)이 프론트매터의 `sources` 항목 중 하나로 역추적 가능한지 검증.

검증 프롬프트 (Critic Agent용):
> 다음 페이지의 모든 문장을 검토해서, 각 사실 주장이 sources에 명시된 원본 노트(note_id) 중 어느 것에 근거하는지 매핑하라. 매핑 불가능한 주장이 있으면 "untraceable"로 표시하고 그 주장을 인용해 보고하라.

`untraceable` 주장이 1개라도 있으면 **컴파일 거부 → 재작성 (최대 2회)**.

#### 2-2. 모순 감지

같은 entity·concept 페이지의 새 버전이 기존 버전과 사실 충돌하지 않는지 검증.

검증 절차:
1. 새 버전 컴파일 직전, 기존 페이지 백업 (`.harness/snapshots/`)
2. 컴파일 후, 백업과 새 버전을 LLM에게 비교 요청
3. 다음 충돌 유형 검출:
   - 동일 사실에 대한 모순된 결론
   - 날짜·수치의 변경 (출처 변경 없이 발생)
   - 인물·기관 귀속의 변경

충돌 발견 시 페이지에 `## ⚠️ 모순 표시` 섹션 자동 추가, 사용자 확인 큐로 이동.

#### 2-3. 환각 비율 (Hallucination Rate)

샘플링 방식:
1. 컴파일된 페이지에서 무작위 5개 사실 주장 추출
2. 각 주장이 원본 노트에 실제 등장하는지 LLM에게 검증 요청
3. 환각 비율 = (원본에 없는 주장 수) / 5

임계치: **20% 초과 시 컴파일 거부**.

#### 2-4. 인용 무결성

"X가 Y라고 말했다" 형태의 인용에서:
- X가 사용자 본인이 아닌 제3자인가
- 원본 노트에 X의 발화로 명시되어 있는가
- Y의 표현이 원본과 의미적으로 일치하는가

위반 시 인용 부분 제거 또는 재작성.

#### 2-5. 변경 최소성

새 소스 1건의 인입이 다음 임계치를 초과하면 **사용자 검토 큐로 이동**:
- 단일 페이지의 50% 이상 재작성
- 10개 이상 페이지의 동시 수정
- 단일 commit에서 5개 이상 entity 페이지의 confidentiality 변경

이 임계치는 LLM의 과도한 자유도를 제한하는 안전장치.

### Layer 3 — 운영 검증 (런타임 모니터링)

allinonememo 백엔드와 my-kms Repo에 상시 작동.

#### 3-1. 동기화 지연

```sql
-- Supabase 쿼리
SELECT
  AVG(EXTRACT(EPOCH FROM (synced_at - created_at))) as avg_lag_seconds,
  MAX(EXTRACT(EPOCH FROM (synced_at - created_at))) as max_lag_seconds
FROM sync_status
WHERE created_at > now() - interval '1 hour';
```

- 평균 지연 30초 초과: 텔레그램 알림
- 최대 지연 5분 초과: 텔레그램 즉시 알림 + Sentry 에러

#### 3-2. 동기화 실패율

```sql
SELECT
  COUNT(*) FILTER (WHERE status = 'failed') * 100.0 / COUNT(*) as fail_rate
FROM sync_status
WHERE created_at > now() - interval '24 hours';
```

- 24시간 실패율 5% 초과: 텔레그램 알림 + 실패 항목 목록 첨부

#### 3-3. 고아 페이지 비율

주간 Wiki Linter 실행 시 산출.
- inbound link가 0개인 페이지 / 전체 페이지 수
- 10% 초과 시 텔레그램 알림 (Linter 보고서에 포함)

#### 3-4. Git Repo 크기

`scripts/harness/check_repo_size.sh` (cron 일 1회)
- 일주일 사이 Repo 크기 50MB 이상 증가 시 알림
- 비정상적 증가는 보통 무한 재작성·바이너리 유입 신호

#### 3-5. 민감정보 오라우팅 (가장 중요)

```bash
# 매 commit 후 즉시 실행
grep -r "confidentiality: kita-internal" personal/ shared/ && \
  echo "ALERT: kita-internal data leaked to non-kita folder" && \
  exit 1
```

위반 발견 시:
1. 즉시 텔레그램 알림
2. 위반 파일을 `kita/quarantine/` 폴더로 자동 이동
3. allinonememo 백엔드의 동기화 워커 일시 중지
4. 원인 분석 후 수동 재개

## 디렉터리 구조

```
my-kms/
├── .github/
│   └── workflows/
│       └── harness.yml              ← Layer 1 GitHub Actions
├── .harness/                        ← Harness 작업 디렉터리 (.gitignore)
│   ├── snapshots/                   ← Layer 2 모순 감지용 백업
│   └── reports/                     ← 린트·검증 리포트
├── scripts/
│   └── harness/
│       ├── check_frontmatter.py
│       ├── check_wikilinks.py
│       ├── check_domain_consistency.py
│       ├── check_repo_size.sh
│       └── critic_runner.py         ← Layer 2 LLM-as-judge 호출
├── .gitleaks.toml                   ← 한국 특화 비밀정보 패턴
└── ...
```

## 실패 처리 정책

| Layer | 실패 시 정책 |
|-------|-------------|
| Layer 1 | Hard fail — push/PR 차단 |
| Layer 2 | Soft fail — 컴파일 결과 commit 안 함, 재작성 큐로 이동 (최대 2회), 그래도 실패 시 사용자 검토 큐 |
| Layer 3 | Notify — 알림만, 시스템 정상 작동 유지 (단 3-5는 즉시 격리) |

## 하네스 자체의 검증

하네스 스크립트도 코드이므로 단위 테스트 필요.
`tests/harness/` 디렉터리에 각 스크립트의 정상·이상 케이스 테스트 작성.

```python
# 예: tests/harness/test_check_domain_consistency.py
def test_kita_internal_in_personal_folder_fails():
    """confidentiality: kita-internal 페이지가 personal/ 에 있으면 실패해야 한다"""
    create_test_file("personal/leaked.md", confidentiality="kita-internal")
    result = run_check_domain_consistency()
    assert result.exit_code != 0
    assert "personal/leaked.md" in result.output
```

## 운영 원칙

1. **하네스가 빨개지면 즉시 작업 중단**. 회피·우회 금지.
2. **하네스 스킵 옵션 제공 금지**. `--no-verify` 같은 우회로 두지 않는다.
3. **하네스 자체 변경은 신중하게**. 검증 기준 완화는 별도 PR로 충분한 사유와 함께.
4. **임계치는 측정 후 조정**. 처음엔 보수적으로 설정하고, 운영 데이터로 조정.
5. **사용자에게 보이는 알림은 actionable해야**. "에러 발생"이 아니라 "X 파일의 Y 줄에서 Z 위반, 다음 명령으로 확인" 형태.

## Phase 9 적용 순서

1. **Phase 9-1과 동시**: Layer 1 (정적 검증) + Layer 3 (운영 검증) 우선 적용
2. **Phase 9-2와 동시**: Layer 2 (의미 검증) 적용 — Wiki Compiler Agent와 한 묶음
3. **Phase 9-3 이후**: 임계치 조정·하네스 자체 개선
