from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dm_ai_sim.action_encoder import decode_action
from dm_ai_sim.actions import Action
from dm_ai_sim.agents.heuristic_agent import HeuristicAgent
from dm_ai_sim.agents.selfplay_optional_block_finetuned_agent import SelfPlayOptionalBlockFineTunedAgent
from dm_ai_sim.selfplay_env import DuelMastersSelfPlayEnv, SelfPlayConfig


LOG_PATH = Path("logs") / "trigger_analysis.jsonl"


def main(games: int = 20, output_path: Path = LOG_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    records = [analyze_game(game_index) for game_index in range(games)]
    with output_path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")

    trigger_count = sum(1 for record in records for event in record["events"] if event["trigger_activated"])
    destroy_count = sum(
        1 for record in records for event in record["events"] if event["attacker_destroyed_by_trigger"]
    )
    print(f"wrote {len(records)} games to {output_path}")
    print(f"trigger activations: {trigger_count}")
    print(f"attackers destroyed by trigger: {destroy_count}")


def analyze_game(game_index: int) -> dict[str, Any]:
    env = DuelMastersSelfPlayEnv(
        SelfPlayConfig(
            seed=12000 + game_index,
            fixed_opponent="heuristic",
            include_heuristic_opponent=False,
            include_random_opponent=False,
            intermediate_rewards=False,
            max_turns=120,
        )
    )
    env.reset()
    learner = SelfPlayOptionalBlockFineTunedAgent()
    fallback = HeuristicAgent()
    opponent = HeuristicAgent()
    events: list[dict[str, Any]] = []
    done = False
    step_count = 0

    while not done and step_count < 1000:
        state = env.base_env.state
        if state is None:
            break
        before = env.base_env.get_observation()
        shield_counts_before = [len(player.shields) for player in state.players]

        if state.current_player == 0 and learner.is_available:
            action_id = learner.act(env, player_id=0)
            action = decode_action(action_id)
            _obs, _reward, done, info = env.base_env.step_action_id(action_id)
        else:
            agent = opponent if state.current_player == 1 else fallback
            action = agent.act(env.base_env.legal_actions(), before)
            _obs, _reward, done, info = env.base_env.step(action)

        shield_counts_after = [len(player.shields) for player in state.players]
        events.append(_event(before, action, info, shield_counts_before, shield_counts_after))
        step_count += 1

    state = env.base_env.state
    return {
        "game": game_index,
        "winner": state.winner if state is not None else None,
        "turns": state.turn_number if state is not None else None,
        "steps": step_count,
        "tags": _classify_trigger_tags(events, state.winner if state is not None else None),
        "events": events,
    }


def _event(
    observation: dict[str, Any],
    action: Action,
    info: dict[str, Any],
    shield_counts_before: list[int],
    shield_counts_after: list[int],
) -> dict[str, Any]:
    attacker_player = observation["current_player"]
    defender_player = 1 - attacker_player
    return {
        "turn": observation["turn_number"],
        "attacker_player": attacker_player,
        "defender_player": defender_player,
        "action": _action_dict(action),
        "shield_broken": bool(info.get("shield_broken", False)),
        "broken_shield_card": info.get("broken_shield_card"),
        "trigger_activated": bool(info.get("trigger_activated", False)),
        "trigger_effect": info.get("trigger_effect"),
        "attacker_destroyed_by_trigger": bool(info.get("attacker_destroyed_by_trigger", False)),
        "shield_count_before": shield_counts_before[defender_player],
        "shield_count_after": shield_counts_after[defender_player],
        "winner": info.get("winner"),
    }


def _classify_trigger_tags(events: list[dict[str, Any]], winner: int | None) -> list[str]:
    tags: set[str] = set()
    learner_events = [event for event in events if event["attacker_player"] == 0]
    trigger_events = [event for event in events if event["trigger_activated"]]

    if any(
        event["action"]["type"] == "END_ATTACK"
        and event["shield_count_before"] == 0
        for event in learner_events
    ):
        tags.add("リーサル可能だったか")
        tags.add("リーサルを逃したか")
    if trigger_events:
        tags.add("trigger_activated後に勝敗が変わった可能性があるか")
    if any(
        event["trigger_effect"] == "DESTROY_ATTACKER"
        and event["attacker_destroyed_by_trigger"]
        for event in trigger_events
    ):
        tags.add("DESTROY_ATTACKERで主要アタッカーを失ったか")
    if any(event["trigger_effect"] == "GAIN_SHIELD" for event in trigger_events):
        tags.add("GAIN_SHIELDでリーサルがずれたか")
    if any(event["trigger_effect"] == "SUMMON_SELF" for event in trigger_events):
        tags.add("SUMMON_SELFで盤面が逆転したか")
    if any(event["trigger_effect"] == "DRAW_1" for event in trigger_events):
        tags.add("DRAW_1で防御側の手札差が広がったか")
    if any(
        event["action"]["type"] == "END_ATTACK"
        and event["shield_count_before"] > 0
        for event in learner_events
    ):
        tags.add("S・トリガーを恐れて攻撃しなかった可能性があるか")
    if any(
        event["shield_broken"]
        and event["trigger_activated"]
        and event["attacker_player"] == 0
        for event in events
    ):
        tags.add("S・トリガーを無視して無理攻めした可能性があるか")
    if winner == 0 and trigger_events:
        tags.add("S・トリガー後も勝利したか")
    return sorted(tags)


def _action_dict(action: Action) -> dict[str, Any]:
    values: dict[str, Any] = {"type": action.type.value}
    for field in ("card_index", "attacker_index", "target_index", "blocker_index"):
        value = getattr(action, field)
        if value is not None:
            values[field] = value
    return values


if __name__ == "__main__":
    main()
