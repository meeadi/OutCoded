from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ServedQuestion(BaseModel):
    """What the player sees. Deliberately has no correct answer in it."""

    format: str
    category: str
    language: str | None
    difficulty: str
    prompt: str
    code: str | None
    options: list[str]
    time_limit_s: int


class NextQuestionResponse(BaseModel):
    attempt_id: UUID
    question: ServedQuestion


class AnswerRequest(BaseModel):
    attempt_id: UUID
    choice: int | None = Field(default=None, ge=0, le=3, description="Position of the option the player clicked (0-based), or null if time ran out")


class AnswerResponse(BaseModel):
    correct: bool
    timed_out: bool
    correct_choice: int  # position of the right option as the player saw it
    response_ms: int
    explanation: str


class Profile(BaseModel):
    id: UUID
    username: str | None
    rating: float
    rating_deviation: float
    created_at: datetime

class UsernameRequest(BaseModel):
    username: str = Field(pattern=r"^[A-Za-z0-9_]{3,20}$")