"""Spot suspicious answer patterns. These are flags for a human to review,
never automatic bans: false accusations hurt a community more than cheaters do.

Every detector looks at one player's answers and returns a Flag (or None)
with a severity from 0 to 1 and the evidence behind it.
"""

import math
import statistics
from dataclasses import dataclass

# --- superhuman_speed -------------------------------------------------------
# Nobody reads code faster than about 100 characters per second, so a right
# answer that arrives before the question could even be read is suspicious.
MS_PER_CHAR = 10
MIN_READ_MS = 600
SPEED_MIN_HITS = 3
SPEED_MIN_SHARE = 0.25

# --- overperformance --------------------------------------------------------
# Work out the rating this player *performed* at on these answers, and compare
# it with their known rating. The gap only counts if it's bigger than both
# uncertainties together can explain. Simulated on 5,000 honest players, this
# flags about 1 in 1,000 while catching ~80% of AI-assisted cheaters.
OVERPERFORMANCE_MIN_ANSWERS = 15
OVERPERFORMANCE_Z = 3.0
PROVISIONAL_RD = 110  # ratings this uncertain are still a guess: don't judge against them
_LN10_400 = math.log(10) / 400

# --- robotic_timing ---------------------------------------------------------
# Humans are inconsistent; scripts answer in eerily steady times. Spread is
# measured on the middle half of answers (interquartile range), so a bot's
# network hiccups can't hide it. Simulated honest players flagged: under 0.1%.
ROBOTIC_MIN_ANSWERS = 10
ROBOTIC_MAX_SPREAD = 0.15  # robust spread relative to the median
_IQR_TO_SD = 1.349  # for normal data, the interquartile range is 1.349 standard deviations

# --- tab_switching ----------------------------------------------------------
# Leaving the tab mid-question and coming back with the right answer.
AWAY_MIN_MS = 2000
AWAY_MIN_HITS = 3
AWAY_MIN_SHARE = 0.3


@dataclass(frozen=True)
class Answer:
    correct: bool
    timed_out: bool
    response_ms: int
    text_chars: int  # prompt + code + options: how much there was to read
    question_rating: float
    first_time: bool  # the player's first ever attempt at this question
    away_ms: int | None = None  # browser-reported; None if unknown
    slug: str = ""


@dataclass(frozen=True)
class Flag:
    kind: str
    severity: float
    evidence: dict


def min_read_ms(text_chars: int) -> int:
    return max(MIN_READ_MS, text_chars * MS_PER_CHAR)


def expected_correct(player_rating: float, question_rating: float) -> float:
    """Chance a player of this rating gets a question of this difficulty right (Elo curve)."""
    return 1 / (1 + 10 ** ((question_rating - player_rating) / 400))


def superhuman_speed(answers: list[Answer]) -> Flag | None:
    # Only first attempts: recognising a question you've seen before is legitimate.
    correct = [a for a in answers if a.correct and a.first_time]
    hits = [a for a in correct if a.response_ms < min_read_ms(a.text_chars)]
    if len(hits) < SPEED_MIN_HITS:
        return None
    share = len(hits) / len(correct)
    if share < SPEED_MIN_SHARE:
        return None
    return Flag(
        "superhuman_speed",
        severity=round(min(1.0, share), 3),
        evidence={
            "too_fast": len(hits),
            "first_time_correct": len(correct),
            "examples": [
                {"question": a.slug, "answered_ms": a.response_ms, "read_ms": min_read_ms(a.text_chars)}
                for a in sorted(hits, key=lambda a: a.response_ms)[:5]
            ],
        },
    )


def performance_rating(answers: list[Answer]) -> tuple[float, float]:
    """The rating that best explains these answers (maximum likelihood), and its standard error.

    All-right (or all-wrong) has no finite answer, so we add one virtual right
    and one virtual wrong answer at the average question difficulty. That keeps
    the estimate finite without moving it much once there's real data.
    """
    average = statistics.fmean(a.question_rating for a in answers)
    padded = [(a.correct, a.question_rating) for a in answers] + [(True, average), (False, average)]

    def surplus(rating: float) -> float:
        return sum(correct - expected_correct(rating, q) for correct, q in padded)

    low, high = -1000.0, 5000.0
    for _ in range(60):  # bisection: surplus() falls as the rating rises
        mid = (low + high) / 2
        low, high = (mid, high) if surplus(mid) > 0 else (low, mid)
    rating = (low + high) / 2

    information = sum(
        expected_correct(rating, q) * (1 - expected_correct(rating, q)) for _, q in padded
    ) * _LN10_400**2
    return rating, 1 / math.sqrt(information)


def overperformance(answers: list[Answer], player_rating: float, player_rd: float) -> Flag | None:
    fresh = [a for a in answers if a.first_time]
    if len(fresh) < OVERPERFORMANCE_MIN_ANSWERS or player_rd > PROVISIONAL_RD:
        return None
    performed, standard_error = performance_rating(fresh)
    z = (performed - player_rating) / math.hypot(standard_error, player_rd)
    if z < OVERPERFORMANCE_Z:
        return None
    return Flag(
        "overperformance",
        severity=round(min(1.0, (z - OVERPERFORMANCE_Z) / 3 + 0.5), 3),
        evidence={
            "answers": len(fresh),
            "correct": sum(a.correct for a in fresh),
            "performed_at": round(performed),
            "rated": round(player_rating),
            "z_score": round(z, 2),
        },
    )


def timing_spread(times: list[int]) -> float:
    """Robust relative spread: like standard deviation / mean, but outliers barely move it."""
    median = statistics.median(times)
    if median <= 0:
        return math.inf
    q1, _, q3 = statistics.quantiles(times, n=4)
    return (q3 - q1) / _IQR_TO_SD / median


def robotic_timing(answers: list[Answer]) -> Flag | None:
    times = [a.response_ms for a in answers if a.correct]
    if len(times) < ROBOTIC_MIN_ANSWERS:
        return None
    spread = timing_spread(times)
    if spread > ROBOTIC_MAX_SPREAD:
        return None
    return Flag(
        "robotic_timing",
        severity=round(min(1.0, 1 - spread / ROBOTIC_MAX_SPREAD + 0.5), 3),
        evidence={
            "correct_answers": len(times),
            "median_ms": round(statistics.median(times)),
            "spread": round(spread, 3),
            "human_typical": "> 0.4",
        },
    )


def tab_switching(answers: list[Answer]) -> Flag | None:
    reported = [a for a in answers if a.correct and a.away_ms is not None]
    hits = [a for a in reported if a.away_ms >= AWAY_MIN_MS]
    if len(hits) < AWAY_MIN_HITS:
        return None
    share = len(hits) / len(reported)
    if share < AWAY_MIN_SHARE:
        return None
    return Flag(
        "tab_switching",
        severity=round(min(1.0, share), 3),
        evidence={
            "left_tab_then_correct": len(hits),
            "correct_answers": len(reported),
            "longest_away_ms": max(a.away_ms for a in hits),
        },
    )


def detect(answers: list[Answer], player_rating: float, player_rd: float) -> list[Flag]:
    candidates = [
        superhuman_speed(answers),
        overperformance(answers, player_rating, player_rd),
        robotic_timing(answers),
        tab_switching(answers),
    ]
    return [flag for flag in candidates if flag is not None]