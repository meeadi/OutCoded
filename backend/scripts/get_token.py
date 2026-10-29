"""Sign in as a test user and print an access token.

Until the frontend exists, use this token in the API docs (http://localhost:8000/docs):
click "Authorize" and paste it in.

Create the test user first: Supabase dashboard -> Authentication -> Users ->
Add user -> Create new user (tick "Auto Confirm User").

Usage (from the backend folder):
    python scripts/get_token.py you@example.com
"""

import getpass
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import get_settings  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Usage: python scripts/get_token.py <email>")
    settings = get_settings()
    if not settings.supabase_publishable_key:
        sys.exit("Set SUPABASE_PUBLISHABLE_KEY in backend/.env first.")

    email = sys.argv[1]
    password = getpass.getpass(f"Password for {email}: ")
    response = httpx.post(
        f"{settings.supabase_url.rstrip('/')}/auth/v1/token",
        params={"grant_type": "password"},
        headers={"apikey": settings.supabase_publishable_key},
        json={"email": email, "password": password},
        timeout=15,
    )
    if response.status_code != 200:
        sys.exit(f"Sign-in failed ({response.status_code}): {response.text}")

    print(response.json()["access_token"])


if __name__ == "__main__":
    main()
