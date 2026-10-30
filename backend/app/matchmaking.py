"""Ranked matchmaking: pair players with similar ratings.

Players wait in a queue over a WebSocket. Every second the matchmaker looks
for the closest pair whose rating gap is acceptable. The acceptable gap starts
small and widens the longer someone waits, so nobody waits forever.
When a pair is found, it creates a rated match and tells both players its code;
they then connect to that match like any other Code-Off.

Messages (server -> browser):
    queued     you're in the queue
    searching  still looking (sent every second, with the current search range)
    matched    found someone: here's the match code
    error      something went wrong
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from uuid import UUID

import asyncpg
from fastapi import WebSocket

from app.codes import new_code
from app.events import log_event

logger = logging.getLogger("outcoded.matchmaking")

START_RANGE = 100  # rating gap accepted straight away
RANGE_GROWTH_PER_S = 50  # the gap widens this much per second of waiting
ANYONE_AFTER_S = 30  # after this long, any opponent will do


def allowed_gap(waited_s: float) -> float | None:
    """How far apart two ratings may be after waiting this long. None = no limit."""
    if waited_s >= ANYONE_AFTER_S:
        return None
    return START_RANGE + RANGE_GROWTH_PER_S * waited_s


def acceptable(a: "Entry", b: "Entry", now: float) -> bool:
    # The more patient player's range counts: once either is happy, it's a match.
    gaps = [allowed_gap(now - a.joined_at), allowed_gap(now - b.joined_at)]
    if None in gaps:
        return True
    return abs(a.rating - b.rating) <= max(gaps)


@dataclass
class Entry:
    user_id: UUID
    username: str
    rating: float
    socket: WebSocket
    joined_at: float = field(default_factory=time.monotonic)


class Matchmaker:
    def __init__(self):
        self.waiting: dict[UUID, Entry] = {}
        self.lock = asyncio.Lock()
        self.task: asyncio.Task | None = None
        self.pool: asyncpg.Pool | None = None

    async def join(self, entry: Entry, pool: asyncpg.Pool) -> None:
        self.pool = pool
        async with self.lock:
            previous = self.waiting.pop(entry.user_id, None)
            self.waiting[entry.user_id] = entry
            in_queue = len(self.waiting)
        if previous:
            await _close(previous.socket, "Searching in another tab")
        await _send(entry.socket, {"type": "queued", "rating": round(entry.rating), "in_queue": in_queue})

        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self._loop())
        await self._pair_up()

    async def leave(self, user_id: UUID, socket: WebSocket) -> None:
        async with self.lock:
            entry = self.waiting.get(user_id)
            if entry and entry.socket is socket:
                del self.waiting[user_id]

    async def _loop(self) -> None:
        """Re-check the queue every second while anyone is waiting."""
        try:
            while True:
                await asyncio.sleep(1)
                async with self.lock:
                    if not self.waiting:
                        return
                await self._pair_up()
                await self._send_status()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Matchmaker loop crashed")

    async def _pair_up(self) -> None:
        async with self.lock:
            now = time.monotonic()
            longest_waiting_first = sorted(self.waiting.values(), key=lambda e: e.joined_at)
            taken: set[UUID] = set()
            pairs: list[tuple[Entry, Entry]] = []
            for a in longest_waiting_first:
                if a.user_id in taken:
                    continue
                candidates = [
                    b
                    for b in longest_waiting_first
                    if b.user_id != a.user_id and b.user_id not in taken and acceptable(a, b, now)
                ]
                if candidates:
                    b = min(candidates, key=lambda c: abs(c.rating - a.rating))  # closest rating
                    taken |= {a.user_id, b.user_id}
                    pairs.append((a, b))
            for a, b in pairs:
                del self.waiting[a.user_id]
                del self.waiting[b.user_id]

        for a, b in pairs:
            await self._start_match(a, b)

    async def _start_match(self, a: Entry, b: Entry) -> None:
        try:
            async with self.pool.acquire() as conn:
                code = await _create_rated_match(conn, a.user_id, b.user_id)
                await log_event(
                    conn,
                    "match_found",
                    user_id=a.user_id,
                    code=code,
                    opponent=str(b.user_id),
                    rating_gap=round(abs(a.rating - b.rating)),
                    waited_s=round(time.monotonic() - min(a.joined_at, b.joined_at), 1),
                )
        except Exception:
            logger.exception("Couldn't create a ranked match")
            failed = {"type": "error", "message": "Couldn't start the match. Try again."}
            for entry in (a, b):
                await _send(entry.socket, failed)
            return

        for me, them in ((a, b), (b, a)):
            await _send(
                me.socket,
                {
                    "type": "matched",
                    "code": code,
                    "opponent": them.username,
                    "opponent_rating": round(them.rating),
                },
            )

    async def _send_status(self) -> None:
        async with self.lock:
            entries = list(self.waiting.values())
        now = time.monotonic()
        for entry in entries:
            gap = allowed_gap(now - entry.joined_at)
            await _send(
                entry.socket,
                {
                    "type": "searching",
                    "waited_s": int(now - entry.joined_at),
                    "range": None if gap is None else int(gap),
                    "in_queue": len(entries),
                },
            )


async def _create_rated_match(conn: asyncpg.Connection, host_id: UUID, guest_id: UUID) -> str:
    for _ in range(5):
        code = new_code()
        try:
            await conn.execute(
                """
                insert into public.matches (code, host_id, guest_id, rated)
                values ($1, $2, $3, true)
                """,
                code,
                host_id,
                guest_id,
            )
            return code
        except asyncpg.UniqueViolationError:
            continue
    raise RuntimeError("Couldn't find a free match code")


async def _send(socket: WebSocket, message: dict) -> None:
    try:
        await socket.send_json(message)
    except Exception:
        pass


async def _close(socket: WebSocket, reason: str) -> None:
    try:
        await socket.close(code=4000, reason=reason)
    except Exception:
        pass


matchmaker = Matchmaker()