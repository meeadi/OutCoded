"""Code-Off: create a friend match, find a ranked one, and play over WebSockets."""

import asyncio
import logging
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from app.auth import CurrentUser, decode_token, get_current_user
from app.codes import new_code
from app.config import get_settings
from app.db import ensure_profile, get_conn
from app.events import log_event
from app.match_room import RoomError, registry
from app.matchmaking import Entry, matchmaker

router = APIRouter(tags=["matches"])
logger = logging.getLogger("outcoded.matches")


class MatchCreated(BaseModel):
    code: str


class MatchInfo(BaseModel):
    code: str
    status: str
    host: str | None


@router.post("/matches", response_model=MatchCreated, status_code=status.HTTP_201_CREATED)
async def create_match(
    user: CurrentUser = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> MatchCreated:
    """A casual match against a friend, joined through an invite link."""
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


async def _authenticate(websocket: WebSocket) -> UUID | None:
    """Browsers can't put a token in WebSocket headers, so it's the first message instead."""
    try:
        first = await asyncio.wait_for(websocket.receive_json(), timeout=10)
        claims = await run_in_threadpool(decode_token, str(first.get("token", "")))
        return UUID(claims["sub"])
    except Exception:
        await _reject(websocket, "Please sign in again.", 4001)
        return None


@router.websocket("/ws/matches/{code}")
async def match_socket(websocket: WebSocket, code: str) -> None:
    await websocket.accept()
    user_id = await _authenticate(websocket)
    if user_id is None:
        return

    try:
        room = await registry.get(code, websocket.app.state.pool, get_settings().answer_grace_ms)
        if room is None:
            await _reject(websocket, "This match doesn't exist or is already over.", 4004)
            return
        await room.join(user_id, websocket)
    except RoomError as error:
        await _reject(websocket, str(error), 4003)
        return
    except Exception:
        logger.exception("Couldn't join match %s", code)
        await _reject(websocket, "Something went wrong on our side. Try again.", 1011)
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


@router.websocket("/ws/queue")
async def queue_socket(websocket: WebSocket) -> None:
    """Ranked matchmaking. Stay connected while searching; close to stop searching."""
    await websocket.accept()
    user_id = await _authenticate(websocket)
    if user_id is None:
        return

    pool: asyncpg.Pool = websocket.app.state.pool
    async with pool.acquire() as conn:
        profile = await conn.fetchrow(
            "select username, rating from public.profiles where id = $1", user_id
        )
    if profile is None or not profile["username"]:
        await _reject(websocket, "Pick a username before playing.", 4003)
        return

    entry = Entry(user_id=user_id, username=profile["username"], rating=profile["rating"], socket=websocket)
    try:
        await matchmaker.join(entry, pool)
        while True:
            await websocket.receive_text()  # nothing to receive; just wait for the browser to leave
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("Queue connection failed")
    finally:
        await matchmaker.leave(user_id, websocket)


async def _reject(websocket: WebSocket, message: str, code: int) -> None:
    try:
        await websocket.send_json({"type": "error", "message": message})
        await websocket.close(code=code)
    except Exception:
        pass