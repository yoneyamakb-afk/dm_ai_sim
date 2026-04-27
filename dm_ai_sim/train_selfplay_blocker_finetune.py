from __future__ import annotations

import os
from pathlib import Path

from sb3_contrib import MaskablePPO

from dm_ai_sim.selfplay_blocker_finetune_env import (
    DuelMastersBlockerFineTuneEnv,
    FineTuneRewardConfig,
)
from dm_ai_sim.selfplay_env import SelfPlayConfig
from dm_ai_sim.train_selfplay import SnapshotCallback, save_snapshot


def _new_model(
    env: DuelMastersBlockerFineTuneEnv,
    verbose: int,
    n_steps: int,
    batch_size: int,
) -> MaskablePPO:
    return MaskablePPO(
        "MlpPolicy",
        env,
        verbose=verbose,
        n_steps=n_steps,
        batch_size=batch_size,
        learning_rate=3e-4,
        gamma=0.99,
    )


def train(
    total_timesteps: int | None = None,
    model_path: Path | None = None,
    opponent_pool_dir: Path | None = None,
    verbose: int = 1,
    n_steps: int = 256,
    batch_size: int = 64,
    reward_shaping: bool = True,
) -> Path:
    model_dir = Path("saved_models")
    pool_dir = opponent_pool_dir or model_dir / "opponents_blocker_finetuned"
    model_dir.mkdir(exist_ok=True)
    pool_dir.mkdir(parents=True, exist_ok=True)

    steps = total_timesteps if total_timesteps is not None else int(
        os.environ.get("DM_SELFPLAY_BLOCKER_FINETUNE_TIMESTEPS", "50000")
    )
    snapshot_interval = int(os.environ.get("DM_SELFPLAY_BLOCKER_FINETUNE_SNAPSHOT_INTERVAL", "10000"))
    output_path = model_path or model_dir / "selfplay_blocker_finetuned"

    env = DuelMastersBlockerFineTuneEnv(
        SelfPlayConfig(
            seed=5050,
            opponent_pool_dir=pool_dir,
            include_heuristic_opponent=True,
            include_random_opponent=True,
            intermediate_rewards=True,
        ),
        reward_config=FineTuneRewardConfig(enabled=reward_shaping),
        ppo_blocker_path=model_dir / "ppo_blocker.zip",
    )

    bootstrap_paths = [
        model_dir / "selfplay_blocker.zip",
        model_dir / "ppo_blocker.zip",
    ]
    bootstrap = next((path for path in bootstrap_paths if path.exists()), None)
    if bootstrap is not None:
        try:
            model = MaskablePPO.load(str(bootstrap), env=env, verbose=verbose)
            print(f"Loaded fine-tune bootstrap model: {bootstrap}")
        except Exception as exc:
            print(f"Skipping incompatible fine-tune bootstrap model {bootstrap}: {exc}")
            model = _new_model(env, verbose=verbose, n_steps=n_steps, batch_size=batch_size)
    else:
        model = _new_model(env, verbose=verbose, n_steps=n_steps, batch_size=batch_size)

    callback = SnapshotCallback(snapshot_interval=snapshot_interval, opponent_pool_dir=pool_dir)
    model.learn(total_timesteps=steps, callback=callback, reset_num_timesteps=True)
    model.save(output_path)
    final_snapshot = save_snapshot(model, steps, pool_dir)
    print(f"Saved fine-tuned blocker self-play model: {output_path.with_suffix('.zip')}")
    print(f"Saved fine-tuned blocker snapshot: {final_snapshot}")
    return output_path.with_suffix(".zip")


def main() -> None:
    train()


if __name__ == "__main__":
    main()
