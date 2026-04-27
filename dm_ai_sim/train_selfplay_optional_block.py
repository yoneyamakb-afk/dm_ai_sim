from __future__ import annotations

import os
import shutil
from pathlib import Path

from sb3_contrib import MaskablePPO

from dm_ai_sim.selfplay_env import DuelMastersSelfPlayEnv, SelfPlayConfig
from dm_ai_sim.train_selfplay import SnapshotCallback, save_snapshot


def train(
    total_timesteps: int | None = None,
    model_path: Path | None = None,
    opponent_pool_dir: Path | None = None,
    verbose: int = 1,
    n_steps: int = 256,
    batch_size: int = 64,
) -> Path:
    model_dir = Path("saved_models")
    pool_dir = opponent_pool_dir or model_dir / "opponents_optional_block"
    model_dir.mkdir(exist_ok=True)
    pool_dir.mkdir(parents=True, exist_ok=True)

    steps = total_timesteps if total_timesteps is not None else int(
        os.environ.get("DM_SELFPLAY_OPTIONAL_BLOCK_TIMESTEPS", "50000")
    )
    snapshot_interval = int(os.environ.get("DM_SELFPLAY_OPTIONAL_BLOCK_SNAPSHOT_INTERVAL", "10000"))
    output_path = model_path or model_dir / "selfplay_optional_block"

    ppo_optional_block_path = model_dir / "ppo_optional_block.zip"
    if ppo_optional_block_path.exists():
        shutil.copy2(ppo_optional_block_path, pool_dir / "ppo_snapshot_0.zip")

    env = DuelMastersSelfPlayEnv(
        SelfPlayConfig(
            seed=7070,
            opponent_pool_dir=pool_dir,
            include_heuristic_opponent=True,
            include_random_opponent=True,
            intermediate_rewards=True,
        )
    )

    if ppo_optional_block_path.exists():
        try:
            model = MaskablePPO.load(str(ppo_optional_block_path), env=env, verbose=verbose)
            print(f"Loaded optional-block bootstrap model: {ppo_optional_block_path}")
        except Exception as exc:
            print(f"Could not load optional-block bootstrap model: {exc}")
            model = _new_model(env, verbose, n_steps, batch_size)
    else:
        model = _new_model(env, verbose, n_steps, batch_size)

    callback = SnapshotCallback(snapshot_interval=snapshot_interval, opponent_pool_dir=pool_dir)
    model.learn(total_timesteps=steps, callback=callback, reset_num_timesteps=True)
    model.save(output_path)
    final_snapshot = save_snapshot(model, steps, pool_dir)
    print(f"Saved optional-block self-play model: {output_path.with_suffix('.zip')}")
    print(f"Saved optional-block snapshot: {final_snapshot}")
    return output_path.with_suffix(".zip")


def _new_model(env: DuelMastersSelfPlayEnv, verbose: int, n_steps: int, batch_size: int) -> MaskablePPO:
    return MaskablePPO(
        "MlpPolicy",
        env,
        verbose=verbose,
        n_steps=n_steps,
        batch_size=batch_size,
        learning_rate=3e-4,
        gamma=0.99,
    )


def main() -> None:
    train()


if __name__ == "__main__":
    main()
