"""Practice: serve one question, then check the player's answer.

Flow:
  GET  /solo/topics  -> every topic with question counts per difficulty preset
  POST /solo/next    -> server picks a question matching the player's choices,
                        shuffles its options, records when it was shown, and
                        returns it WITHOUT the answer
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
from app.practice import PRESETS, preset_range
from app.schemas import (
    AnswerRequest,
    AnswerResponse,
    NextQuestionResponse,
    PracticeRequest,
    PracticeTopic,
    PracticeTopicsResponse,
    ServedQuestion,
)
from app.scoring import AlreadyAnswered, AttemptNotFound, InvalidChoice, score_attempt

router = APIRouter(prefix="/solo", tags=["practice"])

# Questions this player most recently got wrong (and hasn't fixed since).
_MISTAKES = """
    select question_id from (
        select distinct on (question_id) question_id, is_correct
        from public.attempts
        where user_id = $1 and answered_at is not null
        order by question_id, answered_at desc
    ) latest
    where not is_correct
"""

_PICK_QUESTION = f"""
    select id, format, category, language, difficulty, prompt, code, options, time_limit_s,
           rating, rating_deviation
    from public.questions
    where status = 'active'
      and (cardinality($3::text[]) = 0 or category = any($3::text[]))
      -- review: only your unfixed mistakes (from any pool); otherwise the practice pool
      and (case when $7 then id in ({_MISTAKES}) else pool in ('practice', 'both') end)
      and ($4::float8 is null or rating >= $4)
      and ($5::float8 is null or rating <= $5)
      and ($6 or id not in (
            select question_id from public.attempts
            where user_id = $1
            order by shown_at desc
            limit $2))
    order by random()
    limit 1
"""


@router.get("/topics", response_model=PracticeTopicsResponse)
async def practice_topics(
    user: CurrentUser = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> PracticeTopicsResponse:
    """Every topic, with how many questions each difficulty preset has for this player."""
    await ensure_profile(conn, user.id)
    rating = await conn.fetchval("select rating from public.profiles where id = $1", user.id)
    ranges = {name: preset_range(name, rating) for name in PRESETS}

    rows = await conn.fetch(
        f"""
        select t.id, t.name,
               count(q.id) as all_count,
               count(q.id) filter (where q.rating <= $2) as chill,
               count(q.id) filter (where q.rating between $3 and $4) as level,
               count(q.id) filter (where q.rating >= $5) as pain,
               (select count(*) from public.questions m
                where m.category = t.id and m.status = 'active'
                  and m.id in ({_MISTAKES})) as mistakes
        from public.topics t
        left join public.questions q
          on q.category = t.id and q.status = 'active' and q.pool in ('practice', 'both')
        group by t.id, t.name, t.sort_order
        order by t.sort_order
        """,
        user.id,
        ranges["chill"][1],
        ranges["level"][0],
        ranges["level"][1],
        ranges["pain"][0],
    )
    return PracticeTopicsResponse(
        rating=rating,
        topics=[
            PracticeTopic(
                id=r["id"],
                name=r["name"],
                counts={
                    "chill": r["chill"],
                    "level": r["level"],
                    "pain": r["pain"],
                    "all": r["all_count"],
                },
                mistakes=r["mistakes"],
            )
            for r in rows
        ],
    )


@router.post("/next", response_model=NextQuestionResponse)
async def next_question(
    body: PracticeRequest | None = None,
    user: CurrentUser = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> NextQuestionResponse:
    settings = get_settings()
    body = body or PracticeRequest()
    await ensure_profile(conn, user.id)

    rating = await conn.fetchval("select rating from public.profiles where id = $1", user.id)
    low, high = preset_range(body.preset, rating)
    review = body.variant == "review"
    window = settings.recent_question_window

    async def pick(low, high, allow_repeats):
        return await conn.fetchrow(
            _PICK_QUESTION, user.id, window, body.topics, low, high, allow_repeats, review
        )

    # Best: the chosen difficulty, nothing seen recently. Then relax step by step
    # rather than run dry: allow repeats, then any difficulty.
    question = await pick(low, high, False) or await pick(low, high, True)
    widened = False
    if question is None and not review and (low is not None or high is not None):
        question = await pick(None, None, False) or await pick(None, None, True)
        widened = question is not None
    if question is None:
        if review:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Nothing to review: you've fixed every mistake.")
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No questions here yet.")

    order = game.shuffled_order(len(question["options"]))
    async with conn.transaction():
        attempt_id = await conn.fetchval(
            """
            insert into public.attempts (user_id, question_id, mode, option_order, variant)
            values ($1, $2, 'solo', $3, $4)
            returning id
            """,
            user.id,
            question["id"],
            order,
            body.variant,
        )
        await log_event(
            conn,
            "question_served",
            user_id=user.id,
            attempt_id=attempt_id,
            question_id=question["id"],
            mode="solo",
            variant=body.variant,
            preset=body.preset,
            topics=body.topics,
            widened=widened,
            format=question["format"],
            difficulty=question["difficulty"],
        )

    return NextQuestionResponse(
        attempt_id=attempt_id,
        widened=widened,
        question=ServedQuestion(
            format=question["format"],
            category=question["category"],
            language=question["language"],
            difficulty=question["difficulty"],
            prompt=question["prompt"],
            code=question["code"],
            options=game.apply_order(question["options"], order),
            time_limit_s=question["time_limit_s"],
            rating=question["rating"],
            rating_deviation=question["rating_deviation"],
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
            conn, body.attempt_id, user.id, body.choice, get_settings().answer_grace_ms, body.away_ms
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