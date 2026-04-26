-- 004_add_trace_id.sql
-- 모든 파이프라인 테이블에 trace_id 컬럼 추가 (이미 있으면 건너뜀)
-- 한 trace_id로 thoughts→agent_runs→notes→tasks 전체 이력 조회 가능

alter table agent_runs add column if not exists trace_id uuid;
alter table notes      add column if not exists trace_id uuid;
alter table tasks      add column if not exists trace_id uuid;
-- thoughts 테이블은 003 migration에서 trace_id가 이미 정의됨

create index if not exists idx_agent_runs_trace_id on agent_runs(trace_id);
create index if not exists idx_notes_trace_id      on notes(trace_id);
create index if not exists idx_tasks_trace_id      on tasks(trace_id);

-- ── 디버깅용: 한 trace_id의 전체 파이프라인 이력 조회 ──────────────────
-- 아래 쿼리를 Supabase SQL Editor에서 실행할 때 $1 자리에 trace_id를 넣는다.
--
-- select 'thought'   as kind, status,      null         as detail, created_at
--   from thoughts   where trace_id = $1
-- union all
-- select 'agent_run',          final_action, intent       as detail, created_at
--   from agent_runs where trace_id = $1
-- union all
-- select 'note',               null,          summary      as detail, created_at
--   from notes      where trace_id = $1
-- union all
-- select 'task',               status,        title        as detail, created_at
--   from tasks      where trace_id = $1
-- order by created_at;
