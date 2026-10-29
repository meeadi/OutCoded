from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App settings, read from environment variables or backend/.env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Postgres connection string. On Supabase use the *Session pooler* string
    # (Connect button -> Session pooler), which works on IPv4 networks.
    database_url: str

    # e.g. https://abcdefghijkl.supabase.co (no trailing slash)
    supabase_url: str

    # Only needed by scripts/get_token.py, never by the API itself.
    supabase_publishable_key: str | None = None

    # Comma-separated list of frontend origins allowed to call the API.
    cors_origins: str = "http://localhost:5173"

    # Extra time allowed after a question's limit, to absorb network latency.
    answer_grace_ms: int = 1500

    # Don't serve a player any of the last N questions they've seen.
    recent_question_window: int = 50

    @property
    def jwks_url(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"

    @property
    def jwt_issuer(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/auth/v1"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
