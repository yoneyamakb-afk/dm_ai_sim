from pathlib import Path

from dm_ai_sim.agents.ppo_blocker_agent import PPOBlockerAgent
from dm_ai_sim.agents.selfplay_blocker_agent import SelfPlayBlockerAgent
from dm_ai_sim.evaluate_blocker import available_agents, main as evaluate_blocker_main
from dm_ai_sim.selfplay_env import DuelMastersSelfPlayEnv, SelfPlayConfig
from dm_ai_sim.train_ppo_blocker import train as train_ppo_blocker
from dm_ai_sim.train_selfplay_blocker import train as train_selfplay_blocker


def test_blocker_agents_handle_missing_models() -> None:
    env = DuelMastersSelfPlayEnv(SelfPlayConfig(seed=1, fixed_opponent="random"))
    env.reset()
    ppo_agent = PPOBlockerAgent(Path("missing_ppo_blocker.zip"))
    selfplay_agent = SelfPlayBlockerAgent(Path("missing_selfplay_blocker.zip"))

    assert not ppo_agent.is_available
    assert not selfplay_agent.is_available
    assert ppo_agent.act(env) in env.base_env.legal_action_ids()
    assert selfplay_agent.act(env) in env.base_env.legal_action_ids()


def test_evaluate_blocker_handles_missing_models(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)

    agents = available_agents()
    evaluate_blocker_main()

    assert [agent.name for agent in agents] == ["RandomAgent", "HeuristicAgent"]


def test_train_ppo_blocker_short_run(tmp_path: Path) -> None:
    model_path = tmp_path / "ppo_blocker_test"

    saved_path = train_ppo_blocker(
        total_timesteps=16,
        model_path=model_path,
        verbose=0,
        n_steps=8,
        batch_size=8,
    )

    assert saved_path.exists()


def test_train_selfplay_blocker_short_run(tmp_path: Path) -> None:
    model_path = tmp_path / "selfplay_blocker_test"
    pool_dir = tmp_path / "opponents_blocker"

    saved_path = train_selfplay_blocker(
        total_timesteps=16,
        model_path=model_path,
        opponent_pool_dir=pool_dir,
        verbose=0,
        n_steps=8,
        batch_size=8,
    )

    assert saved_path.exists()
    assert (pool_dir / "ppo_snapshot_16.zip").exists()
