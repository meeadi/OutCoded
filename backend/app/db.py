import json
from collections.abc import AsyncIterator

import asyncpg
from fastapi import Request


async def _init_connection(conn: asyncpg.Connection) -> None:
    # Return jsonb columns as Python objects instead of strings.
    await conn.set_type_codec(
        "jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
    )


async def create_pool(database_url: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(
        dsn=database_url,
        min_size=1,
        max_size=5,  # keep this small on Supabase's free tier
        init=_init_connection,
    )


async def ensure_profile(conn: asyncpg.Connection, user_id) -> None:
    """Create the player's profile if missing.

    Normally the signup trigger does this; this covers accounts created
    before the migration ran.
    """
    await conn.execute(
        "insert into public.profiles (id) values ($1) on conflict (id) do nothing", user_id
    )


async def get_conn(request: Request) -> AsyncIterator[asyncpg.Connection]:
    """FastAPI dependency: borrow a connection from the pool for one request."""
    pool: asyncpg.Pool = request.app.state.pool
    async with pool.acquire() as conn:
        yield conn
