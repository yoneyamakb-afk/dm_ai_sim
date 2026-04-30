from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

from dm_ai_sim.actions import Action, ActionType
from dm_ai_sim.agents.heuristic_agent import HeuristicAgent
from dm_ai_sim.env import Env, EnvConfig
from dm_ai_sim.gstrike_runtime import gstrike_runtime_test_deck


LOG_PATH = Path("logs") / "gstrike_analysis.jsonl"


def main(games: int | None = None, output_path: Path = LOG_PATH) -> None:
    game_count = games if games is not None else int(os.environ.get("DM_ANALYZE_GSTRIKE_GAMES", "20"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    records = [analyze_game(game_index) for game_index in range(game_count)]
    with output_path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")

    events = [event for record in records for event in record["events"]]
    targets = Counter(event["g_strike_target_name"] for event in events if event["g_strike_target_name"])
    print(f"wrote {len(records)} games to {output_path}")
    print(f"g_strike_activations: {sum(1 for event in events if event['g_strike_activated'])}")
    print(f"attacks_prevented: {sum(1 for event in events if event['target_attack_removed_from_legal_actions'])}")
    print(f"target_selection_counts: {dict(sorted(targets.items()))}")
    print(f"g_strike_cards_added_to_hand: {sum(1 for event in events if event['card_added_to_hand'])}")
    print(f"errors: {sum(1 for record in records if record['error'])}")


def analyze_game(game_index: int) -> dict[str, Any]:
    deck0 = gstrike_runtime_test_deck(base_id=200_000 + game_index * 1_000)
    deck1 = gstrike_runtime_test_deck(base_id=210_000 + game_index * 1_000)
    env = Env(deck0=deck0, deck1=deck1, config=EnvConfig(seed=42_000 + game_index, max_turns=120))
    env.reset()
    agents = [HeuristicAgent(), HeuristicAgent()]
    events: list[dict[str, Any]] = []
    done = False
    steps = 0
    error = False
    while not done and steps < 1000:
        observation = env.get_observation()
        action = agents[observation["current_player"]].act(env.legal_actions(), observation)
        _obs, _reward, done, info = env.step(action)
        events.append(_event(env, observation, action, info))
        error = error or bool(env.validate_invariants())
        steps += 1
    return {"game": game_index, "error": error, "events": events}


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
        "turn": observation["turn_number"],
        "player": observation["current_player"],
        "shield_broken": bool(info.get("shield_broken")),
        "g_strike_activated": bool(info.get("g_strike_activated")),
        "g_strike_card_name": info.get("g_strike_card_name"),
        "g_strike_target_name": info.get("g_strike_target_name"),
        "target_was_attack_capable": bool(info.get("g_strike_prevented_attack")),
        "target_attack_removed_from_legal_actions": removed,
        "card_added_to_hand": bool(info.get("g_strike_activated")) and _any_hand_has(env, info.get("g_strike_card_name")),
        "winner": info.get("winner"),
    }


def _any_hand_has(env: Env, card_name: str | None) -> bool:
    if card_name is None or env.state is None:
        return False
    return any(card.name == card_name for player in env.state.players for card in player.hand)


if __name__ == "__main__":
    main()
