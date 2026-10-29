"""Score one answer. Shared by solo practice and Code-Off matches,
so both modes always follow exactly the same rules."""

from dataclasses import dataclass
from uuid import UUID

import asyncpg

from app import game
from app.events import log_event


class AttemptNotFound(Exception):
    pass


class AlreadyAnswered(Exception):
    pass


class InvalidChoice(Exception):
    pass


@dataclass(frozen=True)
class ScoredAnswer:
    correct: bool
    timed_out: bool
    response_ms: int
    points: int  # 0 in solo; match points in a Code-Off
    correct_choice: int  # position of the right option as this player saw it
    explanation: str


async def score_attempt(
    conn: asyncpg.Connection,
    attempt_id: UUID,
    user_id: UUID,
    choice: int | None,
    grace_ms: int,
) -> ScoredAnswer:
    """`choice` is the position the player clicked, or None if their time ran out."""
    async with conn.transaction():
        # Lock the attempt row so a double-click can't be scored twice.
        row = await conn.fetchrow(
            """
            select a.question_id, a.option_order, a.answered_at, a.mode,
                   q.correct_index, q.explanation, q.time_limit_s,
                   (extract(epoch from clock_timestamp() - a.shown_at) * 1000)::int as elapsed_ms
            from public.attempts a
            join public.questions q on q.id = a.question_id
            where a.id = $1 and a.user_id = $2
            for update of a
            """,
            attempt_id,
            user_id,
        )
        if row is None:
            raise AttemptNotFound
        if row["answered_at"] is not None:
            raise AlreadyAnswered

        order = list(row["option_order"])
        chosen = None  # stays None when the player ran out of time without picking
        if choice is not None:
            try:
                chosen = game.to_original_index(choice, order)
            except ValueError:
                raise InvalidChoice from None

        response_ms = row["elapsed_ms"]
        # No choice means the player's timer ran out; otherwise check against server time.
        timed_out = chosen is None or game.is_timed_out(response_ms, row["time_limit_s"], grace_ms)
        correct = not timed_out and chosen == row["correct_index"]
        points = (
            game.match_points(correct, response_ms, row["time_limit_s"])
            if row["mode"] == "match"
            else 0
        )

        await conn.execute(
            """
            update public.attempts
            set answered_at = clock_timestamp(), chosen_index = $2, is_correct = $3,
                timed_out = $4, response_ms = $5, points = $6
            where id = $1
            """,
            attempt_id,
            chosen,
            correct,
            timed_out,
            response_ms,
            points,
        )
        await log_event(
            conn,
            "answer_submitted",
            user_id=user_id,
            attempt_id=attempt_id,
            question_id=row["question_id"],
            mode=row["mode"],
            correct=correct,
            timed_out=timed_out,
            response_ms=response_ms,
            points=points,
        )

    return ScoredAnswer(
        correct=correct,
        timed_out=timed_out,
        response_ms=response_ms,
        points=points,
        correct_choice=game.to_displayed_index(row["correct_index"], order),
        explanation=row["explanation"],
    )