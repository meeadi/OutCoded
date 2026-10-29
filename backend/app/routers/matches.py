"""Code-Off: create a match, look one up, and play it over a WebSocket."""

import asyncio
import secrets
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from app.auth import CurrentUser, decode_token, get_current_user
from app.config import get_settings
from app.db import ensure_profile, get_conn
from app.events import log_event
from app.match_room import RoomError, registry

router = APIRouter(tags=["matches"])

# No 0/o, 1/l/i: codes are easy to read out loud.
CODE_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"
CODE_LENGTH = 6


class MatchCreated(BaseModel):
    code: str


class MatchInfo(BaseModel):
    code: str
    status: str
    host: str | None


def new_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


@router.post("/matches", response_model=MatchCreated, status_code=status.HTTP_201_CREATED)
async def create_match(
    user: CurrentUser = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> MatchCreated:
    await ensure_profile(conn, user.id)
    username = await conn.fetchval("select username from public.profiles where id = $1", user.id)
    if not username:
        raise HTTPException(status.HTTP_409_CONFLICT, "Pick a username first.")

    for _ in range(5):  # a clash between random codes is very unlikely, but possible
        code = new_code()
        try:
            await conn.execute(
                "insert into public.matches (code, host_id) values ($1, $2)", code, user.id
            )
            await log_event(conn, "match_created", user_id=user.id, code=code)
            return MatchCreated(code=code)
        except asyncpg.UniqueViolationError:
            continue
    raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Couldn't create a match, try again.")


@router.get("/matches/{code}", response_model=MatchInfo)
async def match_info(
    code: str,
    _user: CurrentUser = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> MatchInfo:
    row = await conn.fetchrow(
        """
        select m.code, m.status, p.username as host
        from public.matches m join public.profiles p on p.id = m.host_id
        where m.code = $1
        """,
        code,
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No match with that code.")
    return MatchInfo(**dict(row))


@router.websocket("/ws/matches/{code}")
async def match_socket(websocket: WebSocket, code: str) -> None:
    await websocket.accept()

    # Browsers can't put a token in WebSocket headers, so it's the first message instead.
    try:
        first = await asyncio.wait_for(websocket.receive_json(), timeout=10)
        claims = await run_in_threadpool(decode_token, str(first.get("token", "")))
        user_id = UUID(claims["sub"])
    except Exception:
        await _reject(websocket, "Please sign in again.", 4001)
        return

    room = await registry.get(code, websocket.app.state.pool, get_settings().answer_grace_ms)
    if room is None:
        await _reject(websocket, "This match doesn't exist or is already over.", 4004)
        return

    try:
        await room.join(user_id, websocket)
    except RoomError as error:
        await _reject(websocket, str(error), 4003)
        return

    try:
        while True:
            try:
                message = await websocket.receive_json()
            except ValueError:
                continue  # not valid JSON; ignore it
            if isinstance(message, dict) and message.get("type") == "answer":
                await room.handle_answer(user_id, message.get("choice"))
    except WebSocketDisconnect:
        pass
    finally:
        await room.leave(user_id, websocket)


async def _reject(websocket: WebSocket, message: str, code: int) -> None:
    try:
        await websocket.send_json({"type": "error", "message": message})
        await websocket.close(code=code)
    except Exception:
        pass