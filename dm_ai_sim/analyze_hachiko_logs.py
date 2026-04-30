from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dm_ai_sim.actions import Action, ActionType
from dm_ai_sim.agents.heuristic_agent import HeuristicAgent
from dm_ai_sim.env import Env, EnvConfig
from dm_ai_sim.hachiko_runtime import hachiko_runtime_test_deck


LOG_PATH = Path("logs") / "hachiko_analysis.jsonl"


def main(games: int | None = None, output_path: Path = LOG_PATH) -> None:
    game_count = games if games is not None else int(os.environ.get("DM_ANALYZE_HACHIKO_GAMES", "20"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    records = [analyze_game(game_index) for game_index in range(game_count)]
    with output_path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")

    events = [event for record in records for event in record["events"]]
    print(f"wrote {len(records)} games to {output_path}")
    print(f"hachiko_summons: {sum(1 for event in events if event['action'] == 'SUMMON' and event['summoned_card'] == '特攻の忠剣ハチ公')}")
    print(f"speed_attacker_attacks: {sum(1 for event in events if event['speed_attacker_attack'])}")
    print(f"gachinko_judges: {sum(1 for event in events if event['gachinko_judge'])}")
    print(f"gachinko_wins: {sum(1 for event in events if event['gachinko_won'])}")
    print(f"same_name_summons: {sum(1 for event in events if event['same_name_summoned'])}")
    print(f"post_summon_attack_chains: {sum(record['post_summon_attack_chains'] for record in records)}")
    print(f"hachiko_wins: {sum(1 for record in records if record['hachiko_win'])}")


def analyze_game(game_index: int) -> dict[str, Any]:
    deck0 = hachiko_runtime_test_deck(base_id=80_000 + game_index * 1_000)
    deck1 = hachiko_runtime_test_deck(base_id=90_000 + game_index * 1_000)
    env = Env(deck0=deck0, deck1=deck1, config=EnvConfig(seed=25_000 + game_index, max_turns=120))
    env.reset()
    agents = [HeuristicAgent(), HeuristicAgent()]
    events: list[dict[str, Any]] = []
    done = False
    steps = 0
    while not done and steps < 1000:
        observation = env.get_observation()
        action = agents[observation["current_player"]].act(env.legal_actions(), observation)
        before_battle = len(observation["self"]["battle_zone"])
        _obs, _reward, done, info = env.step(action)
        events.append(_event(observation, action, info, before_battle))
        steps += 1

    winner = env.state.winner if env.state is not None else None
    return {
        "game": game_index,
        "winner": winner,
        "hachiko_win": winner is not None and _winner_used_hachiko(events, winner),
        "turns": env.state.turn_number if env.state is not None else None,
        "steps": steps,
        "post_summon_attack_chains": _post_summon_attack_chains(events),
        "events": events,
    }


def _event(observation: dict[str, Any], action: Action, info: dict[str, Any], before_battle: int) -> dict[str, Any]:
    player = observation["current_player"]
    hachiko_attacked = False
    speed_attacker_attack = False
    summoned_card = None
    if action.type == ActionType.SUMMON:
        summoned_card = observation["self"]["hand"][action.card_index]["name"]
    if action.type in {ActionType.ATTACK_CREATURE, ActionType.ATTACK_SHIELD, ActionType.ATTACK_PLAYER}:
        attacker = observation["self"]["battle_zone"][action.attacker_index]
        card = attacker["card"]
        hachiko_attacked = card["name"] == "特攻の忠剣ハチ公"
        speed_attacker_attack = hachiko_attacked and attacker["summoned_turn"] == observation["turn_number"]
    return {
        "turn": observation["turn_number"],
        "player": player,
        "action": action.type.value,
        "summoned_card": summoned_card,
        "hachiko_attacked": hachiko_attacked,
        "speed_attacker_attack": speed_attacker_attack,
        "gachinko_judge": bool(info.get("gachinko_judge", False)),
        "gachinko_won": bool(info.get("gachinko_won", False)),
        "same_name_summoned": bool(info.get("same_name_summoned", False)),
        "same_name_summoned_card": info.get("same_name_summoned_card"),
        "battle_zone_count": before_battle + (1 if info.get("same_name_summoned") else 0),
        "shield_counts": [observation["self"]["shield_count"], observation["opponent"]["shield_count"]],
        "winner": info.get("winner"),
    }


def _post_summon_attack_chains(events: list[dict[str, Any]]) -> int:
    chains = 0
    pending: dict[tuple[int, int], int] = {}
    for event in events:
        key = (event["player"], event["turn"])
        if event["same_name_summoned"]:
            pending[key] = pending.get(key, 0) + 1
        elif event["speed_attacker_attack"] and pending.get(key, 0) > 0:
            chains += 1
            pending[key] -= 1
    return chains


def _winner_used_hachiko(events: list[dict[str, Any]], winner: int) -> bool:
    return any(event["player"] == winner and event["hachiko_attacked"] for event in events)


if __name__ == "__main__":
    main()
