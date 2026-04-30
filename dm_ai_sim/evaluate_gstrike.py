from __future__ import annotations

import os
from typing import Any

from dm_ai_sim.actions import Action, ActionType
from dm_ai_sim.agents.heuristic_agent import HeuristicAgent
from dm_ai_sim.agents.random_agent import RandomAgent
from dm_ai_sim.env import Env, EnvConfig
from dm_ai_sim.gstrike_runtime import gstrike_runtime_test_deck


def main(games: int | None = None) -> None:
    game_count = games if games is not None else int(os.environ.get("DM_EVALUATE_GSTRIKE_GAMES", "20"))
    summary = evaluate_games(game_count)
    for key in ("games", "g_strike_activations", "attacks_prevented", "cards_added_to_hand", "errors"):
        print(f"{key}: {summary[key]}")


def evaluate_games(games: int) -> dict[str, int]:
    summary = {"games": games, "g_strike_activations": 0, "attacks_prevented": 0, "cards_added_to_hand": 0, "errors": 0}
    for game_index in range(games):
        try:
            events = _run_game(game_index)
        except Exception:
            summary["errors"] += 1
            continue
        summary["g_strike_activations"] += sum(1 for event in events if event["g_strike_activated"])
        summary["attacks_prevented"] += sum(1 for event in events if event["target_attack_removed_from_legal_actions"])
        summary["cards_added_to_hand"] += sum(1 for event in events if event["card_added_to_hand"])
    return summary


def _run_game(game_index: int) -> list[dict[str, Any]]:
    deck0 = gstrike_runtime_test_deck(base_id=180_000 + game_index * 1_000)
    deck1 = gstrike_runtime_test_deck(base_id=190_000 + game_index * 1_000)
    env = Env(deck0=deck0, deck1=deck1, config=EnvConfig(seed=41_000 + game_index, max_turns=120))
    env.reset()
    agents = [HeuristicAgent(), RandomAgent(seed=game_index)]
    events: list[dict[str, Any]] = []
    done = False
    steps = 0
    while not done and steps < 1000:
        observation = env.get_observation()
        legal_before = env.legal_actions()
        action = agents[observation["current_player"]].act(legal_before, observation)
        _obs, _reward, done, info = env.step(action)
        events.append(_event(env, observation, action, info))
        steps += 1
    return events


def _event(env: Env, observation: dict[str, Any], action: Action, info: dict[str, Any]) -> dict[str, Any]:
    target_index = info.get("g_strike_target_index")
    removed = False
    if target_index is not None and env.state is not None and env.state.current_player == observation["current_player"]:
        removed = all(
            candidate.attacker_index != target_index
            for candidate in env.legal_actions()
            if candidate.type in {ActionType.ATTACK_CREATURE, ActionType.ATTACK_SHIELD, ActionType.ATTACK_PLAYER}
        )
    return {
        "g_strike_activated": bool(info.get("g_strike_activated")),
        "target_attack_removed_from_legal_actions": removed,
        "card_added_to_hand": bool(info.get("g_strike_activated")) and _defender_hand_has_card(env, info.get("g_strike_card_name")),
    }


def _defender_hand_has_card(env: Env, card_name: str | None) -> bool:
    if card_name is None or env.state is None:
        return False
    return any(card.name == card_name for player in env.state.players for card in player.hand)


if __name__ == "__main__":
    main()
