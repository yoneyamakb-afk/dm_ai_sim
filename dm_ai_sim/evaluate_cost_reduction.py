from __future__ import annotations

import os
from typing import Any

from dm_ai_sim.agents.heuristic_agent import HeuristicAgent
from dm_ai_sim.agents.random_agent import RandomAgent
from dm_ai_sim.cost_reduction_runtime import cost_reduction_runtime_test_deck
from dm_ai_sim.env import Env, EnvConfig


def main(games: int | None = None) -> None:
    game_count = games if games is not None else int(os.environ.get("DM_EVALUATE_COST_REDUCTION_GAMES", "20"))
    summary = evaluate_games(game_count)
    for key in ("games", "cost_reduction_casts", "cost_reduction_used", "summons_enabled_by_reduction", "expired_unused", "errors"):
        print(f"{key}: {summary[key]}")


def evaluate_games(games: int) -> dict[str, int]:
    summary = {
        "games": games,
        "cost_reduction_casts": 0,
        "cost_reduction_used": 0,
        "summons_enabled_by_reduction": 0,
        "expired_unused": 0,
        "errors": 0,
    }
    for game_index in range(games):
        try:
            events = _run_game(game_index)
        except Exception:
            summary["errors"] += 1
            continue
        summary["cost_reduction_casts"] += sum(1 for event in events if event["cost_reduction_created"])
        summary["cost_reduction_used"] += sum(1 for event in events if event["cost_reduction_used"])
        summary["summons_enabled_by_reduction"] += sum(1 for event in events if event["summons_enabled_by_reduction"])
        summary["expired_unused"] += sum(1 for event in events if event["cost_reduction_expired"])
        summary["errors"] += sum(1 for event in events if event["zone_errors"])
    return summary


def _run_game(game_index: int) -> list[dict[str, Any]]:
    deck0 = cost_reduction_runtime_test_deck(base_id=380_000 + game_index * 1_000)
    deck1 = cost_reduction_runtime_test_deck(base_id=390_000 + game_index * 1_000)
    env = Env(deck0=deck0, deck1=deck1, config=EnvConfig(seed=57_000 + game_index, max_turns=120))
    env.reset()
    agents = [HeuristicAgent(), RandomAgent(seed=game_index)]
    events: list[dict[str, Any]] = []
    done = False
    steps = 0
    while not done and steps < 1000:
        observation = env.get_observation()
        action = agents[observation["current_player"]].act(env.legal_actions(), observation)
        _obs, _reward, done, info = env.step(action)
        events.append(_event(env, info))
        steps += 1
    return events


def _event(env: Env, info: dict[str, Any]) -> dict[str, Any]:
    return {
        "cost_reduction_created": bool(info.get("cost_reduction_created")),
        "cost_reduction_used": bool(info.get("cost_reduction_used")),
        "summons_enabled_by_reduction": bool(info.get("summons_enabled_by_reduction")),
        "cost_reduction_expired": bool(info.get("cost_reduction_expired")),
        "zone_errors": bool(env.validate_invariants()),
    }


if __name__ == "__main__":
    main()
