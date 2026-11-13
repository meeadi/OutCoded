from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.practice import Preset, Variant


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
    rating: float #calibrated difficulty 
    rating_deviation: float #uncertainty in the difficulty


class NextQuestionResponse(BaseModel):
    attempt_id: UUID
    question: ServedQuestion
    widened: bool = False  # the chosen difficulty ran dry, so this one is from outside it


class PracticeRequest(BaseModel):
    """What to practice. Everything is optional: no body means a plain rush on all topics."""

    topics: list[str] = Field(default_factory=list, max_length=20)  # empty = all topics
    preset: Preset | None = None  # chill / level / pain; None = any difficulty
    variant: Variant = "rush"


class PracticeTopic(BaseModel):
    id: str
    name: str
    counts: dict[str, int]  # questions per preset: chill, level, pain, all
    mistakes: int  # questions this player last got wrong (for review mode)


class PracticeTopicsResponse(BaseModel):
    rating: float
    topics: list[PracticeTopic]


class AnswerRequest(BaseModel):
    attempt_id: UUID
    choice: int | None = Field(default=None, ge=0, le=3, description="Position of the option the player clicked (0-based), or null if time ran out")
    away_ms: int | None = Field(
        default=None,
        ge=0,
        le=600_000,
        description="How long the tab was hidden or unfocused during the question (browser-reported)",
    )


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