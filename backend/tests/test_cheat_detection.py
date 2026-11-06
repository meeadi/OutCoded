import random

from app.cheat_detection import (
    Answer,
    detect,
    expected_correct,
    overperformance,
    performance_rating,
    robotic_timing,
    superhuman_speed,
    tab_switching,
)


def answer(correct=True, ms=8000, chars=150, rating=1500, first=True, away=None):
    return Answer(
        correct=correct,
        timed_out=False,
        response_ms=ms,
        text_chars=chars,
        question_rating=rating,
        first_time=first,
        away_ms=away,
    )


def honest_player(n=40, seed=1):
    """Realistic: varied times, about the accuracy their rating predicts, rarely leaves the tab."""
    rng = random.Random(seed)
    answers = []
    for _ in range(n):
        q_rating = rng.uniform(1300, 1700)
        correct = rng.random() < expected_correct(1500, q_rating)
        ms = int(rng.uniform(4000, 20000))
        answers.append(answer(correct, ms=ms, rating=q_rating, away=rng.choice([0, 0, 0, 800])))
    return answers


def test_expected_correct_is_half_for_an_even_match():
    assert expected_correct(1500, 1500) == 0.5
    assert expected_correct(1900, 1500) > 0.9


def test_an_honest_player_raises_no_flags():
    for seed in range(20):
        assert detect(honest_player(seed=seed), player_rating=1500, player_rd=80) == [], seed


def test_answering_faster_than_reading_is_flagged():
    answers = honest_player()[:10] + [answer(ms=300, chars=200) for _ in range(5)]
    flag = superhuman_speed(answers)
    assert flag and flag.evidence["too_fast"] == 5


def test_fast_answers_to_repeat_questions_are_fine():
    repeats = [answer(ms=300, chars=200, first=False) for _ in range(10)]
    assert superhuman_speed(honest_player()[:10] + repeats) is None


def test_one_lucky_quick_answer_is_not_enough():
    answers = honest_player() + [answer(ms=300, chars=200)]
    assert superhuman_speed(answers) is None


def test_crushing_questions_far_above_your_level_is_flagged():
    # A settled 1300 player getting 20 out of 20 questions rated 1800 right.
    answers = [answer(rating=1800) for _ in range(20)]
    flag = overperformance(answers, player_rating=1300, player_rd=70)
    assert flag and flag.evidence["z_score"] > 3 and flag.evidence["performed_at"] > 1800


def test_a_strong_player_doing_well_is_not_overperforming():
    answers = [answer(rating=1400) for _ in range(20)]
    assert overperformance(answers, player_rating=2000, player_rd=70) is None


def test_new_players_are_not_judged_against_a_guessed_rating():
    answers = [answer(rating=1800) for _ in range(20)]
    assert overperformance(answers, player_rating=1500, player_rd=350) is None


def test_performance_rating_lands_where_the_answers_point():
    # Half right against 1600-rated questions: performed at about 1600.
    answers = [answer(correct=i % 2 == 0, rating=1600) for i in range(40)]
    rating, error = performance_rating(answers)
    assert abs(rating - 1600) < 1 and 50 < error < 200


def test_too_few_answers_to_judge():
    answers = [answer(rating=1900) for _ in range(5)]
    assert overperformance(answers, player_rating=1200, player_rd=70) is None


def test_metronome_timing_is_flagged():
    answers = [answer(ms=2000 + (i % 3) * 50) for i in range(12)]
    flag = robotic_timing(answers)
    assert flag and flag.evidence["spread"] < 0.15


def test_a_network_hiccup_does_not_hide_a_bot():
    steady = [80, 82, 85, 79, 90, 88, 84, 81, 86, 83, 87, 89]
    answers = [answer(ms=ms) for ms in steady] + [answer(ms=531), answer(ms=900)]
    assert robotic_timing(answers) is not None


def test_leaving_the_tab_then_answering_right_is_flagged():
    answers = [answer(away=0) for _ in range(6)] + [answer(away=9000) for _ in range(4)]
    flag = tab_switching(answers)
    assert flag and flag.evidence["left_tab_then_correct"] == 4


def test_answers_without_tab_data_are_ignored():
    assert tab_switching([answer(away=None) for _ in range(10)]) is None