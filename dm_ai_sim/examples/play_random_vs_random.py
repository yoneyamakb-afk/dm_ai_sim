from __future__ import annotations

from dm_ai_sim.agents import RandomAgent
from dm_ai_sim.env import Env, EnvConfig


def main() -> None:
    env = Env(config=EnvConfig(seed=1))
    agents = [RandomAgent(seed=10), RandomAgent(seed=20)]
    observation = env.reset()
    done = False
    info = {"winner": None}

    while not done:
        player_id = observation["current_player"]
        action = agents[player_id].act(env.legal_actions(), observation)
        observation, _reward, done, info = env.step(action)

    print(f"Winner: Player {info['winner']}")
    print(f"Turns: {info['turn_number']}")


if __name__ == "__main__":
    main()
