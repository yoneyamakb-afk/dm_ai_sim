from pathlib import Path

from stable_baselines3 import PPO

from dm_ai_sim.agents.ppo_agent import PPOAgent
from dm_ai_sim.gym_env import ACTION_SPACE_SIZE, DuelMastersGymConfig, DuelMastersGymEnv


def test_gym_env_reset_step() -> None:
    env = DuelMastersGymEnv(DuelMastersGymConfig(seed=1))
    observation, info = env.reset()

    assert observation.shape == env.observation_space.shape
    assert len(info["action_mask"]) == ACTION_SPACE_SIZE

    action = info["legal_action_ids"][0]
    next_observation, reward, terminated, truncated, next_info = env.step(action)

    assert next_observation.shape == env.observation_space.shape
    assert isinstance(reward, float)
    assert isinstance(terminated, bool)
    assert isinstance(truncated, bool)
    assert len(next_info["action_mask"]) == ACTION_SPACE_SIZE


def test_ppo_can_learn_for_a_few_steps() -> None:
    env = DuelMastersGymEnv(DuelMastersGymConfig(seed=2))
    model = PPO("MlpPolicy", env, n_steps=8, batch_size=8, verbose=0)
    model.learn(total_timesteps=16)


def test_ppo_model_can_be_saved(tmp_path: Path) -> None:
    env = DuelMastersGymEnv(DuelMastersGymConfig(seed=3))
    model = PPO("MlpPolicy", env, n_steps=8, batch_size=8, verbose=0)
    model.learn(total_timesteps=16)
    model_path = tmp_path / "ppo_test"
    model.save(model_path)

    assert model_path.with_suffix(".zip").exists()


def test_ppo_agent_returns_action_id(tmp_path: Path) -> None:
    env = DuelMastersGymEnv(DuelMastersGymConfig(seed=4))
    model = PPO("MlpPolicy", env, n_steps=8, batch_size=8, verbose=0)
    model.learn(total_timesteps=16)
    model_path = tmp_path / "ppo_agent_test"
    model.save(model_path)

    eval_env = DuelMastersGymEnv(DuelMastersGymConfig(seed=5))
    eval_env.reset()
    agent = PPOAgent(model_path.with_suffix(".zip"))
    action_id = agent.act(eval_env)

    assert isinstance(action_id, int)
    assert action_id in eval_env.base_env.legal_action_ids()
