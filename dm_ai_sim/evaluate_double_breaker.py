from __future__ import annotations

import os
from typing import Any

from dm_ai_sim.actions import ActionType
from dm_ai_sim.agents.heuristic_agent import HeuristicAgent
from dm_ai_sim.agents.random_agent import RandomAgent
from dm_ai_sim.double_breaker_runtime import double_breaker_runtime_test_deck
from dm_ai_sim.env import Env, EnvConfig


def main(games: int | None = None) -> None:
    game_count = games if games is not None else int(os.environ.get("DM_EVALUATE_DOUBLE_BREAKER_GAMES", "20"))
    summary = evaluate_games(game_count)
    for key in ("games", "double_breaker_attacks", "total_shields_broken", "multi_break_batches", "errors"):
        print(f"{key}: {summary[key]}")


def evaluate_games(games: int) -> dict[str, int]:
    summary = {"games": games, "double_breaker_attacks": 0, "total_shields_broken": 0, "multi_break_batches": 0, "errors": 0}
    for game_index in range(games):
        try:
            events = _run_game(game_index)
        except Exception:
            summary["errors"] += 1
            continue
        summary["double_breaker_attacks"] += sum(1 for event in events if event["double_breaker_attack"])
        summary["total_shields_broken"] += sum(event["shields_broken_count"] for event in events)
        summary["multi_break_batches"] += sum(1 for event in events if event["multi_break"])
        summary["errors"] += sum(1 for event in events if not event["zone_count_consistency"])
    return summary


def _run_game(game_index: int) -> list[dict[str, Any]]:
    deck0 = double_breaker_runtime_test_deck(base_id=330_000 + game_index * 1_000)
    deck1 = double_breaker_runtime_test_deck(base_id=340_000 + game_index * 1_000)
    env = Env(deck0=deck0, deck1=deck1, config=EnvConfig(seed=55_000 + game_index, max_turns=120))
    env.reset()
    agents = [HeuristicAgent(), RandomAgent(seed=game_index)]
    events: list[dict[str, Any]] = []
    done = False
    steps = 0
    while not done and steps < 1000:
        observation = env.get_observation()
        action = agents[observation["current_player"]].act(env.legal_actions(), observation)
        before = _zone_counts(env)
        _obs, _reward, done, info = env.step(action)
        after = _zone_counts(env)
        events.append(_event(action, info, before, after))
        steps += 1
    return events


def _event(action, info: dict[str, Any], before: int, after: int) -> dict[str, Any]:
    breaker_count = int(info.get("breaker_count", 1))
    return {
        "attack_shield": action.type == ActionType.ATTACK_SHIELD,
        "double_breaker_attack": action.type == ActionType.ATTACK_SHIELD and breaker_count >= 2,
        "breaker_count": breaker_count,
        "shields_to_break": int(info.get("shields_to_break", 0)),
        "shields_broken_count": int(info.get("shields_broken_count", 0)),
        "multi_break": bool(info.get("multi_break")),
        "zone_count_consistency": before == after,
    }


def _zone_counts(env: Env) -> int:
    errors = env.validate_invariants()
    if errors:
        return -1
    assert env.state is not None
    return sum(
        len(player.deck)
        + len(player.hand)
        + len(player.mana)
        + sum(1 + len(creature.evolution_sources) for creature in player.battle_zone)
        + len(player.graveyard)
        + len(player.shields)
        for player in env.state.players
    )


if __name__ == "__main__":
    main()
