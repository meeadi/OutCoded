from uuid import UUID

import asyncpg


async def log_event(
    conn: asyncpg.Connection,
    event_type: str,
    *,
    user_id: UUID | None = None,
    attempt_id: UUID | None = None,
    question_id: UUID | None = None,
    **properties,
) -> None:
    """Append one row to the analytics log. Every gameplay action should call this."""
    await conn.execute(
        """
        insert into public.events (event_type, user_id, attempt_id, question_id, properties)
        values ($1, $2, $3, $4, $5)
        """,
        event_type,
        user_id,
        attempt_id,
        question_id,
        properties,
    )
