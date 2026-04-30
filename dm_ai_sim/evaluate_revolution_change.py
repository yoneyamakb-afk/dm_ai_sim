from __future__ import annotations

import os
from typing import Any

from dm_ai_sim.actions import Action
from dm_ai_sim.agents.heuristic_agent import HeuristicAgent
from dm_ai_sim.agents.random_agent import RandomAgent
from dm_ai_sim.env import Env, EnvConfig
from dm_ai_sim.revolution_change_runtime import revolution_change_runtime_test_deck


def main(games: int | None = None) -> None:
    game_count = games if games is not None else int(os.environ.get("DM_EVALUATE_REVOLUTION_CHANGE_GAMES", "20"))
    summary = evaluate_games(game_count)
    for key in ("games", "revolution_change_activations", "returned_to_hand", "red_girazon_entries", "errors"):
        print(f"{key}: {summary[key]}")


def evaluate_games(games: int) -> dict[str, int]:
    summary = {"games": games, "revolution_change_activations": 0, "returned_to_hand": 0, "red_girazon_entries": 0, "errors": 0}
    for game_index in range(games):
        try:
            events = _run_game(game_index)
        except Exception:
            summary["errors"] += 1
            continue
        summary["revolution_change_activations"] += sum(1 for event in events if event["revolution_change"])
        summary["returned_to_hand"] += sum(1 for event in events if event["returned_to_hand"])
        summary["red_girazon_entries"] += sum(1 for event in events if event["red_girazon_entry"])
    return summary


def _run_game(game_index: int) -> list[dict[str, Any]]:
    deck0 = revolution_change_runtime_test_deck(base_id=230_000 + game_index * 1_000)
    deck1 = revolution_change_runtime_test_deck(base_id=240_000 + game_index * 1_000)
    env = Env(deck0=deck0, deck1=deck1, config=EnvConfig(seed=51_000 + game_index, max_turns=120))
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
        events.append(_event(info, before, _zone_counts(env)))
        steps += 1
    return events


def _event(info: dict[str, Any], before: int, after: int) -> dict[str, Any]:
    return {
        "revolution_change": bool(info.get("revolution_change")),
        "returned_to_hand": bool(info.get("revolution_change_returned_card_name")),
        "red_girazon_entry": info.get("revolution_change_card_name") == "轟く革命 レッドギラゾーン",
        "zone_count_consistency": before == after,
    }


def _zone_counts(env: Env) -> int:
    assert env.state is not None
    return sum(
        len(player.deck) + len(player.hand) + len(player.mana) + len(player.battle_zone) + len(player.graveyard) + len(player.shields)
        for player in env.state.players
    )


if __name__ == "__main__":
    main()
