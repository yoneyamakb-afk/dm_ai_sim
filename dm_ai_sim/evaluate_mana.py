from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dm_ai_sim.action_encoder import encode_action
from dm_ai_sim.agents import HeuristicAgent, PPOSpellAgent, RandomAgent, SelfPlaySpellAgent, SelfPlaySpellFineTunedAgent
from dm_ai_sim.elo import MatchResult, calculate_elo
from dm_ai_sim.mana import playable_hand_counts, untapped_mana_count
from dm_ai_sim.selfplay_env import DuelMastersSelfPlayEnv, SelfPlayConfig


@dataclass(frozen=True, slots=True)
class AgentSpec:
    name: str
    kind: str
    path: Path | None = None


def available_agents() -> list[AgentSpec]:
    specs = [AgentSpec("RandomAgent", "random"), AgentSpec("HeuristicAgent", "heuristic")]
    optional = [
        AgentSpec("SelfPlaySpellFineTunedAgent", "selfplay_spell_finetuned", Path("saved_models") / "selfplay_spell_finetuned.zip"),
        AgentSpec("SelfPlaySpellAgent", "selfplay_spell", Path("saved_models") / "selfplay_spell.zip"),
        AgentSpec("PPOSpellAgent", "ppo_spell", Path("saved_models") / "ppo_spell.zip"),
    ]
    specs.extend(spec for spec in optional if spec.path is not None and spec.path.exists())
    return specs


def main() -> None:
    games = int(os.environ.get("DM_EVALUATE_MANA_GAMES", "50"))
    specs = available_agents()
    win_rates: dict[tuple[str, str], float | None] = {}
    average_turns: dict[tuple[str, str], float | None] = {}
    elo_results: list[MatchResult] = []
    aggregate = {"color_screw": 0, "turn2_playable": 0, "turn3_playable": 0, "tap_in_stalls": 0, "playable_sum": 0, "samples": 0}

    for row in specs:
        for col in specs:
            if row.name == col.name:
                win_rates[(row.name, col.name)] = 0.5
                average_turns[(row.name, col.name)] = 0.0
                continue
            try:
                wins, avg_turns, results, metrics = evaluate_pair(row, col, games)
            except Exception as exc:
                print(f"skip {row.name} vs {col.name}: {exc}")
                win_rates[(row.name, col.name)] = None
                average_turns[(row.name, col.name)] = None
                continue
            win_rates[(row.name, col.name)] = wins / games
            average_turns[(row.name, col.name)] = avg_turns
            elo_results.extend(results)
            for key in aggregate:
                aggregate[key] += metrics[key]

    print("Win rate table for row agent as Player 0")
    print("," + ",".join(spec.name for spec in specs))
    for row in specs:
        print(row.name + "," + ",".join(_format_cell(win_rates[(row.name, col.name)]) for col in specs))

    print("Average turns table")
    print("," + ",".join(spec.name for spec in specs))
    for row in specs:
        print(row.name + "," + ",".join(_format_cell(average_turns[(row.name, col.name)], 2) for col in specs))

    print("Elo")
    for name, rating in sorted(calculate_elo(elo_results).items(), key=lambda item: item[1], reverse=True):
        print(f"{name}: {rating:.1f}")

    samples = max(1, aggregate["samples"])
    print("Mana metrics")
    print(f"average_color_screw_rate: {aggregate['color_screw'] / samples:.3f}")
    print(f"turn2_playable_card_rate: {aggregate['turn2_playable'] / samples:.3f}")
    print(f"turn3_playable_card_rate: {aggregate['turn3_playable'] / samples:.3f}")
    print(f"multicolor_tap_in_stalls: {aggregate['tap_in_stalls']}")
    print(f"average_playable_hand_count: {aggregate['playable_sum'] / samples:.3f}")


def evaluate_pair(row: AgentSpec, col: AgentSpec, games: int) -> tuple[int, float, list[MatchResult], dict[str, int]]:
    wins = 0
    turns: list[int] = []
    results: list[MatchResult] = []
    metrics = {"color_screw": 0, "turn2_playable": 0, "turn3_playable": 0, "tap_in_stalls": 0, "playable_sum": 0, "samples": 0}

    for seed in range(games):
        env = DuelMastersSelfPlayEnv(SelfPlayConfig(seed=23000 + seed, fixed_opponent=_opponent_ref(col)))
        env.reset()
        row_agent = _make_row_agent(row, seed)
        terminated = False
        truncated = False
        info: dict[str, Any] = {"turn_number": 0}
        while not (terminated or truncated):
            _sample_mana_metrics(env, metrics)
            action = _row_action(row_agent, row, env)
            if isinstance(action, int):
                _observation, _reward, terminated, truncated, info = env.step(action)
            else:
                _observation, _reward, done, info = env.base_env.step(action)
                terminated = done
                while not terminated and env.base_env.state is not None and env.base_env.state.current_player == 1:
                    _observation, _reward, terminated, truncated, info = env.step(env.base_env.legal_action_ids()[0])
            if info.get("charged_card_enters_tapped") and env.base_env.state is not None:
                counts = playable_hand_counts(env.base_env.state.players[0])
                if counts["playable"] == 0 and untapped_mana_count(env.base_env.state.players[0]) == 0:
                    metrics["tap_in_stalls"] += 1

        winner = env.base_env.state.winner if env.base_env.state is not None else None
        score = 1.0 if winner == 0 else 0.0 if winner == 1 else 0.5
        if winner == 0:
            wins += 1
        results.append(MatchResult(row.name, col.name, score))
        turns.append(info.get("turn_number", env.base_env.state.turn_number if env.base_env.state else 0))
    return wins, sum(turns) / len(turns), results, metrics


def _sample_mana_metrics(env: DuelMastersSelfPlayEnv, metrics: dict[str, int]) -> None:
    state = env.base_env.state
    if state is None:
        return
    player = state.players[0]
    counts = playable_hand_counts(player)
    metrics["samples"] += 1
    metrics["playable_sum"] += counts["playable"]
    if counts["civilization_shortfall"] > 0 and counts["playable"] == 0:
        metrics["color_screw"] += 1
    if state.turn_number == 2 and counts["playable"] > 0:
        metrics["turn2_playable"] += 1
    if state.turn_number == 3 and counts["playable"] > 0:
        metrics["turn3_playable"] += 1


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
    if spec.kind == "ppo_spell":
        assert spec.path is not None
        return PPOSpellAgent(spec.path)
    if spec.kind == "selfplay_spell":
        assert spec.path is not None
        return SelfPlaySpellAgent(spec.path)
    if spec.kind == "selfplay_spell_finetuned":
        assert spec.path is not None
        return SelfPlaySpellFineTunedAgent(spec.path)
    raise ValueError(f"No runtime agent is implemented for {spec.name}")


def _row_action(agent, spec: AgentSpec, env: DuelMastersSelfPlayEnv):
    if spec.kind in {"random", "heuristic"}:
        action = agent.act(env.base_env.legal_actions(), env.base_env.get_observation())
        try:
            return encode_action(action)
        except ValueError:
            return action
    return agent.act(env, player_id=0)


def _format_cell(value: float | None, digits: int = 3) -> str:
    if value is None:
        return "skip"
    return f"{value:.{digits}f}"


if __name__ == "__main__":
    main()

