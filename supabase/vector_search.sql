-- vector_search.sql — pgvector 의미 검색용 SQL 함수 및 인덱스
-- Supabase SQL Editor에서 실행할 것 (migration.sql 이후)

-- HNSW 인덱스: 코사인 유사도 기반 근사 최근접 이웃 검색
-- 대용량 데이터에서도 빠른 검색 보장 (IVFFlat보다 업서트 친화적)
CREATE INDEX IF NOT EXISTS idx_notes_embedding_hnsw
  ON notes USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

-- match_notes: 쿼리 벡터와 가장 유사한 노트 반환
-- threshold 이상의 유사도만 반환 (노이즈 방지)
CREATE OR REPLACE FUNCTION match_notes(
  query_embedding VECTOR(1536),
  match_count     INT DEFAULT 10,
  threshold       FLOAT DEFAULT 0.5
)
RETURNS TABLE (
  id           UUID,
  source       TEXT,
  raw_content  TEXT,
  summary      TEXT,
  highlights   TEXT[],
  keywords     TEXT[],
  category     TEXT,
  content_type TEXT,
  url          TEXT,
  metadata     JSONB,
  created_at   TIMESTAMPTZ,
  updated_at   TIMESTAMPTZ,
  similarity   FLOAT
)
LANGUAGE sql STABLE
AS $$
  SELECT
    id, source, raw_content, summary, highlights, keywords,
    category, content_type, url, metadata, created_at, updated_at,
    1 - (embedding <=> query_embedding) AS similarity
  FROM notes
  WHERE embedding IS NOT NULL
    AND 1 - (embedding <=> query_embedding) >= threshold
  ORDER BY embedding <=> query_embedding
  LIMIT match_count;
$$;
