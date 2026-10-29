"""Verify Supabase access tokens locally using the project's public keys.

The frontend signs users in with Supabase Auth and sends the resulting
access token as `Authorization: Bearer <token>`. We check its signature
against the public keys Supabase publishes (JWKS), so no secret is needed.
"""

from dataclasses import dataclass
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings

ALLOWED_ALGORITHMS = ("ES256", "RS256")

_bearer = HTTPBearer(auto_error=False)
_jwks_client: jwt.PyJWKClient | None = None


@dataclass(frozen=True)
class CurrentUser:
    id: UUID
    email: str | None


def _get_jwks_client() -> jwt.PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        # Keys are cached in memory; a new key ID triggers a refetch.
        _jwks_client = jwt.PyJWKClient(get_settings().jwks_url, cache_keys=True)
    return _jwks_client


def decode_token(token: str) -> dict:
    """Return the token's claims, or raise jwt.InvalidTokenError."""
    settings = get_settings()
    algorithm = jwt.get_unverified_header(token).get("alg")
    if algorithm not in ALLOWED_ALGORITHMS:
        raise jwt.InvalidAlgorithmError(
            f"Unexpected algorithm {algorithm!r}. Enable asymmetric JWT signing "
            "keys in Supabase (Project Settings -> JWT Keys)."
        )
    signing_key = _get_jwks_client().get_signing_key_from_jwt(token).key
    return jwt.decode(
        token,
        signing_key,
        algorithms=[algorithm],
        audience="authenticated",
        issuer=settings.jwt_issuer,
        options={"require": ["exp", "sub", "aud", "iss"]},
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CurrentUser:
    """FastAPI dependency for endpoints that need a signed-in player.

    It's a plain `def` on purpose: fetching keys uses blocking I/O, and FastAPI
    runs sync dependencies in a thread pool so the event loop stays free.
    """
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing or invalid access token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        claims = decode_token(credentials.credentials)
        return CurrentUser(id=UUID(claims["sub"]), email=claims.get("email"))
    except (jwt.PyJWTError, ValueError, KeyError):
        raise unauthorized from None
