"""
db/client.py — Supabase 클라이언트 싱글톤
"""
from supabase import create_client, Client

from config import settings

_client: Client | None = None


def get_db() -> Client:
    global _client
    if _client is None:
        _client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_ROLE_KEY,
        )
    return _client
