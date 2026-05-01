from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dm_ai_sim.actions import Action, ActionType
from dm_ai_sim.agents.heuristic_agent import HeuristicAgent
from dm_ai_sim.double_breaker_runtime import double_breaker_runtime_test_deck
from dm_ai_sim.env import Env, EnvConfig


LOG_PATH = Path("logs") / "double_breaker_analysis.jsonl"


def main(games: int | None = None, output_path: Path = LOG_PATH) -> None:
    game_count = games if games is not None else int(os.environ.get("DM_ANALYZE_DOUBLE_BREAKER_GAMES", "20"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    records = [analyze_game(game_index) for game_index in range(game_count)]
    with output_path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")

    events = [event for record in records for event in record["events"]]
    print(f"wrote {len(records)} games to {output_path}")
    print(f"double_breaker_attacks: {sum(1 for event in events if event['double_breaker_attack'])}")
    print(f"total_shields_broken: {sum(event['shields_broken_count'] for event in events)}")
    print(f"multi_break_batches: {sum(1 for event in events if event['multi_break'])}")
    print(f"trigger_activations: {sum(event['trigger_activations'] for event in events)}")
    print(f"g_strike_activations: {sum(event['g_strike_activations'] for event in events)}")
    print(f"attacker_destroyed_by_trigger: {sum(1 for event in events if event['attacker_destroyed_by_trigger'])}")
    print(f"errors: {sum(1 for record in records if record['error'])}")


def analyze_game(game_index: int) -> dict[str, Any]:
    deck0 = double_breaker_runtime_test_deck(base_id=350_000 + game_index * 1_000)
    deck1 = double_breaker_runtime_test_deck(base_id=360_000 + game_index * 1_000)
    env = Env(deck0=deck0, deck1=deck1, config=EnvConfig(seed=56_000 + game_index, max_turns=120))
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
        events.append(_event(observation, action, info))
        error = error or bool(env.validate_invariants())
        steps += 1
    return {"game": game_index, "error": error, "events": events}


def _event(observation: dict[str, Any], action: Action, info: dict[str, Any]) -> dict[str, Any]:
    results = _shield_break_results(info)
    breaker_count = int(info.get("breaker_count", 1))
    first_break = results[0] if results else {}
    return {
        "turn": observation["turn_number"],
        "player": observation["current_player"],
        "action": _action_dict(action),
        "attacker_name": _attacker_name(observation, action),
        "breaker_count": breaker_count,
        "double_breaker_attack": action.type == ActionType.ATTACK_SHIELD and breaker_count >= 2,
        "shields_to_break": int(info.get("shields_to_break", 0)),
        "shields_broken_count": int(info.get("shields_broken_count", 0)),
        "multi_break": bool(info.get("multi_break")),
        "batch_id": first_break.get("batch_id"),
        "shield_break_results": results,
        "trigger_activations": sum(1 for result in results if result.get("trigger_activated")),
        "g_strike_activations": sum(1 for result in results if result.get("g_strike_activated")),
        "attacker_destroyed_by_trigger": bool(info.get("attacker_destroyed_by_trigger")),
        "winner": info.get("winner"),
    }


def _action_dict(action: Action) -> dict[str, Any]:
    values: dict[str, Any] = {"type": action.type.value}
    for field in ("card_index", "hand_index", "attacker_index", "target_index", "blocker_index"):
        value = getattr(action, field)
        if value is not None:
            values[field] = value
    if action.side is not None:
        values["side"] = action.side
    return values


def _attacker_name(observation: dict[str, Any], action: Action) -> str | None:
    if action.type in {ActionType.ATTACK_CREATURE, ActionType.ATTACK_PLAYER, ActionType.ATTACK_SHIELD}:
        return _battle_zone_name(observation["self"]["battle_zone"], action.attacker_index)
    if action.type == ActionType.DECLINE_BLOCK:
        pending = observation.get("pending_attack")
        if pending is None:
            return None
        return _battle_zone_name(observation["opponent"]["battle_zone"], pending.get("attacker_index"))
    return None


def _battle_zone_name(battle_zone: list[dict[str, Any]], index: int | None) -> str | None:
    if index is None or index < 0 or index >= len(battle_zone):
        return None
    return battle_zone[index]["card"]["name"]


def _shield_break_results(info: dict[str, Any]) -> list[dict[str, Any]]:
    results = info.get("shield_break_results")
    if not isinstance(results, list):
        return []
    return [result for result in results if isinstance(result, dict)]


if __name__ == "__main__":
    main()
