-- RLS 보안 설정
-- Supabase SQL Editor에서 실행할 것

-- notes 테이블 RLS 활성화
ALTER TABLE notes ENABLE ROW LEVEL SECURITY;

-- 인증된 사용자만 모든 작업 허용 (프론트엔드 직접 접근 시)
CREATE POLICY "인증된 사용자 전체 허용" ON notes
  FOR ALL
  TO authenticated
  USING (true)
  WITH CHECK (true);

-- categories 테이블 RLS 활성화 (읽기 전용)
ALTER TABLE categories ENABLE ROW LEVEL SECURITY;

CREATE POLICY "누구나 카테고리 읽기 허용" ON categories
  FOR SELECT
  USING (true);

-- subscriptions 테이블 RLS 활성화
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "인증된 사용자 구독 전체 허용" ON subscriptions
  FOR ALL
  TO authenticated
  USING (true)
  WITH CHECK (true);
