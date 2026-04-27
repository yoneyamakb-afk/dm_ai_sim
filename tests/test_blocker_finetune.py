from pathlib import Path

from dm_ai_sim.agents.selfplay_blocker_finetuned_agent import SelfPlayBlockerFineTunedAgent
from dm_ai_sim.evaluate_blocker import available_agents, main as evaluate_blocker_main
from dm_ai_sim.selfplay_blocker_finetune_env import DuelMastersBlockerFineTuneEnv, FineTuneRewardConfig
from dm_ai_sim.selfplay_env import SelfPlayConfig
from dm_ai_sim.train_selfplay_blocker_finetune import train as train_finetune


def test_finetuned_agent_handles_missing_model() -> None:
    env = DuelMastersBlockerFineTuneEnv(SelfPlayConfig(seed=1, fixed_opponent="heuristic"))
    env.reset()
    agent = SelfPlayBlockerFineTunedAgent(Path("missing_finetuned.zip"))

    assert not agent.is_available
    assert agent.act(env) in env.base_env.legal_action_ids()


def test_evaluate_blocker_handles_missing_finetuned_model(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)

    agents = available_agents()
    evaluate_blocker_main()

    assert "SelfPlayBlockerFineTunedAgent" not in [agent.name for agent in agents]


def test_reward_shaping_on_off_does_not_break_env() -> None:
    for enabled in (True, False):
        env = DuelMastersBlockerFineTuneEnv(
            SelfPlayConfig(seed=2, fixed_opponent="heuristic"),
            reward_config=FineTuneRewardConfig(enabled=enabled),
        )
        _observation, info = env.reset()
        _next_observation, reward, terminated, truncated, next_info = env.step(info["legal_action_ids"][0])

        assert isinstance(reward, float)
        assert isinstance(terminated, bool)
        assert isinstance(truncated, bool)
        assert "legal_action_ids" in next_info


def test_finetune_short_run(tmp_path: Path) -> None:
    model_path = tmp_path / "selfplay_blocker_finetuned_test"
    pool_dir = tmp_path / "opponents_blocker_finetuned"

    saved_path = train_finetune(
        total_timesteps=16,
        model_path=model_path,
        opponent_pool_dir=pool_dir,
        verbose=0,
        n_steps=8,
        batch_size=8,
        reward_shaping=True,
    )

    assert saved_path.exists()
    assert (pool_dir / "ppo_snapshot_16.zip").exists()
