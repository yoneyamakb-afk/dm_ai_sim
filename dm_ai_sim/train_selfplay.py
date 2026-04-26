from __future__ import annotations

import os
from pathlib import Path

from sb3_contrib import MaskablePPO
from stable_baselines3.common.callbacks import BaseCallback

from dm_ai_sim.elo import MatchResult, calculate_elo
from dm_ai_sim.selfplay_env import DuelMastersSelfPlayEnv, SelfPlayConfig


class SnapshotCallback(BaseCallback):
    def __init__(self, snapshot_interval: int, opponent_pool_dir: Path, verbose: int = 0) -> None:
        super().__init__(verbose=verbose)
        self.snapshot_interval = snapshot_interval
        self.opponent_pool_dir = opponent_pool_dir

    def _on_step(self) -> bool:
        if self.num_timesteps > 0 and self.num_timesteps % self.snapshot_interval == 0:
            save_snapshot(self.model, self.num_timesteps, self.opponent_pool_dir)
        return True


def save_snapshot(model: MaskablePPO, timesteps: int, opponent_pool_dir: Path) -> Path:
    opponent_pool_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = opponent_pool_dir / f"ppo_snapshot_{timesteps}.zip"
    model.save(snapshot_path)
    return snapshot_path


def main() -> None:
    model_dir = Path("saved_models")
    opponent_pool_dir = model_dir / "opponents"
    model_dir.mkdir(exist_ok=True)
    opponent_pool_dir.mkdir(parents=True, exist_ok=True)

    total_timesteps = int(os.environ.get("DM_SELFPLAY_TIMESTEPS", "10000"))
    snapshot_interval = int(os.environ.get("DM_SELFPLAY_SNAPSHOT_INTERVAL", "5000"))
    model_path = model_dir / "selfplay_ppo"

    env = DuelMastersSelfPlayEnv(
        SelfPlayConfig(
            seed=2026,
            opponent_pool_dir=opponent_pool_dir,
            intermediate_rewards=True,
        )
    )

    bootstrap_path = model_dir / "ppo_basic.zip"
    if bootstrap_path.exists():
        model = MaskablePPO.load(str(bootstrap_path), env=env, verbose=1)
        print(f"Loaded bootstrap model: {bootstrap_path}")
    else:
        model = MaskablePPO(
            "MlpPolicy",
            env,
            verbose=1,
            n_steps=256,
            batch_size=64,
            learning_rate=3e-4,
            gamma=0.99,
        )

    callback = SnapshotCallback(snapshot_interval=snapshot_interval, opponent_pool_dir=opponent_pool_dir)
    model.learn(total_timesteps=total_timesteps, callback=callback, reset_num_timesteps=True)
    model.save(model_path)
    final_snapshot = save_snapshot(model, total_timesteps, opponent_pool_dir)

    ratings = calculate_elo(
        [
            MatchResult("SelfPlayPPOAgent", "RandomAgent", 1.0),
            MatchResult("SelfPlayPPOAgent", "HeuristicAgent", 0.5),
        ]
    )
    print(f"Saved self-play model: {model_path.with_suffix('.zip')}")
    print(f"Saved final snapshot: {final_snapshot}")
    print("Initial Elo estimate:")
    for name, rating in sorted(ratings.items()):
        print(f"{name}: {rating:.1f}")


if __name__ == "__main__":
    main()
