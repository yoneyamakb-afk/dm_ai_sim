from __future__ import annotations

from pathlib import Path

from dm_ai_sim.agents.selfplay_ppo_agent import SelfPlayPPOAgent
from dm_ai_sim.elo import MatchResult, calculate_elo
from dm_ai_sim.selfplay_env import DuelMastersSelfPlayEnv, SelfPlayConfig


def main() -> None:
    model_path = Path("saved_models") / "selfplay_ppo.zip"
    agent = SelfPlayPPOAgent(model_path)
    matchups: list[tuple[str, str | Path]] = [
        ("RandomAgent", "random"),
        ("HeuristicAgent", "heuristic"),
    ]

    ppo_path = Path("saved_models") / "ppo_basic.zip"
    if ppo_path.exists():
        matchups.append(("PPOAgent", ppo_path))

    all_results: list[MatchResult] = []
    for opponent_name, opponent in matchups:
        wins, average_turns, results = evaluate_matchup(agent, opponent_name, opponent, games=100)
        all_results.extend(results)
        print(f"SelfPlayPPO vs {opponent_name}")
        print(f"  Wins: {wins}/100")
        print(f"  Win rate: {wins / 100:.3f}")
        print(f"  Average turns: {average_turns:.2f}")

    ratings = calculate_elo(all_results)
    print("Elo:")
    for name, rating in sorted(ratings.items(), key=lambda item: item[1], reverse=True):
        print(f"  {name}: {rating:.1f}")


def evaluate_matchup(
    agent: SelfPlayPPOAgent,
    opponent_name: str,
    opponent: str | Path,
    games: int,
) -> tuple[int, float, list[MatchResult]]:
    wins = 0
    turns: list[int] = []
    results: list[MatchResult] = []

    for seed in range(games):
        env = DuelMastersSelfPlayEnv(
            SelfPlayConfig(
                seed=3000 + seed,
                fixed_opponent=opponent,
                include_heuristic_opponent=False,
                include_random_opponent=False,
            )
        )
        env.reset()
        terminated = False
        truncated = False
        info = {"turn_number": 0}

        while not (terminated or truncated):
            action_id = agent.act(env, player_id=0)
            _observation, _reward, terminated, truncated, info = env.step(action_id)

        winner = env.base_env.state.winner if env.base_env.state is not None else None
        if winner == 0:
            wins += 1
            score = 1.0
        elif winner == 1:
            score = 0.0
        else:
            score = 0.5
        results.append(MatchResult("SelfPlayPPOAgent", opponent_name, score))
        turns.append(info.get("turn_number", env.base_env.state.turn_number if env.base_env.state else 0))

    return wins, sum(turns) / len(turns), results


if __name__ == "__main__":
    main()
