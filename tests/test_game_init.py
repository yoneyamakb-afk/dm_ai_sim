from dm_ai_sim.env import Env, EnvConfig
from dm_ai_sim.state import Phase


def test_reset_initializes_game_zones() -> None:
    env = Env(config=EnvConfig(seed=1))
    observation = env.reset()

    assert observation["current_player"] == 0
    assert observation["phase"] == Phase.MAIN.value
    assert observation["self"]["hand_count"] == 5
    assert observation["self"]["shield_count"] == 5
    assert observation["self"]["deck_count"] == 30
    assert observation["opponent"]["hand_count"] == 5
    assert observation["opponent"]["shield_count"] == 5


def test_first_player_draw_can_be_enabled() -> None:
    env = Env(config=EnvConfig(first_player_draw=True, seed=1))
    observation = env.reset()

    assert observation["self"]["hand_count"] == 6
    assert observation["self"]["deck_count"] == 29
