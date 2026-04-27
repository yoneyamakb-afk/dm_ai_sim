from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dm_ai_sim.action_encoder import encode_action
from dm_ai_sim.agents import (
    HeuristicAgent,
    PPOAgent,
    PPOBlockerAgent,
    RandomAgent,
    SelfPlayBlockerAgent,
    SelfPlayBlockerFineTunedAgent,
    SelfPlayPPOAgent,
)
from dm_ai_sim.elo import MatchResult, calculate_elo
from dm_ai_sim.selfplay_env import DuelMastersSelfPlayEnv, SelfPlayConfig


@dataclass(frozen=True, slots=True)
class AgentSpec:
    name: str
    kind: str
    path: Path | None = None


def available_agents() -> list[AgentSpec]:
    specs = [
        AgentSpec("RandomAgent", "random"),
        AgentSpec("HeuristicAgent", "heuristic"),
    ]
    optional = [
        AgentSpec("PPOAgent", "ppo", Path("saved_models") / "ppo_basic.zip"),
        AgentSpec("SelfPlayPPOAgent", "selfplay", Path("saved_models") / "selfplay_ppo.zip"),
        AgentSpec("PPOBlockerAgent", "ppo_blocker", Path("saved_models") / "ppo_blocker.zip"),
        AgentSpec("SelfPlayBlockerAgent", "selfplay_blocker", Path("saved_models") / "selfplay_blocker.zip"),
        AgentSpec(
            "SelfPlayBlockerFineTunedAgent",
            "selfplay_blocker_finetuned",
            Path("saved_models") / "selfplay_blocker_finetuned.zip",
        ),
    ]
    specs.extend(spec for spec in optional if spec.path is not None and spec.path.exists())
    return specs


def main() -> None:
    games = int(os.environ.get("DM_EVALUATE_BLOCKER_GAMES", "100"))
    specs = available_agents()
    if len(specs) < 2:
        print("Not enough agents to evaluate.")
        return

    win_rates: dict[tuple[str, str], float | None] = {}
    average_turns: dict[tuple[str, str], float | None] = {}
    elo_results: list[MatchResult] = []

    for row in specs:
        for col in specs:
            if row.name == col.name:
                win_rates[(row.name, col.name)] = 0.5
                average_turns[(row.name, col.name)] = 0.0
                continue
            try:
                wins, avg_turns, results = evaluate_pair(row, col, games=games)
            except Exception as exc:
                print(f"skip {row.name} vs {col.name}: {exc}")
                win_rates[(row.name, col.name)] = None
                average_turns[(row.name, col.name)] = None
                continue
            win_rates[(row.name, col.name)] = wins / games
            average_turns[(row.name, col.name)] = avg_turns
            elo_results.extend(results)

    print("Win rate table for row agent as Player 0")
    print("," + ",".join(spec.name for spec in specs))
    for row in specs:
        cells = [_format_cell(win_rates[(row.name, col.name)]) for col in specs]
        print(row.name + "," + ",".join(cells))

    print("Average turns table")
    print("," + ",".join(spec.name for spec in specs))
    for row in specs:
        cells = [_format_cell(average_turns[(row.name, col.name)], digits=2) for col in specs]
        print(row.name + "," + ",".join(cells))

    print("Elo")
    ratings = calculate_elo(elo_results)
    for name, rating in sorted(ratings.items(), key=lambda item: item[1], reverse=True):
        print(f"{name}: {rating:.1f}")


def _format_cell(value: float | None, digits: int = 3) -> str:
    if value is None:
        return "skip"
    return f"{value:.{digits}f}"


def evaluate_pair(row: AgentSpec, col: AgentSpec, games: int) -> tuple[int, float, list[MatchResult]]:
    wins = 0
    turns: list[int] = []
    results: list[MatchResult] = []

    for seed in range(games):
        env = DuelMastersSelfPlayEnv(
            SelfPlayConfig(
                seed=7000 + seed,
                fixed_opponent=_opponent_ref(col),
                include_heuristic_opponent=False,
                include_random_opponent=False,
            )
        )
        env.reset()
        row_agent = _make_row_agent(row, seed)
        terminated = False
        truncated = False
        info = {"turn_number": 0}

        while not (terminated or truncated):
            action = _row_action(row_agent, row, env)
            if isinstance(action, int):
                _observation, _reward, terminated, truncated, info = env.step(action)
            else:
                _observation, _reward, done, info = env.base_env.step(action)
                terminated = done
                while not terminated and env.base_env.state is not None and env.base_env.state.current_player == 1:
                    _observation, _reward, terminated, truncated, info = env.step(env.base_env.legal_action_ids()[0])

        winner = env.base_env.state.winner if env.base_env.state is not None else None
        if winner == 0:
            wins += 1
            score = 1.0
        elif winner == 1:
            score = 0.0
        else:
            score = 0.5
        results.append(MatchResult(row.name, col.name, score))
        turns.append(info.get("turn_number", env.base_env.state.turn_number if env.base_env.state else 0))

    return wins, sum(turns) / len(turns), results


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
    if spec.kind == "ppo":
        assert spec.path is not None
        return PPOAgent(spec.path)
    if spec.kind == "selfplay":
        assert spec.path is not None
        return SelfPlayPPOAgent(spec.path)
    if spec.kind == "ppo_blocker":
        assert spec.path is not None
        return PPOBlockerAgent(spec.path)
    if spec.kind == "selfplay_blocker":
        assert spec.path is not None
        return SelfPlayBlockerAgent(spec.path)
    if spec.kind == "selfplay_blocker_finetuned":
        assert spec.path is not None
        return SelfPlayBlockerFineTunedAgent(spec.path)
    raise ValueError(f"Unknown agent kind: {spec.kind}")


def _row_action(agent, spec: AgentSpec, env: DuelMastersSelfPlayEnv):
    if spec.kind in {"random", "heuristic"}:
        observation = env.base_env.get_observation()
        action = agent.act(env.base_env.legal_actions(), observation)
        try:
            return encode_action(action)
        except ValueError:
            return action
    if spec.kind == "ppo":
        return agent.act(env)
    return agent.act(env, player_id=0)


if __name__ == "__main__":
    main()
