from __future__ import annotations

import os
from typing import Any

from dm_ai_sim.actions import Action, ActionType
from dm_ai_sim.agents.heuristic_agent import HeuristicAgent
from dm_ai_sim.agents.random_agent import RandomAgent
from dm_ai_sim.env import Env, EnvConfig
from dm_ai_sim.hachiko_runtime import hachiko_runtime_test_deck


def main(games: int | None = None) -> None:
    game_count = games if games is not None else int(os.environ.get("DM_EVALUATE_HACHIKO_GAMES", "20"))
    summary = evaluate_games(game_count)
    for key in ("games", "hachiko_attacks", "gachinko_judges", "gachinko_wins", "same_name_summons", "errors"):
        print(f"{key}: {summary[key]}")


def evaluate_games(games: int) -> dict[str, int]:
    summary = {
        "games": games,
        "hachiko_attacks": 0,
        "gachinko_judges": 0,
        "gachinko_wins": 0,
        "same_name_summons": 0,
        "errors": 0,
    }
    for game_index in range(games):
        try:
            events = _run_game(game_index)
        except Exception:
            summary["errors"] += 1
            continue
        summary["hachiko_attacks"] += sum(1 for event in events if event["hachiko_attacked"])
        summary["gachinko_judges"] += sum(1 for event in events if event["gachinko_judge"])
        summary["gachinko_wins"] += sum(1 for event in events if event["gachinko_won"])
        summary["same_name_summons"] += sum(1 for event in events if event["same_name_summoned"])
    return summary


def _run_game(game_index: int) -> list[dict[str, Any]]:
    deck0 = hachiko_runtime_test_deck(base_id=60_000 + game_index * 1_000)
    deck1 = hachiko_runtime_test_deck(base_id=70_000 + game_index * 1_000)
    env = Env(deck0=deck0, deck1=deck1, config=EnvConfig(seed=24_000 + game_index, max_turns=120))
    env.reset()
    agents = [HeuristicAgent(), RandomAgent(seed=game_index)]
    events: list[dict[str, Any]] = []
    done = False
    steps = 0
    while not done and steps < 1000:
        observation = env.get_observation()
        action = agents[observation["current_player"]].act(env.legal_actions(), observation)
        _obs, _reward, done, info = env.step(action)
        events.append(_event(observation, action, info))
        steps += 1
    return events


def _event(observation: dict[str, Any], action: Action, info: dict[str, Any]) -> dict[str, Any]:
    hachiko_attacked = False
    speed_attacker_attack = False
    if action.type in {ActionType.ATTACK_CREATURE, ActionType.ATTACK_SHIELD, ActionType.ATTACK_PLAYER}:
        attacker = observation["self"]["battle_zone"][action.attacker_index]
        card = attacker["card"]
        hachiko_attacked = card["name"] == "特攻の忠剣ハチ公"
        speed_attacker_attack = hachiko_attacked and attacker["summoned_turn"] == observation["turn_number"]
    return {
        "hachiko_attacked": hachiko_attacked,
        "speed_attacker_attack": speed_attacker_attack,
        "gachinko_judge": bool(info.get("gachinko_judge", False)),
        "gachinko_won": bool(info.get("gachinko_won", False)),
        "same_name_summoned": bool(info.get("same_name_summoned", False)),
    }


if __name__ == "__main__":
    main()
