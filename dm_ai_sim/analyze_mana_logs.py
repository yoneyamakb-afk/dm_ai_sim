from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dm_ai_sim.actions import Action, ActionType
from dm_ai_sim.agents.heuristic_agent import HeuristicAgent
from dm_ai_sim.mana import civilization_counts, multicolor_mana_count, playable_hand_counts, untapped_mana_count
from dm_ai_sim.selfplay_env import DuelMastersSelfPlayEnv, SelfPlayConfig


LOG_PATH = Path("logs") / "mana_analysis.jsonl"


def main(games: int = 20, output_path: Path = LOG_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    records = [analyze_game(game_index) for game_index in range(games)]
    with output_path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"wrote {len(records)} games to {output_path}")
    for tag in sorted({tag for record in records for tag in record["tags"]}):
        count = sum(1 for record in records if tag in record["tags"])
        print(f"{tag}: {count}")


def analyze_game(game_index: int) -> dict[str, Any]:
    env = DuelMastersSelfPlayEnv(
        SelfPlayConfig(
            seed=22000 + game_index,
            fixed_opponent="heuristic",
            include_heuristic_opponent=False,
            include_random_opponent=False,
            intermediate_rewards=False,
            max_turns=120,
        )
    )
    env.reset()
    agents = [HeuristicAgent(), HeuristicAgent()]
    events: list[dict[str, Any]] = []
    done = False
    step_count = 0
    while not done and step_count < 1000:
        state = env.base_env.state
        if state is None:
            break
        player_id = state.current_player
        before = _mana_snapshot(env, player_id)
        observation = env.base_env.get_observation()
        legal_actions = env.base_env.legal_actions()
        action = agents[player_id].act(legal_actions, observation)
        _obs, _reward, done, info = env.base_env.step(action)
        after = _mana_snapshot(env, player_id)
        events.append(_event(observation, action, legal_actions, info, before, after))
        step_count += 1

    state = env.base_env.state
    winner = state.winner if state is not None else None
    return {
        "game": game_index,
        "winner": winner,
        "turns": state.turn_number if state is not None else None,
        "steps": step_count,
        "tags": _classify_tags(events),
        "events": events,
    }


def _mana_snapshot(env: DuelMastersSelfPlayEnv, player_id: int) -> dict[str, Any]:
    state = env.base_env.state
    assert state is not None
    player = state.players[player_id]
    counts = playable_hand_counts(player)
    return {
        "mana_count": len(player.mana),
        "untapped_mana_count": untapped_mana_count(player),
        "civilization_counts": civilization_counts(player.mana),
        "untapped_civilization_counts": civilization_counts(player.mana, untapped_only=True),
        "multicolor_mana_count": multicolor_mana_count(player.mana),
        "playable_hand_count": counts["playable"],
        "unplayable_due_to_civilization_count": counts["civilization_shortfall"],
        "unplayable_due_to_cost_count": counts["cost_shortfall"],
    }


def _event(
    observation: dict[str, Any],
    action: Action,
    legal_actions: list[Action],
    info: dict[str, Any],
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, Any]:
    return {
        "turn": observation["turn_number"],
        "player": observation["current_player"],
        "mana_count": before["mana_count"],
        "untapped_mana_count": before["untapped_mana_count"],
        "civilization_counts": before["civilization_counts"],
        "untapped_civilization_counts": before["untapped_civilization_counts"],
        "multicolor_mana_count": before["multicolor_mana_count"],
        "playable_hand_count": before["playable_hand_count"],
        "unplayable_due_to_civilization_count": before["unplayable_due_to_civilization_count"],
        "unplayable_due_to_cost_count": before["unplayable_due_to_cost_count"],
        "charged_card": info.get("charged_card"),
        "charged_card_civilizations": info.get("charged_card_civilizations"),
        "charged_card_enters_tapped": info.get("charged_card_enters_tapped", False),
        "action": _action_dict(action),
        "legal_summon_available": any(candidate.type == ActionType.SUMMON for candidate in legal_actions),
        "legal_cast_spell_available": any(candidate.type == ActionType.CAST_SPELL for candidate in legal_actions),
        "winner": info.get("winner"),
        "after_playable_hand_count": after["playable_hand_count"],
    }


def _action_dict(action: Action) -> dict[str, Any]:
    values: dict[str, Any] = {"type": action.type.value}
    for field in ("card_index", "hand_index", "attacker_index", "target_index", "blocker_index"):
        value = getattr(action, field)
        if value is not None:
            values[field] = value
    return values


def _classify_tags(events: list[dict[str, Any]]) -> list[str]:
    tags: set[str] = set()
    if any(event["unplayable_due_to_civilization_count"] > 0 and event["playable_hand_count"] == 0 for event in events):
        tags.add("色事故")
    if any(event["unplayable_due_to_cost_count"] > 0 and event["playable_hand_count"] == 0 for event in events):
        tags.add("コスト不足")
    if any(event["charged_card_enters_tapped"] and event["after_playable_hand_count"] == 0 for event in events):
        tags.add("多色タップインで動けなかった")
    if any(event["turn"] == 2 and event["player"] == 0 and event["playable_hand_count"] == 0 for event in events):
        tags.add("2ターン目初動失敗")
    if any(event["turn"] == 3 and event["player"] == 0 and event["playable_hand_count"] == 0 for event in events):
        tags.add("3ターン目初動失敗")
    if any(
        event["unplayable_due_to_civilization_count"] > 0 and not event["legal_cast_spell_available"]
        for event in events
    ):
        tags.add("必要文明不足でCAST_SPELL不可")
    if any(
        event["unplayable_due_to_civilization_count"] > 0 and not event["legal_summon_available"]
        for event in events
    ):
        tags.add("必要文明不足でSUMMON不可")
    return sorted(tags)


if __name__ == "__main__":
    main()

