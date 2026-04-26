import pytest

from dm_ai_sim.actions import Action, ActionType
from dm_ai_sim.agents import RandomAgent
from dm_ai_sim.env import Env, EnvConfig


def test_random_games_finish_without_exceptions() -> None:
    for seed in range(100):
        env = Env(config=EnvConfig(seed=seed))
        agents = [RandomAgent(seed=seed * 2), RandomAgent(seed=seed * 2 + 1)]
        observation = env.reset()
        done = False

        while not done:
            env.assert_invariants()
            assert env.legal_actions()
            player_id = observation["current_player"]
            action = agents[player_id].act(env.legal_actions(), observation)
            observation, _reward, done, _info = env.step(action)

        env.assert_invariants()


def test_max_turns_ends_game_as_draw() -> None:
    env = Env(config=EnvConfig(max_turns=1, seed=1))
    env.reset()

    _observation, _reward, done, _info = env.step(Action(ActionType.END_MAIN))
    assert not done
    _observation, _reward, done, _info = env.step(Action(ActionType.END_ATTACK))
    assert not done
    _observation, _reward, done, info = env.step(Action(ActionType.END_MAIN))
    assert not done
    observation, reward, done, info = env.step(Action(ActionType.END_ATTACK))

    assert done
    assert reward == 0.0
    assert info["winner"] is None
    assert info["draw"]
    assert observation["done"]


def test_illegal_action_raises_value_error() -> None:
    env = Env(config=EnvConfig(seed=1))
    env.reset()

    with pytest.raises(ValueError):
        env.step(Action(ActionType.ATTACK_PLAYER, attacker_index=0))


def test_legal_actions_are_non_empty_until_done() -> None:
    env = Env(config=EnvConfig(seed=3))
    agent = RandomAgent(seed=3)
    observation = env.reset()
    done = False

    while not done:
        legal_actions = env.legal_actions()
        assert legal_actions
        observation, _reward, done, _info = env.step(agent.act(legal_actions, observation))


def test_card_count_is_preserved() -> None:
    env = Env(config=EnvConfig(seed=4))
    agent = RandomAgent(seed=4)
    observation = env.reset()
    done = False

    while not done:
        assert env.validate_invariants() == []
        observation, _reward, done, _info = env.step(agent.act(env.legal_actions(), observation))

    assert env.validate_invariants() == []
