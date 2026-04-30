from __future__ import annotations

import os
from typing import Any

from dm_ai_sim.actions import Action, ActionType
from dm_ai_sim.agents.heuristic_agent import HeuristicAgent
from dm_ai_sim.agents.random_agent import RandomAgent
from dm_ai_sim.env import Env, EnvConfig
from dm_ai_sim.twinpact_runtime import twinpact_runtime_test_deck


def main(games: int | None = None) -> None:
    game_count = games if games is not None else int(os.environ.get("DM_EVALUATE_TWINPACT_GAMES", "20"))
    summary = evaluate_games(game_count)
    for key in ("games", "top_side_summons", "bottom_side_casts", "mana_charges", "graveyard_moves", "errors"):
        print(f"{key}: {summary[key]}")


def evaluate_games(games: int) -> dict[str, int]:
    summary = {
        "games": games,
        "top_side_summons": 0,
        "bottom_side_casts": 0,
        "mana_charges": 0,
        "graveyard_moves": 0,
        "errors": 0,
    }
    for game_index in range(games):
        try:
            events = _run_game(game_index)
        except Exception:
            summary["errors"] += 1
            continue
        summary["top_side_summons"] += sum(1 for event in events if event["used_as_creature"])
        summary["bottom_side_casts"] += sum(1 for event in events if event["used_as_spell"])
        summary["mana_charges"] += sum(1 for event in events if event["mana_charged"])
        summary["graveyard_moves"] += sum(1 for event in events if event["moved_to_graveyard"])
    return summary


def _run_game(game_index: int) -> list[dict[str, Any]]:
    deck0 = twinpact_runtime_test_deck(base_id=130_000 + game_index * 1_000)
    deck1 = twinpact_runtime_test_deck(base_id=140_000 + game_index * 1_000)
    env = Env(deck0=deck0, deck1=deck1, config=EnvConfig(seed=31_000 + game_index, max_turns=120))
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
        events.append(_event(observation, action, info, before, _zone_counts(env)))
        steps += 1
    return events


def _event(observation: dict[str, Any], action: Action, info: dict[str, Any], before: int, after: int) -> dict[str, Any]:
    card_name = None
    if action.type in {ActionType.CHARGE_MANA, ActionType.SUMMON} and action.card_index is not None:
        card_name = observation["self"]["hand"][action.card_index]["name"]
    if action.type == ActionType.CAST_SPELL:
        index = action.hand_index if action.hand_index is not None else action.card_index
        if index is not None:
            card_name = observation["self"]["hand"][index]["name"]
    return {
        "card_name": card_name,
        "side_used": info.get("side_used"),
        "used_as_creature": action.type == ActionType.SUMMON and info.get("side_used") == "top",
        "used_as_spell": action.type == ActionType.CAST_SPELL and info.get("side_used") == "bottom",
        "mana_charged": action.type == ActionType.CHARGE_MANA and _is_twinpact_hand_card(observation, action.card_index),
        "moved_to_graveyard": action.type == ActionType.CAST_SPELL and info.get("side_used") == "bottom",
        "zone_count_consistency": before == after,
    }


def _is_twinpact_hand_card(observation: dict[str, Any], index: int | None) -> bool:
    return index is not None and bool(observation["self"]["hand"][index].get("is_twinpact"))


def _zone_counts(env: Env) -> int:
    assert env.state is not None
    total = 0
    for player in env.state.players:
        total += len(player.deck)
        total += len(player.hand)
        total += len(player.mana)
        total += len(player.battle_zone)
        total += len(player.graveyard)
        total += len(player.shields)
    return total


if __name__ == "__main__":
    main()
