"""Live Code-Off matches.

One MatchRoom per match, kept in memory while it's being played. The room is
the referee: it picks the questions, starts every round at the same moment
for both players, scores answers with the server clock, and decides the winner.

Protocol (all messages are JSON with a "type"):

  browser -> server
    {"type": "auth", "token": "..."}           first message, always
    {"type": "answer", "choice": 0-3 | null}   null = my timer ran out

  server -> browser
    waiting            you're in, waiting for an opponent
    start              both players are here; first round in a few seconds
    round              a question (options shuffled per player, no answer)
    opponent_answered  your opponent locked in (but not what they picked)
    round_result       both answers, points, running score, the solution
    match_over         final result
    error              something went wrong; the socket closes after this
"""

import asyncio
import logging
from dataclasses import dataclass
from uuid import UUID

import asyncpg
from fastapi import WebSocket

from app import game, glicko2
from app.events import log_event
from app.ratings import apply_match_result
from app.scoring import AlreadyAnswered, ScoredAnswer, score_attempt

logger = logging.getLogger("outcoded.match")

ROUNDS = 5
START_DELAY_S = 3
BETWEEN_ROUNDS_S = 5
FINAL_PAUSE_S = 5


class RoomError(Exception):
    """A reason this player can't join, shown to them as-is."""


@dataclass
class Player:
    id: UUID
    username: str
    socket: WebSocket
    score: int = 0
    attempt_id: UUID | None = None
    answer: ScoredAnswer | None = None


class MatchRoom:
    def __init__(self, match_id: UUID, code: str, host_id: UUID, rated: bool, pool: asyncpg.Pool, grace_ms: int):
        self.match_id = match_id
        self.code = code
        self.host_id = host_id
        self.rated = rated
        self.pool = pool
        self.grace_ms = grace_ms
        self.players: dict[UUID, Player] = {}
        self.lock = asyncio.Lock()
        self.round_done = asyncio.Event()
        self.task: asyncio.Task | None = None
        self.finished = False

    @property
    def started(self) -> bool:
        return self.task is not None

    # ------------------------------------------------------------------ joining
    async def join(self, user_id: UUID, socket: WebSocket) -> None:
        async with self.lock:
            if self.finished:
                raise RoomError("This match is already over.")

            async with self.pool.acquire() as conn:
                username = await conn.fetchval(
                    "select username from public.profiles where id = $1", user_id
                )
            if not username:
                raise RoomError("Pick a username before playing.")

            existing = self.players.get(user_id)
            if existing:
                if self.started:
                    raise RoomError("You're already in this match in another tab.")
                # Same player opened the link again before the match began: use the new tab.
                await _safe_close(existing.socket)
                existing.socket = socket
            elif len(self.players) >= 2:
                raise RoomError("This match is full.")
            else:
                self.players[user_id] = Player(id=user_id, username=username, socket=socket)

            await _send(socket, {"type": "waiting", "you": username})

            if len(self.players) == 2 and not self.started:
                self.task = asyncio.create_task(self._run())

    async def leave(self, user_id: UUID, socket: WebSocket) -> None:
        async with self.lock:
            player = self.players.get(user_id)
            if player is None or player.socket is not socket or self.finished:
                return  # an old tab closing, or the match already ended
            if not self.started:
                del self.players[user_id]
                if not self.players:
                    registry.forget(self.code)
                return

        # Left mid-match: the other player wins by forfeit.
        if self.task and self.task is not asyncio.current_task():
            self.task.cancel()
        await self._finish(forfeited_by=user_id)

    # ------------------------------------------------------------------ answers
    async def handle_answer(self, user_id: UUID, choice: object) -> None:
        if choice is not None and (not isinstance(choice, int) or isinstance(choice, bool)):
            return  # ignore malformed messages
        async with self.lock:
            player = self.players.get(user_id)
            if player is None or player.attempt_id is None or player.answer is not None:
                return  # no round running, or already answered
            await self._score(player, choice)
            opponent = self._opponent(player)
            if opponent:
                await _send(opponent.socket, {"type": "opponent_answered"})
            if all(p.answer is not None for p in self.players.values()):
                self.round_done.set()

    async def _score(self, player: Player, choice: int | None) -> None:
        async with self.pool.acquire() as conn:
            try:
                player.answer = await score_attempt(
                    conn, player.attempt_id, player.id, choice, self.grace_ms
                )
            except AlreadyAnswered:
                return
            except Exception:
                # Out-of-range choice or similar: count it as no answer.
                player.answer = await score_attempt(
                    conn, player.attempt_id, player.id, None, self.grace_ms
                )
        player.score += player.answer.points

    # ------------------------------------------------------------------ the game
    async def _run(self) -> None:
        try:
            async with self.pool.acquire() as conn:
                guest = next(p for p in self.players.values() if p.id != self.host_id)
                await conn.execute(
                    """
                    update public.matches
                    set status = 'playing', guest_id = $2, started_at = now()
                    where id = $1
                    """,
                    self.match_id,
                    guest.id,
                )
                await log_event(conn, "match_started", match_id=str(self.match_id))

            for player in self.players.values():
                opponent = self._opponent(player)
                await _send(
                    player.socket,
                    {
                        "type": "start",
                        "opponent": opponent.username if opponent else None,
                        "rounds": ROUNDS,
                        "starts_in": START_DELAY_S,
                    },
                )
            await asyncio.sleep(START_DELAY_S)

            used: list[UUID] = []
            for number in range(1, ROUNDS + 1):
                await self._play_round(number, used)
                await asyncio.sleep(BETWEEN_ROUNDS_S if number < ROUNDS else FINAL_PAUSE_S)

            await self._finish(forfeited_by=None)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Match %s crashed", self.code)
            await self._abandon()

    async def _play_round(self, number: int, used: list[UUID]) -> None:
        async with self.pool.acquire() as conn:
            question = await conn.fetchrow(
                """
                select id, format, category, language, difficulty, prompt, code,
                       options, correct_index, explanation, time_limit_s
                from public.questions
                where status = 'active' and not (id = any($1::uuid[]))
                order by random()
                limit 1
                """,
                used,
            )
            if question is None:
                raise RuntimeError("Not enough active questions for a match")
            used.append(question["id"])

            # Every player gets their own shuffle, so "it's option 2" can't be shouted across.
            orders: dict[UUID, list[int]] = {}
            async with self.lock:
                self.round_done = asyncio.Event()
                for player in self.players.values():
                    orders[player.id] = game.shuffled_order(len(question["options"]))
                    player.answer = None
                    player.attempt_id = await conn.fetchval(
                        """
                        insert into public.attempts (user_id, question_id, mode, option_order, match_id)
                        values ($1, $2, 'match', $3, $4)
                        returning id
                        """,
                        player.id,
                        question["id"],
                        orders[player.id],
                        self.match_id,
                    )
                    await log_event(
                        conn,
                        "question_served",
                        user_id=player.id,
                        attempt_id=player.attempt_id,
                        question_id=question["id"],
                        mode="match",
                        round=number,
                    )

        for player in self.players.values():
            await _send(
                player.socket,
                {
                    "type": "round",
                    "round": number,
                    "of": ROUNDS,
                    "question": {
                        "format": question["format"],
                        "category": question["category"],
                        "language": question["language"],
                        "difficulty": question["difficulty"],
                        "prompt": question["prompt"],
                        "code": question["code"],
                        "options": game.apply_order(question["options"], orders[player.id]),
                        "time_limit_s": question["time_limit_s"],
                    },
                },
            )

        # Wait until both have answered, or the clock (plus grace) runs out.
        deadline = question["time_limit_s"] + self.grace_ms / 1000 + 0.5
        try:
            await asyncio.wait_for(self.round_done.wait(), timeout=deadline)
        except TimeoutError:
            pass

        async with self.lock:
            for player in self.players.values():
                if player.answer is None:
                    await self._score(player, None)  # didn't answer in time

            for player in self.players.values():
                opponent = self._opponent(player)
                mine, theirs = player.answer, opponent.answer if opponent else None
                await _send(
                    player.socket,
                    {
                        "type": "round_result",
                        "round": number,
                        "of": ROUNDS,
                        "you": _public(mine),
                        "opponent": _public(theirs),
                        "correct_choice": mine.correct_choice,
                        "explanation": mine.explanation,
                        "score": {"you": player.score, "opponent": opponent.score if opponent else 0},
                        "next_in": BETWEEN_ROUNDS_S if number < ROUNDS else FINAL_PAUSE_S,
                    },
                )
                player.attempt_id = None

    # ------------------------------------------------------------------ ending
    async def _finish(self, forfeited_by: UUID | None) -> None:
        async with self.lock:
            if self.finished:
                return
            self.finished = True

        host = self.players.get(self.host_id)
        guest = next((p for p in self.players.values() if p.id != self.host_id), None)
        host_score = host.score if host else 0
        guest_score = guest.score if guest else 0

        if forfeited_by is not None:
            winner = next((p.id for p in self.players.values() if p.id != forfeited_by), None)
        elif host_score == guest_score:
            winner = None  # draw
        else:
            winner = self.host_id if host_score > guest_score else (guest.id if guest else None)

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                update public.matches
                set status = 'finished', host_score = $2, guest_score = $3,
                    winner_id = $4, forfeit = $5, finished_at = now()
                where id = $1
                """,
                self.match_id,
                host_score,
                guest_score,
                winner,
                forfeited_by is not None,
            )
            await log_event(
                conn,
                "match_finished",
                user_id=winner,
                match_id=str(self.match_id),
                host_score=host_score,
                guest_score=guest_score,
                forfeit=forfeited_by is not None,
                rated=self.rated,
            )

            # Rated matches move both players' ratings (a forfeit counts as a loss).
            rating_changes: dict[UUID, dict] = {}
            if self.rated and guest is not None:
                if winner is None:
                    host_result = glicko2.DRAW
                else:
                    host_result = glicko2.WIN if winner == self.host_id else glicko2.LOSS
                rating_changes = await apply_match_result(
                    conn, self.match_id, self.host_id, guest.id, host_result
                )

        for player in self.players.values():
            if player.id == forfeited_by:
                continue
            opponent = self._opponent(player)
            result = "draw" if winner is None else ("win" if winner == player.id else "loss")
            await _send(
                player.socket,
                {
                    "type": "match_over",
                    "result": result,
                    "forfeit": forfeited_by is not None,
                    "opponent": opponent.username if opponent else None,
                    "score": {"you": player.score, "opponent": opponent.score if opponent else 0},
                    "rated": self.rated,
                    "rating": rating_changes.get(player.id),
                },
            )
        registry.forget(self.code)

    async def _abandon(self) -> None:
        self.finished = True
        async with self.pool.acquire() as conn:
            await conn.execute(
                "update public.matches set status = 'abandoned', finished_at = now() where id = $1",
                self.match_id,
            )
        for player in self.players.values():
            await _send(player.socket, {"type": "error", "message": "Something broke. Match cancelled."})
        registry.forget(self.code)

    def _opponent(self, player: Player) -> Player | None:
        return next((p for p in self.players.values() if p.id != player.id), None)


def _public(answer: ScoredAnswer | None) -> dict | None:
    if answer is None:
        return None
    return {
        "correct": answer.correct,
        "timed_out": answer.timed_out,
        "response_ms": answer.response_ms,
        "points": answer.points,
    }


async def _send(socket: WebSocket, message: dict) -> None:
    try:
        await socket.send_json(message)
    except Exception:
        pass  # the player disconnected; leave() deals with that


async def _safe_close(socket: WebSocket) -> None:
    try:
        await socket.close(code=4000, reason="Opened in another tab")
    except Exception:
        pass


class RoomRegistry:
    """All matches currently being played on this server."""

    def __init__(self):
        self.rooms: dict[str, MatchRoom] = {}
        self.lock = asyncio.Lock()

    async def get(self, code: str, pool: asyncpg.Pool, grace_ms: int) -> MatchRoom | None:
        async with self.lock:
            room = self.rooms.get(code)
            if room is None:
                async with pool.acquire() as conn:
                    match = await conn.fetchrow(
                        """
                        select id, host_id, rated from public.matches where code = $1 and status = 'waiting'
                        """,
                        code,
                    )
                if match is None:
                    return None
                room = MatchRoom(match["id"], code, match["host_id"], match["rated"], pool, grace_ms)
                self.rooms[code] = room
            return room

    def forget(self, code: str) -> None:
        self.rooms.pop(code, None)


registry = RoomRegistry()