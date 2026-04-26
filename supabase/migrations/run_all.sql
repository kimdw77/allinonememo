-- ============================================================
-- run_all.sql — 모든 Phase 8 migration 통합본
-- Supabase SQL Editor에 이 파일 전체를 붙여넣고 실행하세요.
-- 이미 실행한 테이블/컬럼은 IF NOT EXISTS로 자동 건너뜁니다.
-- ============================================================


-- ────────────────────────────────────────────────────────────
-- 001: tasks 테이블
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tasks (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    note_id     uuid REFERENCES notes(id) ON DELETE SET NULL,
    title       text NOT NULL,
    description text NOT NULL DEFAULT '',
    status      text NOT NULL DEFAULT 'todo'
                    CHECK (status IN ('todo', 'in_progress', 'done')),
    priority    text NOT NULL DEFAULT 'medium'
                    CHECK (priority IN ('low', 'medium', 'high')),
    project     text NOT NULL DEFAULT '',
    source      text NOT NULL DEFAULT '',
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS tasks_status_idx      ON tasks(status);
CREATE INDEX IF NOT EXISTS tasks_project_idx     ON tasks(project) WHERE project <> '';
CREATE INDEX IF NOT EXISTS tasks_created_at_idx  ON tasks(created_at DESC);

-- updated_at 자동 갱신 공용 트리거 함수
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS tasks_updated_at ON tasks;
CREATE TRIGGER tasks_updated_at
    BEFORE UPDATE ON tasks
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ────────────────────────────────────────────────────────────
-- 002: agent_runs 테이블
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_runs (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    input_text              text NOT NULL DEFAULT '',
    intent                  text NOT NULL DEFAULT 'memo',
    confidence              numeric(4,3) NOT NULL DEFAULT 0.5,
    final_action            text NOT NULL DEFAULT 'save',
    needs_user_confirmation boolean NOT NULL DEFAULT false,
    issues                  text[] NOT NULL DEFAULT '{}',
    note_id                 uuid REFERENCES notes(id) ON DELETE SET NULL,
    has_tasks               boolean NOT NULL DEFAULT false,
    task_count              int NOT NULL DEFAULT 0,
    source                  text NOT NULL DEFAULT '',
    created_at              timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS agent_runs_created_at_idx ON agent_runs(created_at DESC);
CREATE INDEX IF NOT EXISTS agent_runs_intent_idx     ON agent_runs(intent);
CREATE INDEX IF NOT EXISTS agent_runs_confirm_idx    ON agent_runs(needs_user_confirmation)
    WHERE needs_user_confirmation = true;


-- ────────────────────────────────────────────────────────────
-- 003: thoughts 테이블
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS thoughts (
    id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id               uuid NOT NULL,
    raw_input              text NOT NULL,
    source                 text DEFAULT 'telegram',
    status                 text DEFAULT 'pending'
        CHECK (status IN (
            'pending',
            'processed',
            'pending_user_confirm',
            'manual_review',
            'rejected'
        )),
    critic_issues          jsonb,
    critic_suggested_fixes jsonb,
    created_at             timestamptz DEFAULT now(),
    updated_at             timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_thoughts_trace_id   ON thoughts(trace_id);
CREATE INDEX IF NOT EXISTS idx_thoughts_status      ON thoughts(status);
CREATE INDEX IF NOT EXISTS idx_thoughts_created_at  ON thoughts(created_at DESC);

DROP TRIGGER IF EXISTS thoughts_updated_at ON thoughts;
CREATE TRIGGER thoughts_updated_at
    BEFORE UPDATE ON thoughts
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ────────────────────────────────────────────────────────────
-- 004: 모든 파이프라인 테이블에 trace_id 컬럼 추가
-- ────────────────────────────────────────────────────────────
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS trace_id uuid;
ALTER TABLE notes      ADD COLUMN IF NOT EXISTS trace_id uuid;
ALTER TABLE tasks      ADD COLUMN IF NOT EXISTS trace_id uuid;
-- thoughts는 003에서 이미 포함됨

CREATE INDEX IF NOT EXISTS idx_agent_runs_trace_id ON agent_runs(trace_id);
CREATE INDEX IF NOT EXISTS idx_notes_trace_id      ON notes(trace_id);
CREATE INDEX IF NOT EXISTS idx_tasks_trace_id      ON tasks(trace_id);
