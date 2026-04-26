-- 003_create_thoughts.sql
-- thoughts 테이블: ask_user / reject 케이스의 스테이징 레코드
-- status 흐름: pending → processed (정상 저장)
--                      → pending_user_confirm (/yes /no 대기)
--                      → manual_review (Critic reject, 수동 검토 필요)
--                      → rejected (/no 응답 또는 관리자 거부)

create table if not exists thoughts (
  id                     uuid primary key default gen_random_uuid(),
  trace_id               uuid not null,
  raw_input              text not null,
  source                 text default 'telegram',
  status                 text default 'pending'
    check (status in (
      'pending',
      'processed',
      'pending_user_confirm',
      'manual_review',
      'rejected'
    )),
  critic_issues          jsonb,
  critic_suggested_fixes jsonb,
  created_at             timestamptz default now(),
  updated_at             timestamptz default now()
);

create index if not exists idx_thoughts_trace_id  on thoughts(trace_id);
create index if not exists idx_thoughts_status     on thoughts(status);
create index if not exists idx_thoughts_created_at on thoughts(created_at desc);

-- updated_at 자동 갱신 (set_updated_at 함수는 001 migration에서 생성됨)
drop trigger if exists thoughts_updated_at on thoughts;
create trigger thoughts_updated_at
  before update on thoughts
  for each row execute function set_updated_at();
