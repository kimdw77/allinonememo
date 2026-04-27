-- 006_add_file_url.sql
-- notes 테이블에 원본 파일 URL 컬럼 추가
ALTER TABLE notes ADD COLUMN IF NOT EXISTS file_url TEXT;

-- Supabase Storage media 버킷 생성 (public)
INSERT INTO storage.buckets (id, name, public)
VALUES ('media', 'media', true)
ON CONFLICT (id) DO NOTHING;

-- Storage RLS 정책 (service_role 키로 업로드, 누구나 읽기)
CREATE POLICY IF NOT EXISTS "Public media read"
  ON storage.objects FOR SELECT
  USING (bucket_id = 'media');

CREATE POLICY IF NOT EXISTS "Service role media insert"
  ON storage.objects FOR INSERT
  WITH CHECK (bucket_id = 'media');

CREATE POLICY IF NOT EXISTS "Service role media delete"
  ON storage.objects FOR DELETE
  USING (bucket_id = 'media');
