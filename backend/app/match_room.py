"""Live Code-Off matches.

One MatchRoom per match, kept in memory while it's being played. The room is
the referee: it picks the questions, starts every round at the same moment
for both players, scores answers with the server clock, and decides the winner.

Protocol (all messages are JSON with a "type"):

  browser -> server
    {"type": "auth", "token": "..."}           first message, always
    {"type": "answer", "choice": 0-3 | null,   null = my timer ran out
     "away_ms": int | null}                    time the tab was out of focus
    {"type": "forfeit"}                        I'm leaving on purpose

  server -> browser
    waiting               you're in, waiting for an opponent (says whether it's ranked)
    start                 both players are here; first round in a few seconds
    round                 a question (options shuffled per player, no answer)
    opponent_answered     your opponent locked in (but not what they picked)
    round_result          both answers, points, running score, the solution
    opponent_disconnected your opponent's connection dropped; they have reconnect_s to return
    opponent_reconnected  they're back
    round_voided          the round was interrupted, so it doesn't count (score rolled back)
    resume                you reconnected: here's the match so far
    resuming              everyone's here again; the next round starts in a few seconds
    ping                  heartbeat, so a dead connection gets noticed
    match_over            final result
    error                 something went wrong; the socket closes after this

Dropped connections: the match pauses and the player gets RECONNECT_S to come
back. A round that was cut off is thrown away and replayed with a new question
(it's been on screen, so it could have been looked up), but only once per
player per match, so pulling your own cable can't fish for easier questions.
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
FINAL_PAUSE_S = 3  # time to see the last round's result before the winner is announced
NO_SHOW_S = 20  # a ranked match is cancelled if the opponent hasn't connected by then
RECONNECT_S = 30  # how long a dropped player has to come back before forfeiting
RESUME_DELAY_S = 3  # breather once everyone's back, before the next round
HEARTBEAT_S = 10
REPLAYS_PER_PLAYER = 1  # interrupted rounds a player can have replayed per match


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
    connected: bool = True
    replays_left: int = REPLAYS_PER_PLAYER
    forfeit_task: asyncio.Task | None = None


class MatchRoom:
    def __init__(
        self,
        match_id: UUID,
        code: str,
        host_id: UUID,
        guest_id: UUID | None,
        rated: bool,
        pool: asyncpg.Pool,
        grace_ms: int,
    ):
        self.match_id = match_id
        self.code = code
        self.host_id = host_id
        self.guest_id = guest_id  # ranked matches know both players up front
        self.rated = rated
        self.pool = pool
        self.grace_ms = grace_ms
        self.players: dict[UUID, Player] = {}
        self.lock = asyncio.Lock()
        self.round_done = asyncio.Event()
        self.task: asyncio.Task | None = None
        self.no_show_task: asyncio.Task | None = None
        self.heartbeat_task: asyncio.Task | None = None
        self.finished = False
        self.completed = 0  # rounds that counted
        self.used: list[UUID] = []  # questions already shown in this match
        self.in_round = False
        self.round_voided = False
        self.everyone_here = asyncio.Event()  # cleared while someone is disconnected
        self.history: list[dict[UUID, dict | None]] = []  # each counted round's answers

    @property
    def started(self) -> bool:
        return self.task is not None

    # ------------------------------------------------------------------ joining
    async def join(self, user_id: UUID, socket: WebSocket) -> None:
        async with self.lock:
            if self.finished:
                raise RoomError("This match is already over.")
            if self.rated and user_id not in (self.host_id, self.guest_id):
                raise RoomError("This is a ranked match between two other players.")

            async with self.pool.acquire() as conn:
                username = await conn.fetchval(
                    "select username from public.profiles where id = $1", user_id
                )
            if not username:
                raise RoomError("Pick a username before playing.")

            existing = self.players.get(user_id)
            if existing:
                # The newest connection wins: a second tab, or a phone that switched
                # networks before the server noticed the old connection had died.
                if existing.connected:
                    await _safe_close(existing.socket)
                existing.socket = socket
                if self.started:
                    await self._reconnected(existing)
                    return
            elif len(self.players) >= 2:
                raise RoomError("This match is full.")
            else:
                self.players[user_id] = Player(id=user_id, username=username, socket=socket)

            await _send(socket, {"type": "waiting", "you": username, "rated": self.rated})

            if len(self.players) == 2 and not self.started:
                if self.no_show_task:
                    self.no_show_task.cancel()
                self.everyone_here.set()
                self.task = asyncio.create_task(self._run())
            elif self.rated and self.no_show_task is None:
                self.no_show_task = asyncio.create_task(self._cancel_if_no_show())

    async def leave(self, user_id: UUID, socket: WebSocket) -> None:
        """The connection closed. Mid-match that's not a forfeit yet: they get time to come back."""
        async with self.lock:
            player = self.players.get(user_id)
            if player is None or player.socket is not socket or self.finished:
                return  # an old tab closing, or the match already ended
            if not self.started:
                del self.players[user_id]
                if not self.players:
                    registry.forget(self.code)
                return
            if not player.connected:
                return

            player.connected = False
            self.everyone_here.clear()

            voided = False
            if self.in_round and any(p.answer is None for p in self.players.values()):
                if player.replays_left > 0:
                    # Throw this round away; it gets replayed with a new question.
                    player.replays_left -= 1
                    self.round_voided = voided = True
                    self.round_done.set()
                elif player.answer is None:
                    # No replays left: this round counts as a miss for them.
                    await self._score(player, None)
                    if all(p.answer is not None for p in self.players.values()):
                        self.round_done.set()

            opponent = self._opponent(player)
            if opponent and opponent.connected:
                await _send(
                    opponent.socket,
                    {
                        "type": "opponent_disconnected",
                        "reconnect_s": RECONNECT_S,
                        "round_voided": voided,
                    },
                )
            player.forfeit_task = asyncio.create_task(self._forfeit_if_gone(player))

    async def forfeit(self, user_id: UUID) -> None:
        """Left on purpose (e.g. went back to the menu): the other player wins right away."""
        async with self.lock:
            if user_id not in self.players or not self.started or self.finished:
                return
        await self._end_by_forfeit(user_id, reason="left")

    async def _forfeit_if_gone(self, player: Player) -> None:
        await asyncio.sleep(RECONNECT_S)
        async with self.lock:
            if self.finished or player.connected:
                return
        await self._end_by_forfeit(player.id, reason="disconnected")

    async def _end_by_forfeit(self, user_id: UUID, reason: str) -> None:
        if self.task and self.task is not asyncio.current_task():
            self.task.cancel()
        await self._finish(forfeited_by=user_id, reason=reason)

    async def _reconnected(self, player: Player) -> None:
        """Called with the lock held, when a dropped player comes back."""
        was_away = not player.connected
        player.connected = True
        if player.forfeit_task:
            player.forfeit_task.cancel()
            player.forfeit_task = None

        opponent = self._opponent(player)
        await _send(
            player.socket,
            {
                "type": "resume",
                "opponent": opponent.username if opponent else None,
                "rated": self.rated,
                "rounds": ROUNDS,
                "completed": self.completed,
                "score": {"you": player.score, "opponent": opponent.score if opponent else 0},
                "history": [
                    {
                        "round": i + 1,
                        "you": r.get(player.id),
                        "opponent": r.get(opponent.id) if opponent else None,
                    }
                    for i, r in enumerate(self.history)
                ],
                "opponent_connected": bool(opponent and opponent.connected),
            },
        )
        if was_away and opponent and opponent.connected:
            await _send(opponent.socket, {"type": "opponent_reconnected"})
        if all(p.connected for p in self.players.values()):
            self.everyone_here.set()

    async def _cancel_if_no_show(self) -> None:
        """Ranked: if the matched opponent never connects, call the match off."""
        await asyncio.sleep(NO_SHOW_S)
        if self.started or self.finished:
            return
        await self._abandon("Your opponent didn't show up. Match cancelled, no rating change.")

    # ------------------------------------------------------------------ answers
    async def handle_answer(self, user_id: UUID, choice: object, away_ms: object = None) -> None:
        if choice is not None and (not isinstance(choice, int) or isinstance(choice, bool)):
            return  # ignore malformed messages
        if not isinstance(away_ms, int) or isinstance(away_ms, bool) or not 0 <= away_ms <= 600_000:
            away_ms = None  # optional and browser-reported: drop anything odd
        async with self.lock:
            player = self.players.get(user_id)
            if player is None or player.attempt_id is None or player.answer is not None:
                return  # no round running, or already answered
            await self._score(player, choice, away_ms)
            opponent = self._opponent(player)
            if opponent:
                await _send(opponent.socket, {"type": "opponent_answered"})
            if all(p.answer is not None for p in self.players.values()):
                self.round_done.set()

    async def _score(self, player: Player, choice: int | None, away_ms: int | None = None) -> None:
        async with self.pool.acquire() as conn:
            try:
                player.answer = await score_attempt(
                    conn, player.attempt_id, player.id, choice, self.grace_ms, away_ms
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
            self.heartbeat_task = asyncio.create_task(self._heartbeat())
            await asyncio.sleep(START_DELAY_S)

            while self.completed < ROUNDS:
                await self._wait_for_everyone()
                if not await self._play_round(self.completed + 1):
                    continue  # interrupted: replay this round with a new question
                self.completed += 1
                await asyncio.sleep(BETWEEN_ROUNDS_S if self.completed < ROUNDS else FINAL_PAUSE_S)

            await self._finish(forfeited_by=None)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Match %s crashed", self.code)
            await self._abandon("Something broke on our side. Match cancelled.")

    async def _wait_for_everyone(self) -> None:
        """Pause between rounds while someone is reconnecting."""
        while not self.everyone_here.is_set():
            await self.everyone_here.wait()
            for player in self.players.values():
                await _send(player.socket, {"type": "resuming", "in": RESUME_DELAY_S})
            await asyncio.sleep(RESUME_DELAY_S)  # someone may drop again meanwhile: the loop checks

    async def _heartbeat(self) -> None:
        while True:
            await asyncio.sleep(HEARTBEAT_S)
            for player in list(self.players.values()):
                if player.connected:
                    await _send(player.socket, {"type": "ping"})

    async def _play_round(self, number: int) -> bool:
        """Play one round. Returns False if it was interrupted and doesn't count."""
        used = self.used
        async with self.pool.acquire() as conn:
            question = await conn.fetchrow(
                """
                select id, format, category, language, difficulty, prompt, code,
                       options, correct_index, explanation, time_limit_s,
                       rating, rating_deviation
                from public.questions
                where status = 'active' and pool in ('ranked', 'both')
                  and not (id = any($1::uuid[]))
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
                if not self.everyone_here.is_set():
                    return False  # someone dropped just now; this question was never shown
                self.round_done = asyncio.Event()
                self.round_voided = False
                self.in_round = True
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
                        "rating": question["rating"],
                        "rating_deviation": question["rating_deviation"],
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
            self.in_round = False
            if self.round_voided:
                await self._void_round(number)
                return False

            for player in self.players.values():
                if player.answer is None:
                    await self._score(player, None)  # didn't answer in time

            self.history.append({p.id: _public(p.answer) for p in self.players.values()})
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
        return True

    async def _void_round(self, number: int) -> None:
        """Called with the lock held: undo the interrupted round's points."""
        voided_attempts = []
        for player in self.players.values():
            if player.answer is not None:
                player.score -= player.answer.points
            if player.attempt_id is not None:
                voided_attempts.append(str(player.attempt_id))
            player.answer = None
            player.attempt_id = None
        async with self.pool.acquire() as conn:
            await log_event(
                conn,
                "round_voided",
                match_id=str(self.match_id),
                round=number,
                attempts=voided_attempts,
            )
        for player in self.players.values():
            opponent = self._opponent(player)
            if player.connected:
                await _send(
                    player.socket,
                    {
                        "type": "round_voided",
                        "round": number,
                        "score": {"you": player.score, "opponent": opponent.score if opponent else 0},
                    },
                )

    # ------------------------------------------------------------------ ending
    def _stop_background_tasks(self) -> None:
        for task in [self.heartbeat_task, *(p.forfeit_task for p in self.players.values())]:
            if task and task is not asyncio.current_task():
                task.cancel()

    async def _finish(self, forfeited_by: UUID | None, reason: str | None = None) -> None:
        async with self.lock:
            if self.finished:
                return
            self.finished = True
        self._stop_background_tasks()

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
                    "forfeit_reason": reason,  # "left" or "disconnected"
                    "opponent": opponent.username if opponent else None,
                    "score": {"you": player.score, "opponent": opponent.score if opponent else 0},
                    "rated": self.rated,
                    "rating": rating_changes.get(player.id),  # None in casual matches
                },
            )
        registry.forget(self.code)

    async def _abandon(self, message: str) -> None:
        async with self.lock:
            if self.finished:
                return
            self.finished = True
        self._stop_background_tasks()
        async with self.pool.acquire() as conn:
            await conn.execute(
                "update public.matches set status = 'abandoned', finished_at = now() where id = $1",
                self.match_id,
            )
        for player in self.players.values():
            await _send(player.socket, {"type": "error", "message": message})
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
                        select id, host_id, guest_id, rated from public.matches
                        where code = $1 and status = 'waiting'
                        """,
                        code,
                    )
                if match is None:
                    return None
                room = MatchRoom(
                    match["id"], code, match["host_id"], match["guest_id"], match["rated"], pool, grace_ms
                )
                self.rooms[code] = room
            return room

    def forget(self, code: str) -> None:
        self.rooms.pop(code, None)


registry = RoomRegistry()