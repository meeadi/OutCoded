"""Practice: topics, difficulty presets and modes.

Practice never changes a player's rating. It does help calibrate questions,
except in untimed modes (zen) and on re-tries (review), where answers don't
say much about how hard a question really is.
"""

from typing import Literal

Preset = Literal["chill", "level", "pain"]
Variant = Literal["rush", "blitz", "survival", "zen", "review"]

# Difficulty presets, relative to the player's rating. They overlap a little
# on purpose, so small topics don't run dry as quickly.
PRESETS: dict[str, tuple[float | None, float | None]] = {
    "chill": (None, -100),  # comfortably below your level
    "level": (-200, 200),  # around your level: the best for improving
    "pain": (100, None),  # above it
}

# Answers in these modes don't move a question's difficulty rating.
NO_CALIBRATION = {"zen", "review"}
# Zen has no clock at all.
UNTIMED = {"zen"}


def preset_range(preset: str | None, rating: float) -> tuple[float | None, float | None]:
    """The question-rating range for a preset, e.g. "level" for a 1500 player -> (1300, 1700)."""
    if preset is None:
        return None, None
    low, high = PRESETS[preset]
    return (
        None if low is None else rating + low,
        None if high is None else rating + high,
    )