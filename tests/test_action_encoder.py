import pytest

from dm_ai_sim.action_encoder import ACTION_SPACE_SIZE, decode_action, encode_action, legal_action_mask
from dm_ai_sim.actions import Action, ActionType
from dm_ai_sim.env import Env, EnvConfig


def test_encode_decode_round_trip() -> None:
    actions = [
        Action(ActionType.CHARGE_MANA, card_index=3),
        Action(ActionType.SUMMON, card_index=4),
        Action(ActionType.CAST_SPELL, hand_index=5),
        Action(ActionType.CAST_SPELL, hand_index=6, target_index=2),
        Action(ActionType.REVOLUTION_CHANGE, hand_index=1, attacker_index=2),
        Action(ActionType.INVASION, hand_index=1, attacker_index=2),
        Action(ActionType.ATTACK_SHIELD, attacker_index=5),
        Action(ActionType.ATTACK_PLAYER, attacker_index=6),
        Action(ActionType.BLOCK, blocker_index=7),
        Action(ActionType.DECLINE_BLOCK),
        Action(ActionType.END_MAIN),
        Action(ActionType.END_ATTACK),
    ]

    for action in actions:
        assert decode_action(encode_action(action)) == action


def test_encode_accepts_dict_actions() -> None:
    assert encode_action({"type": "CHARGE_MANA", "card_index": 2}) == 2
    assert encode_action({"type": "CAST_SPELL", "hand_index": 3}) == 259
    assert encode_action({"type": "CAST_SPELL", "hand_index": 2, "target_index": 1}) == 313
    assert encode_action({"type": "REVOLUTION_CHANGE", "hand_index": 1, "attacker_index": 2}) == 394
    assert encode_action({"type": "INVASION", "hand_index": 1, "attacker_index": 2}) == 522
    assert encode_action({"type": "BLOCK", "blocker_index": 3}) == 245
    assert encode_action({"type": ActionType.END_MAIN}) == 160


def test_legal_actions_and_legal_action_ids_match() -> None:
    env = Env(config=EnvConfig(seed=1))
    env.reset()

    assert env.legal_action_ids() == [encode_action(action) for action in env.legal_actions()]


def test_legal_action_mask_marks_only_legal_actions() -> None:
    env = Env(config=EnvConfig(seed=1))
    env.reset()
    mask = legal_action_mask(env)

    assert len(mask) == ACTION_SPACE_SIZE
    assert sum(mask) == len(env.legal_action_ids())
    for action_id in env.legal_action_ids():
        assert mask[action_id] == 1


def test_observation_can_include_action_mask() -> None:
    env = Env(config=EnvConfig(seed=1, include_action_mask=True))
    observation = env.reset()

    assert "action_mask" in observation
    assert len(observation["action_mask"]) == ACTION_SPACE_SIZE


def test_invalid_action_id_raises_value_error() -> None:
    env = Env(config=EnvConfig(seed=1))
    env.reset()

    with pytest.raises(ValueError):
        env.step_action_id(999)

    with pytest.raises(ValueError):
        env.step_action_id(120)


def test_step_action_id_can_finish_game() -> None:
    env = Env(config=EnvConfig(seed=2))
    observation = env.reset()
    done = False

    while not done:
        action_id = env.legal_action_ids()[0]
        observation, _reward, done, _info = env.step_action_id(action_id)

    assert observation["done"]
