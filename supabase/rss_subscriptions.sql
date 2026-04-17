-- RSS 구독 테이블 생성
CREATE TABLE IF NOT EXISTS subscriptions (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  url           text NOT NULL UNIQUE,
  name          text NOT NULL DEFAULT '',
  last_fetched_at timestamptz,
  is_active     boolean NOT NULL DEFAULT true,
  created_at    timestamptz NOT NULL DEFAULT now()
);

-- RLS 활성화
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;

-- 서비스 롤은 모든 작업 허용 (백엔드에서 service_role_key 사용)
CREATE POLICY "service role full access" ON subscriptions
  USING (true)
  WITH CHECK (true);
