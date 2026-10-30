import uuid

from app.matchmaking import ANYONE_AFTER_S, Entry, acceptable, allowed_gap


def entry(rating: float, joined_at: float) -> Entry:
    return Entry(user_id=uuid.uuid4(), username="x", rating=rating, socket=None, joined_at=joined_at)


def test_range_starts_small_and_widens():
    assert allowed_gap(0) == 100
    assert allowed_gap(10) == 600
    assert allowed_gap(ANYONE_AFTER_S) is None


def test_close_ratings_match_immediately():
    assert acceptable(entry(1500, 0), entry(1580, 0), now=0)


def test_far_ratings_wait_until_the_range_covers_them():
    a, b = entry(1500, 0), entry(2100, 0)  # 600 apart
    assert not acceptable(a, b, now=5)  # range 350
    assert acceptable(a, b, now=10)  # range 600


def test_the_more_patient_player_decides():
    veteran_waiter, newcomer = entry(1500, 0), entry(1900, 8)  # 400 apart
    assert acceptable(veteran_waiter, newcomer, now=8)  # the first has waited 8s: range 500


def test_anyone_after_the_limit():
    assert acceptable(entry(800, 0), entry(2800, 0), now=ANYONE_AFTER_S)