from app.practice import preset_range


def test_presets_sit_around_the_players_rating():
    assert preset_range("level", 1500) == (1300, 1700)
    assert preset_range("chill", 1500) == (None, 1400)
    assert preset_range("pain", 1500) == (1600, None)


def test_no_preset_means_any_difficulty():
    assert preset_range(None, 1500) == (None, None)


def test_a_new_players_presets_line_up_with_the_labels():
    # New players sit at 1500, so chill picks the easy questions (1300), pain the hard (1700).
    low, high = preset_range("chill", 1500)
    assert high is not None and 1300 < high < 1500
    low, high = preset_range("pain", 1500)
    assert low is not None and 1500 < low < 1700