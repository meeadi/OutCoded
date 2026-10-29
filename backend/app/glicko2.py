"""The Glicko-2 rating system, implemented from Mark Glickman's paper
"Example of the Glicko-2 system" (glicko.net/glicko/glicko2.pdf).

Every player has three numbers:
  rating      how strong we think they are (starts at 1500)
  rd          rating deviation: how unsure we are (starts at 350, shrinks as they play)
  volatility  how erratic their results are (starts at 0.06)

Unlike plain Elo, a new player's rating moves fast while the system is unsure,
then settles down. We treat every rated match as its own rating period,
like Lichess does, so ratings update the moment a match ends.
"""

import math
from dataclasses import dataclass

SCALE = 173.7178  # converts between the rating scale and Glicko-2's internal scale
TAU = 0.5  # how much volatility can change; the paper suggests 0.3 to 1.2
EPSILON = 0.000001  # convergence tolerance for the volatility calculation
DEFAULT_RATING = 1500.0
DEFAULT_RD = 350.0
DEFAULT_VOLATILITY = 0.06

WIN, DRAW, LOSS = 1.0, 0.5, 0.0


@dataclass(frozen=True)
class Rating:
    rating: float = DEFAULT_RATING
    rd: float = DEFAULT_RD
    volatility: float = DEFAULT_VOLATILITY


def _g(phi: float) -> float:
    return 1 / math.sqrt(1 + 3 * phi**2 / math.pi**2)


def _expected(mu: float, mu_j: float, phi_j: float) -> float:
    return 1 / (1 + math.exp(-_g(phi_j) * (mu - mu_j)))


def _new_volatility(sigma: float, phi: float, v: float, delta: float, tau: float) -> float:
    """Step 5: solve for the new volatility with the Illinois algorithm."""
    a = math.log(sigma**2)

    def f(x: float) -> float:
        ex = math.exp(x)
        return ex * (delta**2 - phi**2 - v - ex) / (2 * (phi**2 + v + ex) ** 2) - (x - a) / tau**2

    big_a = a
    if delta**2 > phi**2 + v:
        big_b = math.log(delta**2 - phi**2 - v)
    else:
        k = 1
        while f(a - k * tau) < 0:
            k += 1
        big_b = a - k * tau

    f_a, f_b = f(big_a), f(big_b)
    while abs(big_b - big_a) > EPSILON:
        big_c = big_a + (big_a - big_b) * f_a / (f_b - f_a)
        f_c = f(big_c)
        if f_c * f_b <= 0:
            big_a, f_a = big_b, f_b
        else:
            f_a /= 2
        big_b, f_b = big_c, f_c

    return math.exp(big_a / 2)


def update(player: Rating, results: list[tuple[Rating, float]], tau: float = TAU) -> Rating:
    """New rating after one rating period.

    `results` is a list of (opponent's rating before the period, score),
    where score is WIN (1), DRAW (0.5) or LOSS (0).
    """
    # Step 2: convert to the Glicko-2 scale.
    mu = (player.rating - DEFAULT_RATING) / SCALE
    phi = player.rd / SCALE
    sigma = player.volatility

    if not results:
        # Didn't play: only the uncertainty grows.
        phi_star = math.sqrt(phi**2 + sigma**2)
        return Rating(player.rating, min(phi_star * SCALE, DEFAULT_RD), sigma)

    # Steps 3 and 4: estimated variance (v) and improvement (delta).
    v_inverse = 0.0
    improvement = 0.0
    for opponent, score in results:
        mu_j = (opponent.rating - DEFAULT_RATING) / SCALE
        phi_j = opponent.rd / SCALE
        g = _g(phi_j)
        expected = _expected(mu, mu_j, phi_j)
        v_inverse += g**2 * expected * (1 - expected)
        improvement += g * (score - expected)
    v = 1 / v_inverse
    delta = v * improvement

    # Step 5: new volatility.
    new_sigma = _new_volatility(sigma, phi, v, delta, tau)

    # Steps 6 and 7: new rating deviation and rating.
    phi_star = math.sqrt(phi**2 + new_sigma**2)
    new_phi = 1 / math.sqrt(1 / phi_star**2 + 1 / v)
    new_mu = mu + new_phi**2 * improvement

    # Step 8: back to the rating scale.
    return Rating(
        rating=SCALE * new_mu + DEFAULT_RATING,
        rd=min(SCALE * new_phi, DEFAULT_RD),
        volatility=new_sigma,
    )


def match_update(a: Rating, b: Rating, score_a: float) -> tuple[Rating, Rating]:
    """Update both players after one match. score_a is WIN, DRAW or LOSS for player a."""
    return update(a, [(b, score_a)]), update(b, [(a, 1 - score_a)])