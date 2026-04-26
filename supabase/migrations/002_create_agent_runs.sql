-- 002_create_agent_runs.sql
-- agent_runs 테이블: 에이전트 파이프라인 실행 기록 (관찰가능성)

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
CREATE INDEX IF NOT EXISTS agent_runs_confirm_idx    ON agent_runs(needs_user_confirmation) WHERE needs_user_confirmation = true;
