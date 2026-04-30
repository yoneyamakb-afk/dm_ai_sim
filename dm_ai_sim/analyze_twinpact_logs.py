from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dm_ai_sim.actions import Action, ActionType
from dm_ai_sim.agents.heuristic_agent import HeuristicAgent
from dm_ai_sim.agents.random_agent import RandomAgent
from dm_ai_sim.env import Env, EnvConfig
from dm_ai_sim.twinpact_runtime import twinpact_runtime_test_deck


LOG_PATH = Path("logs") / "twinpact_analysis.jsonl"


def main(games: int | None = None, output_path: Path = LOG_PATH) -> None:
    game_count = games if games is not None else int(os.environ.get("DM_ANALYZE_TWINPACT_GAMES", "20"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    records = [analyze_game(game_index) for game_index in range(game_count)]
    with output_path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")

    events = [event for record in records for event in record["events"]]
    print(f"wrote {len(records)} games to {output_path}")
    print(f"twinpact_cards_drawn: {sum(record['twinpact_cards_drawn'] for record in records)}")
    print(f"top_side_summoned: {sum(1 for event in events if event['used_as_creature'])}")
    print(f"bottom_side_cast: {sum(1 for event in events if event['used_as_spell'])}")
    print(f"charged_to_mana: {sum(1 for event in events if event['mana_charged'])}")
    print(f"moved_to_graveyard: {sum(1 for event in events if event['moved_to_graveyard'])}")
    print(f"errors: {sum(1 for record in records if not all(event['zone_count_consistency'] for event in record['events']))}")


def analyze_game(game_index: int) -> dict[str, Any]:
    deck0 = twinpact_runtime_test_deck(base_id=150_000 + game_index * 1_000)
    deck1 = twinpact_runtime_test_deck(base_id=160_000 + game_index * 1_000)
    env = Env(deck0=deck0, deck1=deck1, config=EnvConfig(seed=32_000 + game_index, max_turns=120))
    env.reset()
    agents = [HeuristicAgent(), RandomAgent(seed=game_index)]
    events: list[dict[str, Any]] = []
    drawn = 0
    done = False
    steps = 0
    while not done and steps < 1000:
        observation = env.get_observation()
        drawn += sum(1 for card in observation["self"]["hand"] if card.get("is_twinpact"))
        action = agents[observation["current_player"]].act(env.legal_actions(), observation)
        before = _zone_counts(env)
        _obs, _reward, done, info = env.step(action)
        events.append(_event(observation, action, info, before, _zone_counts(env)))
        steps += 1
    winner = env.state.winner if env.state is not None else None
    return {"game": game_index, "winner": winner, "twinpact_cards_drawn": drawn, "events": events}


def _event(observation: dict[str, Any], action: Action, info: dict[str, Any], before: int, after: int) -> dict[str, Any]:
    card = _action_card(observation, action)
    used_as_creature = action.type == ActionType.SUMMON and info.get("side_used") == "top"
    used_as_spell = action.type == ActionType.CAST_SPELL and info.get("side_used") == "bottom"
    return {
        "turn": observation["turn_number"],
        "player": observation["current_player"],
        "action": action.type.value,
        "card_name": card.get("name") if card else None,
        "side_used": info.get("side_used"),
        "used_as_creature": used_as_creature,
        "used_as_spell": used_as_spell,
        "moved_to_battle_zone": used_as_creature,
        "moved_to_graveyard": used_as_spell,
        "mana_charged": action.type == ActionType.CHARGE_MANA and bool(card and card.get("is_twinpact")),
        "zone_count_consistency": before == after,
        "winner": info.get("winner"),
    }


def _action_card(observation: dict[str, Any], action: Action) -> dict[str, Any] | None:
    index = action.card_index
    if action.type == ActionType.CAST_SPELL:
        index = action.hand_index if action.hand_index is not None else action.card_index
    if index is None or action.type not in {ActionType.CHARGE_MANA, ActionType.SUMMON, ActionType.CAST_SPELL}:
        return None
    hand = observation["self"]["hand"]
    return hand[index] if 0 <= index < len(hand) else None


def _zone_counts(env: Env) -> int:
    assert env.state is not None
    return sum(
        len(player.deck) + len(player.hand) + len(player.mana) + len(player.battle_zone) + len(player.graveyard) + len(player.shields)
        for player in env.state.players
    )


if __name__ == "__main__":
    main()
