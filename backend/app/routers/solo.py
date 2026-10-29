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
from app.scoring import AlreadyAnswered, AttemptNotFound, InvalidChoice, score_attempt

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
    try:
        scored = await score_attempt(
            conn, body.attempt_id, user.id, body.choice, get_settings().answer_grace_ms
        )
    except AttemptNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attempt not found") from None
    except AlreadyAnswered:
        raise HTTPException(status.HTTP_409_CONFLICT, "Already answered") from None
    except InvalidChoice:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Choice out of range") from None

    return AnswerResponse(
        correct=scored.correct,
        timed_out=scored.timed_out,
        correct_choice=scored.correct_choice,
        response_ms=scored.response_ms,
        explanation=scored.explanation,
    )
