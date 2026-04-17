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

    # Kakao (선택)
    KAKAO_VERIFY_TOKEN: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
