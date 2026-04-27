-- 005_add_related_links.sql
-- notes 테이블에 related_links JSONB 컬럼 추가
-- 신문·기사 이미지 OCR 시 Tavily 웹검색으로 수집한 관련 기사 링크·이미지 저장
-- 구조: {"articles": [{title, url, description, published_date}], "images": [...], "search_query": "..."}

ALTER TABLE notes
  ADD COLUMN IF NOT EXISTS related_links JSONB DEFAULT '{}'::jsonb;

COMMENT ON COLUMN notes.related_links IS
  '신문·기사 이미지 OCR 시 수집된 관련 웹 기사 링크 및 이미지 목록 (Tavily API)';
