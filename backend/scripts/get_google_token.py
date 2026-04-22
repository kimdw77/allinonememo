"""
scripts/get_google_token.py — Google OAuth2 refresh_token 1회 발급 스크립트
로컬에서 한 번만 실행하여 refresh_token을 얻고 .env에 저장

실행 방법:
  cd backend
  pip install google-auth-oauthlib
  python scripts/get_google_token.py
"""
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

print("=" * 60)
print("Google Calendar refresh_token 발급")
print("=" * 60)
print()

client_id = input("클라이언트 ID: ").strip()
client_secret = input("클라이언트 보안 비밀번호: ").strip()

client_config = {
    "installed": {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uris": ["http://localhost", "urn:ietf:wg:oauth:2.0:oob"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}

flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)
creds = flow.run_local_server(port=0)

print()
print("=" * 60)
print(".env 파일에 아래 값을 추가하세요:")
print("=" * 60)
print(f"GOOGLE_CLIENT_ID={creds.client_id}")
print(f"GOOGLE_CLIENT_SECRET={creds.client_secret}")
print(f"GOOGLE_REFRESH_TOKEN={creds.refresh_token}")
print("GOOGLE_CALENDAR_ID=primary")
