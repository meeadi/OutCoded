import random

import pytest

from app import game


def test_shuffled_order_is_a_permutation():
    order = game.shuffled_order(4, random.Random(7))
    assert sorted(order) == [0, 1, 2, 3]


def test_choice_maps_back_to_original_option():
    options = ["wrong 1", "right", "wrong 2", "wrong 3"]
    order = [2, 0, 3, 1]  # screen shows: wrong 2, wrong 1, wrong 3, right
    displayed = game.apply_order(options, order)
    assert displayed == ["wrong 2", "wrong 1", "wrong 3", "right"]

    clicked = displayed.index("right")
    assert game.to_original_index(clicked, order) == 1
    assert game.to_displayed_index(1, order) == clicked


def test_choice_out_of_range_is_rejected():
    with pytest.raises(ValueError):
        game.to_original_index(3, [1, 0, 2])  # only 3 options on screen


@pytest.mark.parametrize(
    ("response_ms", "expected"),
    [(29_000, False), (31_500, False), (31_501, True)],
)
def test_timeout_includes_grace_period(response_ms, expected):
    assert game.is_timed_out(response_ms, time_limit_s=30, grace_ms=1500) is expected

def test_match_points_reward_speed():
    assert game.match_points(True, 0, 30) == 200  # instant
    assert game.match_points(True, 15_000, 30) == 150  # half the time used
    assert game.match_points(True, 30_000, 30) == 100  # right at the limit
    assert game.match_points(True, 31_000, 30) == 100  # within grace: no negative bonus


def test_match_points_zero_when_wrong():
    assert game.match_points(False, 1_000, 30) == 0