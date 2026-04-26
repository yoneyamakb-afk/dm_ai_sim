from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MatchResult:
    player_a: str
    player_b: str
    score_a: float


def expected_score(rating_a: float, rating_b: float) -> float:
    return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))


def update_elo(
    rating_a: float,
    rating_b: float,
    score_a: float,
    k_factor: float = 32.0,
) -> tuple[float, float]:
    expected_a = expected_score(rating_a, rating_b)
    delta = k_factor * (score_a - expected_a)
    return rating_a + delta, rating_b - delta


def calculate_elo(
    results: list[MatchResult],
    initial_rating: float = 1000.0,
    k_factor: float = 32.0,
) -> dict[str, float]:
    ratings: dict[str, float] = {}
    for result in results:
        ratings.setdefault(result.player_a, initial_rating)
        ratings.setdefault(result.player_b, initial_rating)
        ratings[result.player_a], ratings[result.player_b] = update_elo(
            ratings[result.player_a],
            ratings[result.player_b],
            result.score_a,
            k_factor=k_factor,
        )
    return ratings
