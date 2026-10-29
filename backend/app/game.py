"""Pure game rules, kept free of FastAPI and database code so they're easy to test."""

import random


def shuffled_order(option_count: int, rng: random.Random | None = None) -> list[int]:
    """Random display order. Position i on screen shows original option order[i]."""
    order = list(range(option_count))
    (rng or random).shuffle(order)
    return order


def apply_order(options: list[str], order: list[int]) -> list[str]:
    return [options[i] for i in order]


def to_original_index(displayed_choice: int, order: list[int]) -> int:
    """Map the position the player clicked back to the option's original index."""
    if not 0 <= displayed_choice < len(order):
        raise ValueError("choice out of range")
    return order[displayed_choice]


def to_displayed_index(original_index: int, order: list[int]) -> int:
    return order.index(original_index)


def is_timed_out(response_ms: int, time_limit_s: int, grace_ms: int) -> bool:
    return response_ms > time_limit_s * 1000 + grace_ms
