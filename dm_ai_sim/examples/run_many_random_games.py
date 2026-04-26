from __future__ import annotations

from dm_ai_sim.agents import RandomAgent
from dm_ai_sim.env import Env, EnvConfig


def run_game(seed: int) -> tuple[int | None, int]:
    env = Env(config=EnvConfig(seed=seed))
    agents = [RandomAgent(seed=seed * 2), RandomAgent(seed=seed * 2 + 1)]
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
    errors = 0

    for seed in range(total_games):
        try:
            winner, turns = run_game(seed)
        except Exception:
            errors += 1
            continue

        if winner in wins:
            wins[winner] += 1
        turn_counts.append(turns)

    average_turns = sum(turn_counts) / len(turn_counts) if turn_counts else 0.0
    max_turns = max(turn_counts) if turn_counts else 0

    print(f"Total games: {total_games}")
    print(f"Player 0 wins: {wins[0]}")
    print(f"Player 1 wins: {wins[1]}")
    print(f"Average turns: {average_turns:.2f}")
    print(f"Max turns: {max_turns}")
    print(f"Errors: {errors}")


if __name__ == "__main__":
    main()
