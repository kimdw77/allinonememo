"""
config.py — 환경변수 로드 및 설정 관리
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Supabase
    SUPABASE_URL: str
    SUPABASE_SERVICE_ROLE_KEY: str
    SUPABASE_ANON_KEY: str

    # Claude API
    ANTHROPIC_API_KEY: str

    # Telegram
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_ALLOWED_USER_ID: str  # 화이트리스트: 나의 Telegram User ID
    TELEGRAM_WEBHOOK_SECRET: str = ""  # Webhook 서명 검증용 시크릿

    # Kakao (선택)
    KAKAO_VERIFY_TOKEN: str = ""

    # TODO(phase4): Google Calendar 연동
    # GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN, GOOGLE_CALENDAR_ID

    # Voyage AI (벡터 검색용 임베딩, Phase 2)
    VOYAGE_API_KEY: str = ""

    # Notion 동기화 (Phase 2)
    NOTION_TOKEN: str = ""
    NOTION_DATABASE_ID: str = ""

    # Google Drive 백업 (서비스 계정 방식)
    GOOGLE_SERVICE_ACCOUNT_JSON: str = ""
    GOOGLE_DRIVE_FOLDER_ID: str = ""

    # Google Calendar (OAuth2 refresh_token 방식)
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REFRESH_TOKEN: str = ""
    GOOGLE_CALENDAR_ID: str = "primary"

    # API 보안: 백엔드 내부 API 호출에 사용하는 시크릿 키
    API_SECRET_KEY: str

    # 환경 (production / development) — ENV 대신 APP_ENV 사용 (Railway ENV 예약어 충돌 방지)
    APP_ENV: str = "production"

    # 허용된 프론트엔드 오리진 (쉼표 구분)
    ALLOWED_ORIGINS: str = "https://allinonememo.vercel.app"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()

# 공통 상수
from datetime import timezone, timedelta
KST = timezone(timedelta(hours=9))
