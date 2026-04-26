-- 001_create_tasks.sql
-- tasks 테이블: Task Extractor Agent가 추출한 실행 항목 저장

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

-- updated_at 자동 갱신 트리거
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
