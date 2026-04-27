from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dm_ai_sim.action_encoder import encode_action
from dm_ai_sim.agents import (
    HeuristicAgent,
    PPOSpellAgent,
    RandomAgent,
    SelfPlaySpellAgent,
    SelfPlaySpellFineTunedAgent,
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
    trigger_best = _trigger_best_spec()
    if trigger_best is not None:
        specs.append(trigger_best)
    optional = [
        AgentSpec("PPOSpellAgent", "ppo_spell", Path("saved_models") / "ppo_spell.zip"),
        AgentSpec("SelfPlaySpellAgent", "selfplay_spell", Path("saved_models") / "selfplay_spell.zip"),
        AgentSpec("SelfPlaySpellFineTunedAgent", "selfplay_spell_finetuned", Path("saved_models") / "selfplay_spell_finetuned.zip"),
    ]
    specs.extend(spec for spec in optional if spec.path is not None and spec.path.exists())
    return specs


def _trigger_best_spec() -> AgentSpec | None:
    candidates = [
        AgentSpec("SelfPlayTriggerFineTunedAgent", "trigger_finetuned", Path("saved_models") / "selfplay_trigger_finetuned.zip"),
        AgentSpec("SelfPlayTriggerAgent", "trigger", Path("saved_models") / "selfplay_trigger.zip"),
    ]
    return next((spec for spec in candidates if spec.path is not None and spec.path.exists()), None)


def main() -> None:
    games = int(os.environ.get("DM_EVALUATE_SPELL_GAMES", "100"))
    specs = available_agents()
    if len(specs) < 2:
        print("Not enough agents to evaluate.")
        return

    win_rates: dict[tuple[str, str], float | None] = {}
    average_turns: dict[tuple[str, str], float | None] = {}
    spell_counts: dict[str, int] = {}
    spell_involved_games = 0
    elo_results: list[MatchResult] = []

    for row in specs:
        for col in specs:
            if row.name == col.name:
                win_rates[(row.name, col.name)] = 0.5
                average_turns[(row.name, col.name)] = 0.0
                continue
            try:
                wins, avg_turns, results, counts, involved = evaluate_pair(row, col, games)
            except Exception as exc:
                print(f"skip {row.name} vs {col.name}: {exc}")
                win_rates[(row.name, col.name)] = None
                average_turns[(row.name, col.name)] = None
                continue
            win_rates[(row.name, col.name)] = wins / games
            average_turns[(row.name, col.name)] = avg_turns
            elo_results.extend(results)
            spell_involved_games += involved
            for effect, count in counts.items():
                spell_counts[effect] = spell_counts.get(effect, 0) + count

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

    print("Spell counts")
    print(f"spell_cast: {sum(spell_counts.values())}")
    for effect, count in sorted(spell_counts.items()):
        print(f"{effect}: {count}")
    print(f"CAST_SPELL involved games: {spell_involved_games}")

    print("Direct spell win rates")
    for spec in specs:
        if spec.kind not in {"ppo_spell", "selfplay_spell", "selfplay_spell_finetuned"}:
            continue
        heuristic_rate = win_rates.get((spec.name, "HeuristicAgent"))
        print(f"{spec.name} vs HeuristicAgent: {_format_cell(heuristic_rate)}")
        trigger = _trigger_best_spec()
        if trigger is not None:
            trigger_rate = win_rates.get((spec.name, trigger.name))
            print(f"{spec.name} vs {trigger.name}: {_format_cell(trigger_rate)}")


def evaluate_pair(row: AgentSpec, col: AgentSpec, games: int) -> tuple[int, float, list[MatchResult], dict[str, int], int]:
    wins = 0
    turns: list[int] = []
    results: list[MatchResult] = []
    spell_counts: dict[str, int] = {}
    spell_involved_games = 0

    for seed in range(games):
        env = DuelMastersSelfPlayEnv(
            SelfPlayConfig(
                seed=17000 + seed,
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
        game_had_spell = False

        while not (terminated or truncated):
            action = _row_action(row_agent, row, env)
            if isinstance(action, int):
                _observation, _reward, terminated, truncated, info = env.step(action)
            else:
                _observation, _reward, done, info = env.base_env.step(action)
                terminated = done
                while not terminated and env.base_env.state is not None and env.base_env.state.current_player == 1:
                    _observation, _reward, terminated, truncated, info = env.step(env.base_env.legal_action_ids()[0])
            if info.get("spell_cast"):
                game_had_spell = True
                effect = str(info.get("spell_effect"))
                spell_counts[effect] = spell_counts.get(effect, 0) + 1

        winner = env.base_env.state.winner if env.base_env.state is not None else None
        score = 1.0 if winner == 0 else 0.0 if winner == 1 else 0.5
        if winner == 0:
            wins += 1
        if game_had_spell:
            spell_involved_games += 1
        results.append(MatchResult(row.name, col.name, score))
        turns.append(info.get("turn_number", env.base_env.state.turn_number if env.base_env.state else 0))
    return wins, sum(turns) / len(turns), results, spell_counts, spell_involved_games


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
    if spec.kind == "trigger_finetuned":
        assert spec.path is not None
        return SelfPlayTriggerFineTunedAgent(spec.path)
    if spec.kind == "trigger":
        assert spec.path is not None
        return SelfPlayTriggerAgent(spec.path)
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
