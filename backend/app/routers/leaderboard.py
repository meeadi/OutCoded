"""Leaderboard and public player profiles (ranked play only)."""

from datetime import datetime

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.auth import CurrentUser, get_current_user
from app.db import get_conn

router = APIRouter(tags=["leaderboard"])

# New players stay off the leaderboard until they've played this many ranked
# matches, so one lucky win can't put someone at #1.
PLACEMENT_MATCHES = 5


class Record(BaseModel):
    games: int
    wins: int
    losses: int
    draws: int


class LeaderboardRow(BaseModel):
    rank: int
    username: str
    rating: float
    rating_deviation: float
    record: Record


class Leaderboard(BaseModel):
    placement_matches: int
    players: list[LeaderboardRow]
    you: LeaderboardRow | None  # None until you're placed
    your_games: int


class RatingPoint(BaseModel):
    at: datetime
    rating: float


class RecentMatch(BaseModel):
    at: datetime
    opponent: str | None
    result: str  # win / loss / draw
    change: int
    score_you: int
    score_opponent: int
    forfeit: bool


class PlayerProfile(BaseModel):
    username: str
    rating: float
    rating_deviation: float
    joined: datetime
    rank: int | None  # None until placed
    placement_matches: int
    record: Record
    history: list[RatingPoint]  # oldest first, starting at 1500
    recent: list[RecentMatch]  # newest first


# One row per player who has played ranked: rating, record and leaderboard rank.
_STANDINGS = """
    with records as (
        select user_id,
               count(*)                                   as games,
               count(*) filter (where result = 'win')     as wins,
               count(*) filter (where result = 'loss')    as losses,
               count(*) filter (where result = 'draw')    as draws
        from public.rating_history
        group by user_id
    )
    select p.id, p.username, p.rating, p.rating_deviation,
           r.games, r.wins, r.losses, r.draws,
           case when r.games >= $1
                then rank() over (
                    partition by r.games >= $1
                    order by p.rating desc
                )
           end as rank
    from public.profiles p
    join records r on r.user_id = p.id
    where p.username is not null
"""


def _row(record: asyncpg.Record) -> LeaderboardRow:
    return LeaderboardRow(
        rank=record["rank"],
        username=record["username"],
        rating=record["rating"],
        rating_deviation=record["rating_deviation"],
        record=Record(
            games=record["games"],
            wins=record["wins"],
            losses=record["losses"],
            draws=record["draws"],
        ),
    )


@router.get("/leaderboard", response_model=Leaderboard)
async def leaderboard(
    limit: int = Query(50, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> Leaderboard:
    rows = await conn.fetch(
        f"select * from ({_STANDINGS}) s where rank is not null order by rank, username limit $2",
        PLACEMENT_MATCHES,
        limit,
    )
    mine = await conn.fetchrow(f"select * from ({_STANDINGS}) s where id = $2", PLACEMENT_MATCHES, user.id)
    return Leaderboard(
        placement_matches=PLACEMENT_MATCHES,
        players=[_row(r) for r in rows],
        you=_row(mine) if mine and mine["rank"] is not None else None,
        your_games=mine["games"] if mine else 0,
    )


@router.get("/players/{username}", response_model=PlayerProfile)
async def player_profile(
    username: str,
    _user: CurrentUser = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> PlayerProfile:
    profile = await conn.fetchrow(
        """
        select id, username, rating, rating_deviation, created_at
        from public.profiles where lower(username) = lower($1)
        """,
        username,
    )
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No player with that name.")

    standing = await conn.fetchrow(
        f"select * from ({_STANDINGS}) s where id = $2", PLACEMENT_MATCHES, profile["id"]
    )

    history_rows = await conn.fetch(
        """
        select created_at, rating_before, rating_after
        from public.rating_history
        where user_id = $1
        order by created_at
        """,
        profile["id"],
    )
    history: list[RatingPoint] = []
    if history_rows:
        # Start the line where they started, just before their first ranked match.
        first = history_rows[0]
        history.append(RatingPoint(at=first["created_at"], rating=first["rating_before"]))
        history += [RatingPoint(at=r["created_at"], rating=r["rating_after"]) for r in history_rows]

    recent_rows = await conn.fetch(
        """
        select rh.created_at, rh.result, rh.rating_before, rh.rating_after, m.forfeit,
               opp.username as opponent,
               case when m.host_id = rh.user_id then m.host_score else m.guest_score end as score_you,
               case when m.host_id = rh.user_id then m.guest_score else m.host_score end as score_opponent
        from public.rating_history rh
        join public.matches m on m.id = rh.match_id
        left join public.profiles opp
               on opp.id = case when m.host_id = rh.user_id then m.guest_id else m.host_id end
        where rh.user_id = $1
        order by rh.created_at desc
        limit 10
        """,
        profile["id"],
    )

    return PlayerProfile(
        username=profile["username"],
        rating=profile["rating"],
        rating_deviation=profile["rating_deviation"],
        joined=profile["created_at"],
        rank=standing["rank"] if standing else None,
        placement_matches=PLACEMENT_MATCHES,
        record=Record(
            games=standing["games"] if standing else 0,
            wins=standing["wins"] if standing else 0,
            losses=standing["losses"] if standing else 0,
            draws=standing["draws"] if standing else 0,
        ),
        history=history,
        recent=[
            RecentMatch(
                at=r["created_at"],
                opponent=r["opponent"],
                result=r["result"],
                change=round(r["rating_after"]) - round(r["rating_before"]),
                score_you=r["score_you"],
                score_opponent=r["score_opponent"],
                forfeit=r["forfeit"],
            )
            for r in recent_rows
        ],
    )