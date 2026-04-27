from __future__ import annotations

import os
from pathlib import Path

from sb3_contrib import MaskablePPO

from dm_ai_sim.gym_env import DuelMastersGymConfig, DuelMastersGymEnv


def train(
    total_timesteps: int | None = None,
    model_path: Path | None = None,
    verbose: int = 1,
    n_steps: int = 256,
    batch_size: int = 64,
) -> Path:
    model_dir = Path("saved_models")
    model_dir.mkdir(exist_ok=True)
    output_path = model_path or model_dir / "ppo_spell"
    steps = total_timesteps if total_timesteps is not None else int(os.environ.get("DM_PPO_SPELL_TIMESTEPS", "50000"))

    env = DuelMastersGymEnv(
        DuelMastersGymConfig(
            opponent="heuristic",
            seed=19030,
            intermediate_rewards=False,
        )
    )
    model = MaskablePPO(
        "MlpPolicy",
        env,
        verbose=verbose,
        n_steps=n_steps,
        batch_size=batch_size,
        learning_rate=3e-4,
        gamma=0.99,
    )
    model.learn(total_timesteps=steps)
    model.save(output_path)
    return output_path.with_suffix(".zip")


def main() -> None:
    saved_path = train()
    print(f"Saved spell PPO model: {saved_path}")


if __name__ == "__main__":
    main()

