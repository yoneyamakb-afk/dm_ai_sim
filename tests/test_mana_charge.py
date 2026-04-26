from dm_ai_sim.actions import ActionType
from dm_ai_sim.env import Env, EnvConfig


def test_can_charge_mana_once_per_turn() -> None:
    env = Env(config=EnvConfig(seed=1))
    env.reset()
    charge = next(action for action in env.legal_actions() if action.type == ActionType.CHARGE_MANA)

    observation, reward, done, _info = env.step(charge)

    assert reward == 0.0
    assert not done
    assert observation["self"]["hand_count"] == 4
    assert len(observation["self"]["mana"]) == 1
    assert all(action.type != ActionType.CHARGE_MANA for action in env.legal_actions())
