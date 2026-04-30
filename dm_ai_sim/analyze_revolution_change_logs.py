from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

from dm_ai_sim.actions import Action, ActionType
from dm_ai_sim.agents.heuristic_agent import HeuristicAgent
from dm_ai_sim.env import Env, EnvConfig
from dm_ai_sim.revolution_change_runtime import revolution_change_runtime_test_deck


LOG_PATH = Path("logs") / "revolution_change_analysis.jsonl"


def main(games: int | None = None, output_path: Path = LOG_PATH) -> None:
    game_count = games if games is not None else int(os.environ.get("DM_ANALYZE_REVOLUTION_CHANGE_GAMES", "20"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    records = [analyze_game(game_index) for game_index in range(game_count)]
    with output_path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")

    events = [event for record in records for event in record["events"]]
    returned = Counter(event["returned_card_name"] for event in events if event["returned_card_name"])
    print(f"wrote {len(records)} games to {output_path}")
    print(f"revolution_change_activations: {sum(1 for event in events if event['revolution_change'])}")
    print(f"returned_cards: {dict(sorted(returned.items()))}")
    print(f"red_girazon_entries: {sum(1 for event in events if event['revolution_change_card_name'] == '轟く革命 レッドギラゾーン')}")
    print(f"attackable_after_change: {sum(1 for event in events if event['revolution_change_card_attackable_after_entering'])}")
    print(f"errors: {sum(1 for record in records if record['error'])}")


def analyze_game(game_index: int) -> dict[str, Any]:
    deck0 = revolution_change_runtime_test_deck(base_id=250_000 + game_index * 1_000)
    deck1 = revolution_change_runtime_test_deck(base_id=260_000 + game_index * 1_000)
    env = Env(deck0=deck0, deck1=deck1, config=EnvConfig(seed=52_000 + game_index, max_turns=120))
    env.reset()
    agents = [HeuristicAgent(), HeuristicAgent()]
    events: list[dict[str, Any]] = []
    done = False
    steps = 0
    error = False
    while not done and steps < 1000:
        observation = env.get_observation()
        action = agents[observation["current_player"]].act(env.legal_actions(), observation)
        before = _snapshot(env, observation["current_player"])
        _obs, _reward, done, info = env.step(action)
        events.append(_event(env, observation, action, info, before, _snapshot(env, observation["current_player"])))
        error = error or bool(env.validate_invariants())
        steps += 1
    return {"game": game_index, "error": error, "events": events}


def _event(env: Env, observation: dict[str, Any], action: Action, info: dict[str, Any], before: dict[str, int], after: dict[str, int]) -> dict[str, Any]:
    attackable_after = False
    if info.get("revolution_change") and env.state is not None:
        player = env.state.players[observation["current_player"]]
        index = len(player.battle_zone) - 1
        attackable_after = any(candidate.attacker_index == index for candidate in env.legal_actions() if candidate.type in {ActionType.ATTACK_CREATURE, ActionType.ATTACK_SHIELD, ActionType.ATTACK_PLAYER})
    return {
        "turn": observation["turn_number"],
        "player": observation["current_player"],
        "action": action.type.value,
        "revolution_change": bool(info.get("revolution_change")),
        "revolution_change_card_name": info.get("revolution_change_card_name"),
        "returned_card_name": info.get("revolution_change_returned_card_name"),
        "battle_zone_count_before": before["battle"],
        "battle_zone_count_after": after["battle"],
        "hand_count_before": before["hand"],
        "hand_count_after": after["hand"],
        "revolution_change_card_attackable_after_entering": attackable_after,
        "winner": info.get("winner"),
    }


def _snapshot(env: Env, player_id: int) -> dict[str, int]:
    assert env.state is not None
    player = env.state.players[player_id]
    return {"hand": len(player.hand), "battle": len(player.battle_zone)}


if __name__ == "__main__":
    main()
