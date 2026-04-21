"""
scripts/get_google_token.py — Google OAuth2 refresh_token 1회 발급 스크립트
로컬에서 한 번만 실행하여 refresh_token을 얻고 Railway 환경변수에 저장

실행 방법:
  cd backend
  pip install google-auth-oauthlib
  python scripts/get_google_token.py
"""
import json

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

print("=" * 60)
print("Google Calendar refresh_token 발급")
print("=" * 60)
print()
print("Google Cloud Console에서 다운로드한 client_secrets.json 파일 경로를 입력하세요.")
print("(기본값: client_secrets.json)")
path = input("경로 [client_secrets.json]: ").strip() or "client_secrets.json"

flow = InstalledAppFlow.from_client_secrets_file(path, scopes=SCOPES)
creds = flow.run_local_server(port=0)

print()
print("=" * 60)
print("아래 값을 Railway 환경변수에 추가하세요:")
print("=" * 60)
print(f"GOOGLE_CLIENT_ID     = {creds.client_id}")
print(f"GOOGLE_CLIENT_SECRET = {creds.client_secret}")
print(f"GOOGLE_REFRESH_TOKEN = {creds.refresh_token}")
print()
print("GOOGLE_CALENDAR_ID는 기본 캘린더면 'primary' 그대로 사용하세요.")
