-- 007_sync_status.sql
-- GitHub 동기화 상태 추적 테이블 (Phase 9-1)

CREATE TABLE IF NOT EXISTS sync_status (
  id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  note_id     UUID        REFERENCES notes(id) ON DELETE CASCADE,
  trace_id    TEXT,
  status      TEXT        NOT NULL DEFAULT 'pending'
              CHECK (status IN ('pending', 'synced', 'failed', 'quarantined')),
  github_path TEXT,           -- 예: "personal/notes/2026-04-30-ai-strategy.md"
  github_sha  TEXT,           -- 마지막 commit SHA
  attempts    INT         DEFAULT 0,
  last_error  TEXT,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  synced_at   TIMESTAMPTZ,    -- HARNESS 3-1 지연 측정용
  updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sync_status_pending
  ON sync_status(status) WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_sync_status_note_id
  ON sync_status(note_id);

CREATE INDEX IF NOT EXISTS idx_sync_status_created_at
  ON sync_status(created_at DESC);
