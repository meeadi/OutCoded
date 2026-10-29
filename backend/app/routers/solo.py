"""Solo practice: serve one question, then check the player's answer.

Flow:
  POST /solo/next    -> server picks a question, shuffles its options,
                        records when it was shown, returns it WITHOUT the answer
  POST /solo/answer  -> server measures the response time with its own clock,
                        checks the answer, and only then reveals the solution
"""

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status

from app import game
from app.auth import CurrentUser, get_current_user
from app.config import get_settings
from app.db import ensure_profile, get_conn
from app.events import log_event
from app.schemas import AnswerRequest, AnswerResponse, NextQuestionResponse, ServedQuestion

router = APIRouter(prefix="/solo", tags=["solo"])

_PICK_QUESTION = """
    select id, format, category, language, difficulty, prompt, code, options, time_limit_s
    from public.questions
    where status = 'active'
      and ($3 or id not in (
            select question_id from public.attempts
            where user_id = $1
            order by shown_at desc
            limit $2))
    order by random()
    limit 1
"""


@router.post("/next", response_model=NextQuestionResponse)
async def next_question(
    user: CurrentUser = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> NextQuestionResponse:
    settings = get_settings()
    await ensure_profile(conn, user.id)

    window = settings.recent_question_window
    question = await conn.fetchrow(_PICK_QUESTION, user.id, window, False)
    if question is None:
        # The player has seen everything recently: allow repeats.
        question = await conn.fetchrow(_PICK_QUESTION, user.id, window, True)
    if question is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No active questions yet")

    order = game.shuffled_order(len(question["options"]))
    async with conn.transaction():
        attempt_id = await conn.fetchval(
            """
            insert into public.attempts (user_id, question_id, mode, option_order)
            values ($1, $2, 'solo', $3)
            returning id
            """,
            user.id,
            question["id"],
            order,
        )
        await log_event(
            conn,
            "question_served",
            user_id=user.id,
            attempt_id=attempt_id,
            question_id=question["id"],
            mode="solo",
            format=question["format"],
            difficulty=question["difficulty"],
        )

    return NextQuestionResponse(
        attempt_id=attempt_id,
        question=ServedQuestion(
            format=question["format"],
            category=question["category"],
            language=question["language"],
            difficulty=question["difficulty"],
            prompt=question["prompt"],
            code=question["code"],
            options=game.apply_order(question["options"], order),
            time_limit_s=question["time_limit_s"],
        ),
    )


@router.post("/answer", response_model=AnswerResponse)
async def submit_answer(
    body: AnswerRequest,
    user: CurrentUser = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> AnswerResponse:
    settings = get_settings()
    async with conn.transaction():
        # Lock the attempt row so a double-click can't be scored twice.
        row = await conn.fetchrow(
            """
            select a.question_id, a.option_order, a.answered_at,
                   q.correct_index, q.explanation, q.time_limit_s,
                   (extract(epoch from clock_timestamp() - a.shown_at) * 1000)::int as elapsed_ms
            from public.attempts a
            join public.questions q on q.id = a.question_id
            where a.id = $1 and a.user_id = $2
            for update of a
            """,
            body.attempt_id,
            user.id,
        )
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Attempt not found")
        if row["answered_at"] is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Already answered")

        order = list(row["option_order"])
        chosen = None  # stays None when the player ran out of time without picking
        if body.choice is not None:
            try:
                chosen = game.to_original_index(body.choice, order)
            except ValueError:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY, "Choice out of range"
                ) from None

        response_ms = row["elapsed_ms"]
        # No choice means the player's timer ran out; otherwise check against server time.
        timed_out = chosen is None or game.is_timed_out(
            response_ms, row["time_limit_s"], settings.answer_grace_ms
        )
        correct = not timed_out and chosen == row["correct_index"]

        await conn.execute(
            """
            update public.attempts
            set answered_at = clock_timestamp(), chosen_index = $2, is_correct = $3,
                timed_out = $4, response_ms = $5
            where id = $1
            """,
            body.attempt_id,
            chosen,
            correct,
            timed_out,
            response_ms,
        )
        await log_event(
            conn,
            "answer_submitted",
            user_id=user.id,
            attempt_id=body.attempt_id,
            question_id=row["question_id"],
            mode="solo",
            correct=correct,
            timed_out=timed_out,
            response_ms=response_ms,
        )

    return AnswerResponse(
        correct=correct,
        timed_out=timed_out,
        correct_choice=game.to_displayed_index(row["correct_index"], order),
        response_ms=response_ms,
        explanation=row["explanation"],
    )
