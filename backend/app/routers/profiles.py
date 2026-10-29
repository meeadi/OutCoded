import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import CurrentUser, get_current_user
from app.db import ensure_profile, get_conn
from app.schemas import Profile, UsernameRequest

router = APIRouter(tags=["profiles"])

# Names nobody gets to pick (compared in lowercase).
RESERVED_USERNAMES = {"admin", "administrator", "moderator", "mod", "root", "system", "support", "outcoded"}

_PROFILE_COLUMNS = "id, username, rating, rating_deviation, created_at"


@router.get("/me", response_model=Profile)
async def me(
    user: CurrentUser = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> Profile:
    await ensure_profile(conn, user.id)
    row = await conn.fetchrow(f"select {_PROFILE_COLUMNS} from public.profiles where id = $1", user.id)
    return Profile(**dict(row))


@router.put("/me/username", response_model=Profile)
async def set_username(
    body: UsernameRequest,
    user: CurrentUser = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> Profile:
    if body.username.lower() in RESERVED_USERNAMES:
        raise HTTPException(status.HTTP_409_CONFLICT, "Nice try. That name is reserved.")

    await ensure_profile(conn, user.id)
    try:
        row = await conn.fetchrow(
            f"update public.profiles set username = $2 where id = $1 returning {_PROFILE_COLUMNS}",
            user.id,
            body.username,
        )
    except asyncpg.UniqueViolationError:
        raise HTTPException(status.HTTP_409_CONFLICT, "That name is taken.") from None
    return Profile(**dict(row))