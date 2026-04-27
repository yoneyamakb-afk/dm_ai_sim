from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dm_ai_sim.action_encoder import encode_action
from dm_ai_sim.agents import (
    HeuristicAgent,
    PPOAgent,
    PPOBlockerAgent,
    PPOOptionalBlockAgent,
    PPOTriggerAgent,
    RandomAgent,
    SelfPlayBlockerAgent,
    SelfPlayBlockerFineTunedAgent,
    SelfPlayOptionalBlockAgent,
    SelfPlayOptionalBlockFineTunedAgent,
    SelfPlayPPOAgent,
    SelfPlayTriggerAgent,
    SelfPlayTriggerFineTunedAgent,
)
from dm_ai_sim.elo import MatchResult, calculate_elo
from dm_ai_sim.selfplay_env import DuelMastersSelfPlayEnv, SelfPlayConfig


@dataclass(frozen=True, slots=True)
class AgentSpec:
    name: str
    kind: str
    path: Path | None = None


def available_agents() -> list[AgentSpec]:
    specs = [AgentSpec("RandomAgent", "random"), AgentSpec("HeuristicAgent", "heuristic")]
    optional = [
        AgentSpec("PPOAgent", "ppo", Path("saved_models") / "ppo_basic.zip"),
        AgentSpec("SelfPlayPPOAgent", "selfplay", Path("saved_models") / "selfplay_ppo.zip"),
        AgentSpec("PPOBlockerAgent", "ppo_blocker", Path("saved_models") / "ppo_blocker.zip"),
        AgentSpec("SelfPlayBlockerAgent", "selfplay_blocker", Path("saved_models") / "selfplay_blocker.zip"),
        AgentSpec("SelfPlayBlockerFineTunedAgent", "selfplay_blocker_finetuned", Path("saved_models") / "selfplay_blocker_finetuned.zip"),
        AgentSpec("PPOOptionalBlockAgent", "ppo_optional_block", Path("saved_models") / "ppo_optional_block.zip"),
        AgentSpec("SelfPlayOptionalBlockAgent", "selfplay_optional_block", Path("saved_models") / "selfplay_optional_block.zip"),
        AgentSpec("SelfPlayOptionalBlockFineTunedAgent", "selfplay_optional_block_finetuned", Path("saved_models") / "selfplay_optional_block_finetuned.zip"),
        AgentSpec("PPOTriggerAgent", "ppo_trigger", Path("saved_models") / "ppo_trigger.zip"),
        AgentSpec("SelfPlayTriggerAgent", "selfplay_trigger", Path("saved_models") / "selfplay_trigger.zip"),
        AgentSpec("SelfPlayTriggerFineTunedAgent", "selfplay_trigger_finetuned", Path("saved_models") / "selfplay_trigger_finetuned.zip"),
    ]
    specs.extend(spec for spec in optional if spec.path is not None and spec.path.exists())
    return specs


def main() -> None:
    games = int(os.environ.get("DM_EVALUATE_TRIGGER_GAMES", "100"))
    specs = available_agents()
    if len(specs) < 2:
        print("Not enough agents to evaluate.")
        return

    win_rates: dict[tuple[str, str], float | None] = {}
    average_turns: dict[tuple[str, str], float | None] = {}
    trigger_counts = {"DRAW_1": 0, "DESTROY_ATTACKER": 0, "SUMMON_SELF": 0, "GAIN_SHIELD": 0}
    elo_results: list[MatchResult] = []

    for row in specs:
        for col in specs:
            if row.name == col.name:
                win_rates[(row.name, col.name)] = 0.5
                average_turns[(row.name, col.name)] = 0.0
                continue
            try:
                wins, avg_turns, results, counts = evaluate_pair(row, col, games=games)
            except Exception as exc:
                print(f"skip {row.name} vs {col.name}: {exc}")
                win_rates[(row.name, col.name)] = None
                average_turns[(row.name, col.name)] = None
                continue
            win_rates[(row.name, col.name)] = wins / games
            average_turns[(row.name, col.name)] = avg_turns
            elo_results.extend(results)
            for effect, count in counts.items():
                trigger_counts[effect] += count

    print("Win rate table for row agent as Player 0")
    print("," + ",".join(spec.name for spec in specs))
    for row in specs:
        print(row.name + "," + ",".join(_format_cell(win_rates[(row.name, col.name)]) for col in specs))

    print("Average turns table")
    print("," + ",".join(spec.name for spec in specs))
    for row in specs:
        print(row.name + "," + ",".join(_format_cell(average_turns[(row.name, col.name)], 2) for col in specs))

    print("Elo")
    ratings = calculate_elo(elo_results)
    for name, rating in sorted(ratings.items(), key=lambda item: item[1], reverse=True):
        print(f"{name}: {rating:.1f}")

    print("Direct trigger checks")
    best_optional = "SelfPlayOptionalBlockFineTunedAgent"
    for name in ["PPOTriggerAgent", "SelfPlayTriggerAgent", "SelfPlayTriggerFineTunedAgent"]:
        heuristic = win_rates.get((name, "HeuristicAgent"))
        optional = win_rates.get((name, best_optional))
        if heuristic is not None:
            print(f"{name} vs HeuristicAgent: {heuristic:.3f}")
        if optional is not None:
            print(f"{name} vs {best_optional}: {optional:.3f}")

    print("Trigger counts")
    print(f"trigger activations: {sum(trigger_counts.values())}")
    for effect in ["DESTROY_ATTACKER", "GAIN_SHIELD", "SUMMON_SELF", "DRAW_1"]:
        print(f"{effect}: {trigger_counts[effect]}")


def evaluate_pair(row: AgentSpec, col: AgentSpec, games: int) -> tuple[int, float, list[MatchResult], dict[str, int]]:
    wins = 0
    turns: list[int] = []
    results: list[MatchResult] = []
    trigger_counts = {"DRAW_1": 0, "DESTROY_ATTACKER": 0, "SUMMON_SELF": 0, "GAIN_SHIELD": 0}

    for seed in range(games):
        env = DuelMastersSelfPlayEnv(
            SelfPlayConfig(
                seed=16000 + seed,
                fixed_opponent=_opponent_ref(col),
                include_heuristic_opponent=False,
                include_random_opponent=False,
            )
        )
        env.reset()
        row_agent = _make_row_agent(row, seed)
        terminated = False
        truncated = False
        info: dict[str, Any] = {"turn_number": 0}

        while not (terminated or truncated):
            action = _row_action(row_agent, row, env)
            if isinstance(action, int):
                _observation, _reward, terminated, truncated, info = env.step(action)
            else:
                _observation, _reward, done, info = env.base_env.step(action)
                terminated = done
                while not terminated and env.base_env.state is not None and env.base_env.state.current_player == 1:
                    _observation, _reward, terminated, truncated, info = env.step(env.base_env.legal_action_ids()[0])
            effect = info.get("trigger_effect")
            if effect in trigger_counts:
                trigger_counts[effect] += 1

        winner = env.base_env.state.winner if env.base_env.state is not None else None
        score = 1.0 if winner == 0 else 0.0 if winner == 1 else 0.5
        if winner == 0:
            wins += 1
        results.append(MatchResult(row.name, col.name, score))
        turns.append(info.get("turn_number", env.base_env.state.turn_number if env.base_env.state else 0))

    return wins, sum(turns) / len(turns), results, trigger_counts


def _opponent_ref(spec: AgentSpec) -> str | Path:
    if spec.kind in {"random", "heuristic"}:
        return spec.kind
    assert spec.path is not None
    return spec.path


def _make_row_agent(spec: AgentSpec, seed: int):
    if spec.kind == "random":
        return RandomAgent(seed=seed)
    if spec.kind == "heuristic":
        return HeuristicAgent()
    assert spec.path is not None
    mapping = {
        "ppo": PPOAgent,
        "selfplay": SelfPlayPPOAgent,
        "ppo_blocker": PPOBlockerAgent,
        "selfplay_blocker": SelfPlayBlockerAgent,
        "selfplay_blocker_finetuned": SelfPlayBlockerFineTunedAgent,
        "ppo_optional_block": PPOOptionalBlockAgent,
        "selfplay_optional_block": SelfPlayOptionalBlockAgent,
        "selfplay_optional_block_finetuned": SelfPlayOptionalBlockFineTunedAgent,
        "ppo_trigger": PPOTriggerAgent,
        "selfplay_trigger": SelfPlayTriggerAgent,
        "selfplay_trigger_finetuned": SelfPlayTriggerFineTunedAgent,
    }
    return mapping[spec.kind](spec.path)


def _row_action(agent, spec: AgentSpec, env: DuelMastersSelfPlayEnv):
    if spec.kind in {"random", "heuristic"}:
        action = agent.act(env.base_env.legal_actions(), env.base_env.get_observation())
        try:
            return encode_action(action)
        except ValueError:
            return action
    if spec.kind == "ppo":
        return agent.act(env)
    return agent.act(env, player_id=0)


def _format_cell(value: float | None, digits: int = 3) -> str:
    if value is None:
        return "skip"
    return f"{value:.{digits}f}"


if __name__ == "__main__":
    main()
