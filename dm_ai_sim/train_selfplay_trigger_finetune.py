from __future__ import annotations

import os
from pathlib import Path

from sb3_contrib import MaskablePPO

from dm_ai_sim.selfplay_env import SelfPlayConfig
from dm_ai_sim.train_selfplay import SnapshotCallback, save_snapshot
from dm_ai_sim.trigger_finetune_env import DuelMastersTriggerFineTuneEnv, TriggerRewardConfig


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
    pool_dir = opponent_pool_dir or model_dir / "opponents_trigger_finetuned"
    model_dir.mkdir(exist_ok=True)
    pool_dir.mkdir(parents=True, exist_ok=True)
    steps = total_timesteps if total_timesteps is not None else int(
        os.environ.get("DM_SELFPLAY_TRIGGER_FINETUNE_TIMESTEPS", "50000")
    )
    snapshot_interval = int(os.environ.get("DM_SELFPLAY_TRIGGER_FINETUNE_SNAPSHOT_INTERVAL", "10000"))
    output_path = model_path or model_dir / "selfplay_trigger_finetuned"

    env = DuelMastersTriggerFineTuneEnv(
        SelfPlayConfig(
            seed=15050,
            opponent_pool_dir=pool_dir,
            include_heuristic_opponent=True,
            include_random_opponent=True,
            intermediate_rewards=True,
        ),
        reward_config=TriggerRewardConfig(enabled=reward_shaping),
        ppo_trigger_path=model_dir / "ppo_trigger.zip",
        selfplay_trigger_path=model_dir / "selfplay_trigger.zip",
        optional_block_path=model_dir / "selfplay_optional_block_finetuned.zip",
    )

    bootstrap_paths = [
        model_dir / "selfplay_trigger.zip",
        model_dir / "ppo_trigger.zip",
        model_dir / "selfplay_optional_block_finetuned.zip",
    ]
    bootstrap = next((path for path in bootstrap_paths if path.exists()), None)
    if bootstrap is not None:
        try:
            model = MaskablePPO.load(str(bootstrap), env=env, verbose=verbose)
            print(f"Loaded trigger fine-tune bootstrap model: {bootstrap}")
        except Exception as exc:
            print(f"Could not load trigger fine-tune bootstrap model: {exc}")
            model = _new_model(env, verbose, n_steps, batch_size)
    else:
        model = _new_model(env, verbose, n_steps, batch_size)

    callback = SnapshotCallback(snapshot_interval=snapshot_interval, opponent_pool_dir=pool_dir)
    model.learn(total_timesteps=steps, callback=callback, reset_num_timesteps=True)
    model.save(output_path)
    final_snapshot = save_snapshot(model, steps, pool_dir)
    print(f"Saved fine-tuned trigger self-play model: {output_path.with_suffix('.zip')}")
    print(f"Saved fine-tuned trigger snapshot: {final_snapshot}")
    return output_path.with_suffix(".zip")


def _new_model(env: DuelMastersTriggerFineTuneEnv, verbose: int, n_steps: int, batch_size: int) -> MaskablePPO:
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
