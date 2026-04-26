from __future__ import annotations

from pathlib import Path

from sb3_contrib import MaskablePPO

from dm_ai_sim.gym_env import DuelMastersGymConfig, DuelMastersGymEnv


def main() -> None:
    model_dir = Path("saved_models")
    model_dir.mkdir(exist_ok=True)
    model_path = model_dir / "ppo_basic"

    env = DuelMastersGymEnv(
        DuelMastersGymConfig(
            opponent="random",
            seed=42,
            intermediate_rewards=True,
        )
    )
    model = MaskablePPO(
        "MlpPolicy",
        env,
        verbose=1,
        n_steps=256,
        batch_size=64,
        learning_rate=3e-4,
        gamma=0.99,
    )
    model.learn(total_timesteps=10_000)
    model.save(model_path)
    print(f"Saved model: {model_path.with_suffix('.zip')}")


if __name__ == "__main__":
    main()
