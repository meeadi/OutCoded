import asyncpg
from fastapi import APIRouter, Depends

from app.auth import CurrentUser, get_current_user
from app.db import ensure_profile, get_conn
from app.schemas import Profile

router = APIRouter(tags=["profiles"])


@router.get("/me", response_model=Profile)
async def me(
    user: CurrentUser = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> Profile:
    await ensure_profile(conn, user.id)
    row = await conn.fetchrow(
        """
        select id, username, rating, rating_deviation, created_at
        from public.profiles where id = $1
        """,
        user.id,
    )
    return Profile(**dict(row))
