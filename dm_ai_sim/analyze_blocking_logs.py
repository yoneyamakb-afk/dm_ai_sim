from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dm_ai_sim.action_encoder import decode_action, encode_action
from dm_ai_sim.actions import Action, ActionType
from dm_ai_sim.agents.heuristic_agent import HeuristicAgent
from dm_ai_sim.agents.selfplay_blocker_finetuned_agent import SelfPlayBlockerFineTunedAgent
from dm_ai_sim.agents.selfplay_optional_block_finetuned_agent import SelfPlayOptionalBlockFineTunedAgent
from dm_ai_sim.selfplay_env import DuelMastersSelfPlayEnv, SelfPlayConfig


LOG_PATH = Path("logs") / "blocking_analysis.jsonl"


def main(games: int = 20, output_path: Path = LOG_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    records = []
    for game_index in range(games):
        record = analyze_game(game_index)
        records.append(record)

    with output_path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")

    losses = [record for record in records if record["winner"] == 1]
    print(f"wrote {len(records)} games to {output_path}")
    print(f"learner losses: {len(losses)}")
    for label in sorted({label for record in losses for label in record["loss_tags"]}):
        count = sum(1 for record in losses if label in record["loss_tags"])
        print(f"{label}: {count}")


def analyze_game(game_index: int) -> dict[str, Any]:
    env = DuelMastersSelfPlayEnv(
        SelfPlayConfig(
            seed=9000 + game_index,
            fixed_opponent="heuristic",
            include_heuristic_opponent=False,
            include_random_opponent=False,
            intermediate_rewards=False,
            max_turns=120,
        )
    )
    env.reset()
    learner = _make_learner()
    opponent = HeuristicAgent()
    events: list[dict[str, Any]] = []
    done = False
    step_count = 0

    while not done and step_count < 1000:
        state = env.base_env.state
        if state is None:
            break
        before = env.base_env.get_observation()
        if state.current_player == 0 and hasattr(learner, "model"):
            action_id = learner.act(env, player_id=0)
            action = decode_action(action_id)
            _obs, _reward, done, info = env.base_env.step_action_id(action_id)
        else:
            agent = opponent if state.current_player == 1 else learner
            action = agent.act(env.base_env.legal_actions(), before)
            _obs, _reward, done, info = env.base_env.step(action)

        events.append(_event(before, action, info))
        step_count += 1

    state = env.base_env.state
    winner = state.winner if state is not None else None
    return {
        "game": game_index,
        "winner": winner,
        "turns": state.turn_number if state is not None else None,
        "steps": step_count,
        "loss_tags": _classify_loss(events) if winner == 1 else [],
        "events": events,
    }


def _make_learner() -> SelfPlayOptionalBlockFineTunedAgent | SelfPlayBlockerFineTunedAgent | HeuristicAgent:
    optional = SelfPlayOptionalBlockFineTunedAgent()
    if optional.is_available:
        return optional
    legacy = SelfPlayBlockerFineTunedAgent()
    if legacy.is_available:
        return legacy
    print("fine-tuned models unavailable, using HeuristicAgent fallback")
    return HeuristicAgent()


def _event(observation: dict[str, Any], action: Action, info: dict[str, Any]) -> dict[str, Any]:
    pending = observation.get("pending_attack")
    self_obs = observation["self"]
    opponent_obs = observation["opponent"]
    return {
        "turn": observation["turn_number"],
        "current_player": observation["current_player"],
        "phase": observation["phase"],
        "action": _action_dict(action),
        "pending_attack": pending is not None,
        "pending_target_type": pending.get("target_type") if pending else None,
        "pending_blocker_count": pending.get("blocker_count") if pending else 0,
        "blocked": bool(info.get("blocked", False)),
        "declined": bool(info.get("declined_block", False)),
        "attacker_power": pending.get("attacker_power") if pending else info.get("attacker_power"),
        "blocker_power": info.get("blocker_power"),
        "own_untapped_attackers": sum(1 for creature in self_obs["battle_zone"] if not creature["tapped"]),
        "opponent_untapped_blockers": sum(
            1 for creature in opponent_obs["battle_zone"] if creature["card"]["blocker"] and not creature["tapped"]
        ),
        "opponent_creatures": len(opponent_obs["battle_zone"]),
        "shield_counts": [
            self_obs["shield_count"],
            opponent_obs["shield_count"],
        ],
        "winner": info.get("winner"),
    }


def _action_dict(action: Action) -> dict[str, Any]:
    values: dict[str, Any] = {"type": action.type.value}
    for field in ("card_index", "attacker_index", "target_index", "blocker_index"):
        value = getattr(action, field)
        if value is not None:
            values[field] = value
    try:
        values["action_id"] = encode_action(action)
    except ValueError:
        pass
    return values


def _classify_loss(events: list[dict[str, Any]]) -> list[str]:
    tags: set[str] = set()
    learner_events = [event for event in events if event["current_player"] == 0]

    if any(
        event["action"]["type"] == ActionType.ATTACK_SHIELD.value and event.get("blocked")
        for event in learner_events
    ):
        tags.add("ブロッカーを処理せずシールド攻撃している")
    if any(event["action"]["type"] == ActionType.ATTACK_SHIELD.value for event in learner_events) and not any(
        event["action"]["type"] == ActionType.ATTACK_CREATURE.value for event in learner_events
    ):
        tags.add("攻撃順が悪い")
    if any(event["action"]["type"].startswith("ATTACK") for event in learner_events) and not any(
        event["action"]["type"] == ActionType.SUMMON.value for event in learner_events
    ):
        tags.add("召喚より攻撃を優先して負けている")
    if sum(1 for event in learner_events if event["action"]["type"] == ActionType.CHARGE_MANA.value) <= 1:
        tags.add("マナチャージ判断が悪い")
    if any(event["action"]["type"] == ActionType.END_ATTACK.value for event in learner_events):
        tags.add("リーサルを逃している")
    if any(
        event["action"]["type"] == ActionType.END_ATTACK.value
        and event["shield_counts"][1] == 0
        and event["own_untapped_attackers"] > 0
        for event in learner_events
    ):
        tags.add("リーサル可能だったか")
    if not any(event["action"]["type"] == ActionType.BLOCK.value for event in learner_events):
        tags.add("自軍ブロッカーを活かせていない")
    block_choices = [event for event in learner_events if event["pending_attack"]]
    if block_choices:
        block_rate = sum(1 for event in block_choices if event["action"]["type"] == ActionType.BLOCK.value) / len(block_choices)
        if block_rate >= 0.8:
            tags.add("ブロック判断が過剰")
        if block_rate <= 0.2:
            tags.add("ブロック判断が消極的すぎる")
    if any(
        event["pending_attack"]
        and event["pending_target_type"] == "PLAYER"
        and event["action"]["type"] == ActionType.DECLINE_BLOCK.value
        for event in learner_events
    ):
        tags.add("BLOCKすれば敗北を防げたか")
        tags.add("DECLINE_BLOCKが敗因になったか")
    if any(
        event["action"]["type"] == ActionType.BLOCK.value
        and event["blocker_power"] is not None
        and event["attacker_power"] is not None
        and event["blocker_power"] > event["attacker_power"]
        for event in learner_events
    ):
        tags.add("BLOCKが過剰で盤面損になったか")
    if any(
        event["action"]["type"] == ActionType.ATTACK_SHIELD.value
        and event["opponent_untapped_blockers"] > 0
        for event in learner_events
    ):
        tags.add("相手ブロッカーを攻撃で処理すべきだったか")
    if any(
        event["action"]["type"] == ActionType.ATTACK_SHIELD.value
        and event["opponent_creatures"] > 0
        for event in learner_events
    ):
        tags.add("シールド攻撃より先にクリーチャー攻撃すべきだったか")
    if any(
        event["action"]["type"] == ActionType.ATTACK_CREATURE.value
        and event["own_untapped_attackers"] > 1
        for event in learner_events
    ):
        tags.add("攻撃順で後続攻撃が通ったか")
    if any(
        event["action"]["type"] in {ActionType.ATTACK_SHIELD.value, ActionType.END_ATTACK.value}
        and event["own_untapped_attackers"] > 1
        and event["opponent_untapped_blockers"] > 0
        for event in learner_events
    ):
        tags.add("攻撃順ミスで後続攻撃が通らなかったか")
    tags.add("先攻/後攻による偏り")
    return sorted(tags)


if __name__ == "__main__":
    main()
