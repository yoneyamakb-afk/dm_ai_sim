from __future__ import annotations

from dm_ai_sim.agents import HeuristicAgent, RandomAgent
from dm_ai_sim.env import Env, EnvConfig


def run_game(seed: int) -> tuple[int | None, int]:
    env = Env(config=EnvConfig(seed=seed))
    agents = [HeuristicAgent(), RandomAgent(seed=seed)]
    observation = env.reset()
    done = False
    info = {"winner": None, "turn_number": 1}

    while not done:
        env.assert_invariants()
        player_id = observation["current_player"]
        legal_actions = env.legal_actions()
        action = agents[player_id].act(legal_actions, observation)
        observation, _reward, done, info = env.step(action)

    env.assert_invariants()
    return info["winner"], info["turn_number"]


def main() -> None:
    total_games = 1000
    wins = {0: 0, 1: 0}
    turn_counts: list[int] = []

    for seed in range(total_games):
        winner, turns = run_game(seed)
        if winner in wins:
            wins[winner] += 1
        turn_counts.append(turns)

    average_turns = sum(turn_counts) / len(turn_counts) if turn_counts else 0.0
    max_turns = max(turn_counts) if turn_counts else 0
    player_0_win_rate = wins[0] / total_games if total_games else 0.0
    player_1_win_rate = wins[1] / total_games if total_games else 0.0

    print(f"Total games: {total_games}")
    print(f"HeuristicAgent wins: {wins[0]}")
    print(f"RandomAgent wins: {wins[1]}")
    print(f"HeuristicAgent win rate: {player_0_win_rate:.3f}")
    print(f"RandomAgent win rate: {player_1_win_rate:.3f}")
    print(f"Average turns: {average_turns:.2f}")
    print(f"Max turns: {max_turns}")


if __name__ == "__main__":
    main()
