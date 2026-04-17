-- MyVault Supabase 마이그레이션
-- Supabase SQL Editor에서 실행할 것

-- pgvector 확장 활성화 (의미 검색용, Phase 2)
CREATE EXTENSION IF NOT EXISTS vector;

-- 카테고리 마스터 테이블
CREATE TABLE IF NOT EXISTS categories (
  id    SERIAL PRIMARY KEY,
  name  TEXT UNIQUE NOT NULL,
  color TEXT DEFAULT '#6366f1',
  icon  TEXT DEFAULT '📁'
);

-- 기본 카테고리 삽입
INSERT INTO categories (name, color, icon) VALUES
  ('비즈니스', '#3b82f6', '💼'),
  ('기술',     '#10b981', '💻'),
  ('무역/수출', '#f59e0b', '🚢'),
  ('건강',     '#ef4444', '❤️'),
  ('교육',     '#8b5cf6', '📚'),
  ('뉴스',     '#6b7280', '📰'),
  ('개인메모',  '#ec4899', '📝'),
  ('기타',     '#9ca3af', '📌')
ON CONFLICT (name) DO NOTHING;

-- 메모/노트 핵심 테이블
CREATE TABLE IF NOT EXISTS notes (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source       TEXT NOT NULL,          -- 'kakao' | 'telegram' | 'youtube' | 'rss' | 'manual'
  raw_content  TEXT NOT NULL,          -- 원본 내용
  summary      TEXT,                   -- Claude 요약
  keywords     TEXT[],                 -- 자동 추출 키워드
  category     TEXT,                   -- 자동 분류 카테고리
  content_type TEXT,                   -- 'article' | 'video' | 'memo' | 'link' | 'other'
  url          TEXT,                   -- 링크 (있을 경우)
  metadata     JSONB DEFAULT '{}',     -- 유튜브 제목, RSS 출처 등
  embedding    VECTOR(1536),           -- 벡터 검색용 (Phase 2)
  created_at   TIMESTAMPTZ DEFAULT now(),
  updated_at   TIMESTAMPTZ DEFAULT now()
);

-- 구독 사이트/채널 테이블 (Phase 2)
CREATE TABLE IF NOT EXISTS subscriptions (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  type         TEXT NOT NULL,          -- 'youtube_channel' | 'rss' | 'url'
  target       TEXT NOT NULL,          -- URL 또는 채널ID
  title        TEXT,                   -- 구독 이름
  last_fetched TIMESTAMPTZ,
  active       BOOLEAN DEFAULT true,
  created_at   TIMESTAMPTZ DEFAULT now()
);

-- 검색 성능을 위한 인덱스
CREATE INDEX IF NOT EXISTS idx_notes_created_at ON notes (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notes_category    ON notes (category);
CREATE INDEX IF NOT EXISTS idx_notes_source      ON notes (source);
-- 키워드 배열 검색용 GIN 인덱스
CREATE INDEX IF NOT EXISTS idx_notes_keywords    ON notes USING GIN (keywords);
-- 전문 검색용 인덱스 (raw_content + summary)
CREATE INDEX IF NOT EXISTS idx_notes_fts ON notes
  USING GIN (to_tsvector('simple', coalesce(raw_content,'') || ' ' || coalesce(summary,'')));

-- updated_at 자동 갱신 트리거
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER notes_updated_at
  BEFORE UPDATE ON notes
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- RLS(Row Level Security) 비활성화 — Service Role Key로만 접근하므로 불필요
ALTER TABLE notes         DISABLE ROW LEVEL SECURITY;
ALTER TABLE categories    DISABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions DISABLE ROW LEVEL SECURITY;
