import pytest

from app.glicko2 import DRAW, LOSS, WIN, Rating, match_update, update


def test_matches_glickmans_worked_example():
    # The example from Glickman's paper: a 1500 player beats a 1400,
    # then loses to a 1550 and a 1700, all in one rating period.
    player = Rating(1500, 200, 0.06)
    results = [(Rating(1400, 30), WIN), (Rating(1550, 100), LOSS), (Rating(1700, 300), LOSS)]

    new = update(player, results, tau=0.5)

    assert new.rating == pytest.approx(1464.06, abs=0.01)
    assert new.rd == pytest.approx(151.52, abs=0.01)
    assert new.volatility == pytest.approx(0.05999, abs=0.00001)


def test_winner_gains_and_loser_drops_by_the_same_amount_when_equal():
    winner, loser = match_update(Rating(), Rating(), WIN)
    assert winner.rating > 1500 > loser.rating
    assert winner.rating - 1500 == pytest.approx(1500 - loser.rating)


def test_new_players_move_much_faster_than_settled_ones():
    newbie, _ = match_update(Rating(1500, 350), Rating(1500, 350), WIN)
    veteran, _ = match_update(Rating(1500, 60), Rating(1500, 60), WIN)
    assert newbie.rating - 1500 > 3 * (veteran.rating - 1500)


def test_playing_shrinks_uncertainty():
    after, _ = match_update(Rating(), Rating(), WIN)
    assert after.rd < 350


def test_beating_a_stronger_player_is_worth_more():
    upset, _ = match_update(Rating(1500, 100), Rating(1800, 100), WIN)
    expected_win, _ = match_update(Rating(1500, 100), Rating(1200, 100), WIN)
    assert upset.rating - 1500 > expected_win.rating - 1500


def test_draw_between_equals_changes_nothing():
    a, b = match_update(Rating(1600, 80), Rating(1600, 80), DRAW)
    assert a.rating == pytest.approx(1600)
    assert b.rating == pytest.approx(1600)


def test_inactivity_only_grows_uncertainty_and_caps_at_350():
    player = Rating(1700, 340, 0.06)
    after = update(player, [])
    assert after.rating == 1700
    assert 340 < after.rd <= 350