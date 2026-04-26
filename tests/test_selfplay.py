from pathlib import Path

from sb3_contrib import MaskablePPO

from dm_ai_sim.agents.selfplay_ppo_agent import SelfPlayPPOAgent
from dm_ai_sim.elo import MatchResult, calculate_elo, update_elo
from dm_ai_sim.selfplay_env import DuelMastersSelfPlayEnv, SelfPlayConfig
from dm_ai_sim.train_selfplay import save_snapshot


def test_selfplay_env_reset_step() -> None:
    env = DuelMastersSelfPlayEnv(SelfPlayConfig(seed=1, fixed_opponent="random"))
    observation, info = env.reset()

    assert observation.shape == env.observation_space.shape
    assert info["legal_action_ids"]

    action_id = info["legal_action_ids"][0]
    next_observation, reward, terminated, truncated, next_info = env.step(action_id)

    assert next_observation.shape == env.observation_space.shape
    assert isinstance(reward, float)
    assert isinstance(terminated, bool)
    assert isinstance(truncated, bool)
    assert next_info["legal_action_ids"]


def test_snapshot_save_and_opponent_loading(tmp_path: Path) -> None:
    env = DuelMastersSelfPlayEnv(SelfPlayConfig(seed=2, opponent_pool_dir=tmp_path))
    model = MaskablePPO("MlpPolicy", env, n_steps=8, batch_size=8, verbose=0)
    model.learn(total_timesteps=16)

    snapshot_path = save_snapshot(model, 16, tmp_path)
    assert snapshot_path.exists()

    eval_env = DuelMastersSelfPlayEnv(SelfPlayConfig(seed=3, fixed_opponent=snapshot_path))
    _observation, info = eval_env.reset()

    assert info["opponent"] == snapshot_path.name


def test_elo_calculation() -> None:
    rating_a, rating_b = update_elo(1000.0, 1000.0, 1.0)
    assert rating_a > 1000.0
    assert rating_b < 1000.0

    ratings = calculate_elo([MatchResult("A", "B", 1.0), MatchResult("A", "B", 0.5)])
    assert set(ratings) == {"A", "B"}


def test_selfplay_ppo_agent_returns_action_id(tmp_path: Path) -> None:
    env = DuelMastersSelfPlayEnv(SelfPlayConfig(seed=4, opponent_pool_dir=tmp_path))
    model = MaskablePPO("MlpPolicy", env, n_steps=8, batch_size=8, verbose=0)
    model.learn(total_timesteps=16)
    model_path = tmp_path / "selfplay_test"
    model.save(model_path)

    eval_env = DuelMastersSelfPlayEnv(SelfPlayConfig(seed=5, fixed_opponent="random"))
    eval_env.reset()
    agent = SelfPlayPPOAgent(model_path.with_suffix(".zip"))
    action_id = agent.act(eval_env)

    assert isinstance(action_id, int)
    assert action_id in eval_env.base_env.legal_action_ids()
