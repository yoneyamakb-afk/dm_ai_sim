from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dm_ai_sim.actions import Action, ActionType
from dm_ai_sim.agents.heuristic_agent import HeuristicAgent
from dm_ai_sim.selfplay_env import DuelMastersSelfPlayEnv, SelfPlayConfig


LOG_PATH = Path("logs") / "spell_analysis.jsonl"


def main(games: int = 20, output_path: Path = LOG_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    records = [analyze_game(game_index) for game_index in range(games)]
    with output_path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")

    spell_count = sum(1 for record in records for event in record["events"] if event["spell_cast"])
    print(f"wrote {len(records)} games to {output_path}")
    print(f"spell_cast: {spell_count}")
    for tag in sorted({tag for record in records for tag in record["tags"]}):
        count = sum(1 for record in records if tag in record["tags"])
        print(f"{tag}: {count}")


def analyze_game(game_index: int) -> dict[str, Any]:
    env = DuelMastersSelfPlayEnv(
        SelfPlayConfig(
            seed=18000 + game_index,
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
        before = env.base_env.get_observation()
        legal_actions = env.base_env.legal_actions()
        snapshot = _snapshot(env)
        action = agents[state.current_player].act(legal_actions, before)
        _obs, _reward, done, info = env.base_env.step(action)
        events.append(_event(before, action, legal_actions, info, snapshot, _snapshot(env)))
        step_count += 1

    state = env.base_env.state
    winner = state.winner if state is not None else None
    return {
        "game": game_index,
        "winner": winner,
        "turns": state.turn_number if state is not None else None,
        "steps": step_count,
        "tags": _classify_spell_tags(events, winner),
        "events": events,
    }


def _snapshot(env: DuelMastersSelfPlayEnv) -> dict[str, list[int]]:
    state = env.base_env.state
    assert state is not None
    return {
        "hand": [len(player.hand) for player in state.players],
        "mana": [len(player.mana) for player in state.players],
        "shield": [len(player.shields) for player in state.players],
        "battle": [len(player.battle_zone) for player in state.players],
        "blocker": [sum(1 for creature in player.battle_zone if creature.card.blocker) for player in state.players],
        "max_power": [max((creature.card.power for creature in player.battle_zone), default=0) for player in state.players],
    }


def _event(
    observation: dict[str, Any],
    action: Action,
    legal_actions: list[Action],
    info: dict[str, Any],
    before: dict[str, list[int]],
    after: dict[str, list[int]],
) -> dict[str, Any]:
    player = observation["current_player"]
    opponent = 1 - player
    target_power = 0
    target_blocker = False
    if action.target_index is not None:
        creatures = observation["opponent"].get("battle_zone", [])
        if 0 <= action.target_index < len(creatures):
            target = creatures[action.target_index]
            target_power = int(target.get("power", 0))
            target_blocker = bool(target.get("blocker", False))
    return {
        "turn": observation["turn_number"],
        "player": player,
        "action": _action_dict(action),
        "spell_cast": bool(info.get("spell_cast", False)),
        "spell_name": info.get("spell_name"),
        "spell_effect": info.get("spell_effect"),
        "target_index": info.get("spell_target_index"),
        "hand_count_before": before["hand"][player],
        "hand_count_after": after["hand"][player],
        "mana_count_before": before["mana"][player],
        "mana_count_after": after["mana"][player],
        "shield_count_before": before["shield"][player],
        "shield_count_after": after["shield"][player],
        "opponent_battle_zone_before": before["battle"][opponent],
        "opponent_battle_zone_after": after["battle"][opponent],
        "opponent_blocker_count_before": before["blocker"][opponent],
        "opponent_blocker_count_after": after["blocker"][opponent],
        "opponent_max_power_before": before["max_power"][opponent],
        "target_power": target_power,
        "target_blocker": target_blocker,
        "legal_summon_available": any(candidate.type == ActionType.SUMMON for candidate in legal_actions),
        "legal_attack_available": any(
            candidate.type in {ActionType.ATTACK_SHIELD, ActionType.ATTACK_PLAYER, ActionType.ATTACK_CREATURE}
            for candidate in legal_actions
        ),
        "legal_cast_spell_available": any(candidate.type == ActionType.CAST_SPELL for candidate in legal_actions),
        "winner": info.get("winner"),
    }


def _action_dict(action: Action) -> dict[str, Any]:
    values: dict[str, Any] = {"type": action.type.value}
    for field in ("card_index", "hand_index", "attacker_index", "target_index", "blocker_index"):
        value = getattr(action, field)
        if value is not None:
            values[field] = value
    return values


def _classify_spell_tags(events: list[dict[str, Any]], winner: int | None) -> list[str]:
    tags: set[str] = set()
    if any(
        event.get("spell_effect") == "DESTROY_TARGET"
        and event.get("opponent_blocker_count_after", event.get("opponent_battle_zone_after", 0))
        < event.get("opponent_blocker_count_before", event.get("opponent_battle_zone_before", 0))
        for event in events
    ):
        tags.add("DESTROY_TARGETでblockerを処理したか")
    if any(
        event.get("spell_effect") == "DESTROY_TARGET"
        and any(
            later.get("player") == event.get("player")
            and later.get("turn") == event.get("turn")
            and later.get("action", {}).get("type") in {"ATTACK_SHIELD", "ATTACK_PLAYER"}
            for later in events[index + 1 :]
        )
        for index, event in enumerate(events)
    ):
        tags.add("DESTROY_TARGETでリーサルが通ったか")
    if any(
        event.get("spell_effect") == "DESTROY_TARGET"
        and event.get("target_power", 9999) < 3000
        and not event.get("target_blocker", False)
        for event in events
    ):
        tags.add("DESTROY_TARGETで低価値対象を取った可能性")
    if any(event.get("spell_effect") == "DRAW_1" and event.get("hand_count_before", 99) <= 1 and event.get("hand_count_after", 0) > event.get("hand_count_before", 0) for event in events):
        tags.add("DRAW_1で手札切れを回避した")
    if any(
        event.get("spell_effect") == "MANA_BOOST"
        and any(
            later.get("player") == event.get("player")
            and later.get("action", {}).get("type") == "SUMMON"
            and later.get("mana_count_before", 0) >= 5
            for later in events[index + 1 :]
        )
        for index, event in enumerate(events)
    ):
        tags.add("MANA_BOOSTで高コスト召喚に繋がった")
    if any(event.get("spell_effect") == "GAIN_SHIELD" and event.get("shield_count_before", 99) == 0 and event.get("shield_count_after", 0) > 0 for event in events):
        tags.add("GAIN_SHIELDでそのターンの敗北を防いだか")
    if not any(event.get("spell_cast") for event in events) and winner is not None:
        tags.add("呪文を使わずに負けた可能性")
    spell_count = sum(1 for event in events if event.get("spell_cast"))
    summon_count = sum(1 for event in events if event.get("action", {}).get("type") == "SUMMON")
    if spell_count >= summon_count + 2 and winner is not None:
        tags.add("呪文を使いすぎて盤面展開が遅れた可能性")
    if any(event.get("spell_cast") and event.get("legal_summon_available", False) for event in events):
        tags.add("CAST_SPELLより召喚を優先すべきだった可能性")
    if any(event.get("spell_cast") and event.get("legal_attack_available", False) for event in events):
        tags.add("CAST_SPELLより攻撃を優先すべきだった可能性")
    return sorted(tags)


if __name__ == "__main__":
    main()
