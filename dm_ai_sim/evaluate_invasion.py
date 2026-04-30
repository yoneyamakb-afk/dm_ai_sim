from __future__ import annotations

import os
from typing import Any

from dm_ai_sim.agents.heuristic_agent import HeuristicAgent
from dm_ai_sim.agents.random_agent import RandomAgent
from dm_ai_sim.env import Env, EnvConfig
from dm_ai_sim.invasion_runtime import invasion_runtime_test_deck


def main(games: int | None = None) -> None:
    game_count = games if games is not None else int(os.environ.get("DM_EVALUATE_INVASION_GAMES", "20"))
    summary = evaluate_games(game_count)
    for key in ("games", "invasion_activations", "red_zone_z_entries", "evolution_sources_total", "errors"):
        print(f"{key}: {summary[key]}")


def evaluate_games(games: int) -> dict[str, int]:
    summary = {"games": games, "invasion_activations": 0, "red_zone_z_entries": 0, "evolution_sources_total": 0, "errors": 0}
    for game_index in range(games):
        try:
            events = _run_game(game_index)
        except Exception:
            summary["errors"] += 1
            continue
        summary["invasion_activations"] += sum(1 for event in events if event["invasion"])
        summary["red_zone_z_entries"] += sum(1 for event in events if event["red_zone_z_entry"])
        summary["evolution_sources_total"] += sum(event["evolution_source_count"] for event in events)
        summary["errors"] += sum(1 for event in events if not event["zone_count_consistency"])
    return summary


def _run_game(game_index: int) -> list[dict[str, Any]]:
    deck0 = invasion_runtime_test_deck(base_id=280_000 + game_index * 1_000)
    deck1 = invasion_runtime_test_deck(base_id=290_000 + game_index * 1_000)
    env = Env(deck0=deck0, deck1=deck1, config=EnvConfig(seed=53_000 + game_index, max_turns=120))
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
        events.append(_event(env, observation["current_player"], info, before, after))
        steps += 1
    return events


def _event(env: Env, player_id: int, info: dict[str, Any], before: int, after: int) -> dict[str, Any]:
    evolution_source_count = 0
    if info.get("invasion") and env.state is not None:
        player = env.state.players[player_id]
        if player.battle_zone:
            evolution_source_count = len(player.battle_zone[-1].evolution_sources)
    return {
        "invasion": bool(info.get("invasion")),
        "red_zone_z_entry": info.get("invasion_card_name") == "熱き侵略 レッドゾーンZ",
        "evolution_source_count": evolution_source_count,
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
