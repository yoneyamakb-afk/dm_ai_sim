from __future__ import annotations

import random

from dm_ai_sim.env import Env, EnvConfig


def main() -> None:
    rng = random.Random(123)
    env = Env(config=EnvConfig(seed=123, include_action_mask=True))
    observation = env.reset()
    done = False
    info = {"winner": None, "turn_number": 1}

    while not done:
        action_ids = env.legal_action_ids()
        action_id = rng.choice(action_ids)
        observation, _reward, done, info = env.step_action_id(action_id)

    print(f"Winner: {info['winner']}")
    print(f"Turns: {info['turn_number']}")
    print(f"Action mask size: {len(observation['action_mask'])}")


if __name__ == "__main__":
    main()
