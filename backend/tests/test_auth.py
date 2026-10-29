"""Token checks, using a locally generated key instead of Supabase's."""

import time
import uuid

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app import auth
from app.config import get_settings

SUPABASE_URL = "https://example-project.supabase.co"
PRIVATE_KEY = ec.generate_private_key(ec.SECP256R1())
OTHER_KEY = ec.generate_private_key(ec.SECP256R1())


class FakeJWKSClient:
    """Stands in for PyJWKClient: always hands back our test public key."""

    def get_signing_key_from_jwt(self, token):
        return type("Key", (), {"key": PRIVATE_KEY.public_key()})()


@pytest.fixture(autouse=True)
def fake_supabase(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", SUPABASE_URL)
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused")
    get_settings.cache_clear()
    monkeypatch.setattr(auth, "_jwks_client", FakeJWKSClient())
    yield
    get_settings.cache_clear()


def make_token(key=PRIVATE_KEY, algorithm="ES256", **overrides) -> str:
    claims = {
        "sub": str(uuid.uuid4()),
        "email": "player@example.com",
        "aud": "authenticated",
        "iss": f"{SUPABASE_URL}/auth/v1",
        "exp": int(time.time()) + 3600,
    }
    claims.update(overrides)
    return jwt.encode(claims, key, algorithm=algorithm, headers={"kid": "test"})


def current_user(token: str | None):
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token) if token else None
    return auth.get_current_user(creds)


def test_valid_token_returns_user():
    user_id = str(uuid.uuid4())
    user = current_user(make_token(sub=user_id))
    assert str(user.id) == user_id
    assert user.email == "player@example.com"


@pytest.mark.parametrize(
    "token",
    [
        None,
        "not-a-jwt",
        make_token(exp=int(time.time()) - 10),                   # expired
        make_token(aud="anon"),                                  # wrong audience
        make_token(iss="https://evil.example.com/auth/v1"),      # wrong issuer
        make_token(key=OTHER_KEY),                               # signed by someone else
        make_token(key="x" * 32, algorithm="HS256"),            # symmetric keys refused
    ],
    ids=["missing", "garbage", "expired", "audience", "issuer", "signature", "hs256"],
)
def test_bad_tokens_are_rejected(token):
    with pytest.raises(HTTPException) as exc:
        current_user(token)
    assert exc.value.status_code == 401
