"""Apply Glicko-2 to both players when a rated match ends."""

from uuid import UUID

import asyncpg

from app import glicko2


async def apply_match_result(
    conn: asyncpg.Connection,
    match_id: UUID,
    player_a: UUID,
    player_b: UUID,
    score_a: float,
) -> dict[UUID, dict]:
    """Update both ratings in one transaction and record the history.

    score_a is glicko2.WIN, DRAW or LOSS from player_a's point of view.
    Returns {player_id: {"before": int, "after": int, "change": int}}.
    """
    async with conn.transaction():
        # Lock both profiles, always in the same order so two matches
        # finishing at once can't deadlock each other.
        rows = await conn.fetch(
            """
            select id, rating, rating_deviation, volatility
            from public.profiles
            where id = any($1::uuid[])
            order by id
            for update
            """,
            [player_a, player_b],
        )
        before = {
            row["id"]: glicko2.Rating(row["rating"], row["rating_deviation"], row["volatility"])
            for row in rows
        }
        new_a, new_b = glicko2.match_update(before[player_a], before[player_b], score_a)
        after = {player_a: new_a, player_b: new_b}
        scores = {player_a: score_a, player_b: 1 - score_a}

        changes = {}
        for player_id, new in after.items():
            old = before[player_id]
            result = {glicko2.WIN: "win", glicko2.DRAW: "draw", glicko2.LOSS: "loss"}[scores[player_id]]
            await conn.execute(
                """
                update public.profiles
                set rating = $2, rating_deviation = $3, volatility = $4
                where id = $1
                """,
                player_id,
                new.rating,
                new.rd,
                new.volatility,
            )
            await conn.execute(
                """
                insert into public.rating_history (
                    user_id, match_id, result, rating_before, rating_after,
                    rd_before, rd_after, volatility_before, volatility_after
                )
                values ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                player_id,
                match_id,
                result,
                old.rating,
                new.rating,
                old.rd,
                new.rd,
                old.volatility,
                new.volatility,
            )
            changes[player_id] = {
                "before": round(old.rating),
                "after": round(new.rating),
                "change": round(new.rating) - round(old.rating),
            }
        return changes