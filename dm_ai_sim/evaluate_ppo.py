from __future__ import annotations

from pathlib import Path

from dm_ai_sim.agents.ppo_agent import PPOAgent
from dm_ai_sim.gym_env import DuelMastersGymConfig, DuelMastersGymEnv


def main() -> None:
    model_path = Path("saved_models") / "ppo_basic.zip"
    agent = PPOAgent(model_path)
    games = 100
    wins = 0
    turns: list[int] = []

    for seed in range(games):
        env = DuelMastersGymEnv(DuelMastersGymConfig(opponent="random", seed=1000 + seed))
        _observation, _info = env.reset()
        terminated = False
        truncated = False

        while not (terminated or truncated):
            action_id = agent.act(env)
            _observation, _reward, terminated, truncated, info = env.step(action_id)

        if env.base_env.state is not None and env.base_env.state.winner == 0:
            wins += 1
        turns.append(info.get("turn_number", env.base_env.state.turn_number if env.base_env.state else 0))

    print(f"Games: {games}")
    print(f"PPO wins: {wins}")
    print(f"Win rate: {wins / games:.3f}")
    print(f"Average turns: {sum(turns) / len(turns):.2f}")


if __name__ == "__main__":
    main()
