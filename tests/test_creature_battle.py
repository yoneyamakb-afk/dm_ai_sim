from dm_ai_sim.action_encoder import ACTION_SPACE_SIZE, decode_action, encode_action, legal_action_mask
from dm_ai_sim.actions import Action, ActionType
from dm_ai_sim.card import Card
from dm_ai_sim.env import Env, EnvConfig
from dm_ai_sim.gym_env import DuelMastersGymConfig, DuelMastersGymEnv
from dm_ai_sim.state import Creature, Phase


def _battle_env(attacker_power: int, defender_power: int) -> Env:
    deck = [Card(id=i, name=f"C{i}", cost=1, power=1000) for i in range(40)]
    env = Env(deck0=deck, deck1=deck, config=EnvConfig(seed=1))
    env.reset()
    assert env.state is not None
    env.state.turn_number = 2
    env.state.phase = Phase.ATTACK
    env.state.players[0].battle_zone.append(
        Creature(Card(id=9001, name="Attacker", cost=1, power=attacker_power), summoned_turn=1)
    )
    env.state.players[1].battle_zone.append(
        Creature(Card(id=9002, name="Defender", cost=1, power=defender_power), summoned_turn=1)
    )
    return env


def test_favorable_battle_destroys_only_defender() -> None:
    env = _battle_env(attacker_power=4000, defender_power=2000)
    env.step(Action(ActionType.ATTACK_CREATURE, attacker_index=0, target_index=0))

    assert len(env.state.players[0].battle_zone) == 1
    assert len(env.state.players[1].battle_zone) == 0
    assert [card.name for card in env.state.players[1].graveyard] == ["Defender"]


def test_equal_power_battle_destroys_both() -> None:
    env = _battle_env(attacker_power=3000, defender_power=3000)
    env.step(Action(ActionType.ATTACK_CREATURE, attacker_index=0, target_index=0))

    assert len(env.state.players[0].battle_zone) == 0
    assert len(env.state.players[1].battle_zone) == 0
    assert [card.name for card in env.state.players[0].graveyard] == ["Attacker"]
    assert [card.name for card in env.state.players[1].graveyard] == ["Defender"]


def test_unfavorable_battle_destroys_only_attacker() -> None:
    env = _battle_env(attacker_power=1000, defender_power=5000)
    env.step(Action(ActionType.ATTACK_CREATURE, attacker_index=0, target_index=0))

    assert len(env.state.players[0].battle_zone) == 0
    assert len(env.state.players[1].battle_zone) == 1
    assert [card.name for card in env.state.players[0].graveyard] == ["Attacker"]


def test_attack_creature_is_legal_when_opponent_has_creature() -> None:
    env = _battle_env(attacker_power=4000, defender_power=2000)

    assert Action(ActionType.ATTACK_CREATURE, attacker_index=0, target_index=0) in env.legal_actions()


def test_attack_creature_action_id_round_trip_and_mask() -> None:
    env = _battle_env(attacker_power=4000, defender_power=2000)
    action = Action(ActionType.ATTACK_CREATURE, attacker_index=0, target_index=0)
    action_id = encode_action(action)

    assert decode_action(action_id) == action
    assert action_id in env.legal_action_ids()
    assert legal_action_mask(env)[action_id] == 1


def test_gym_env_still_steps_with_creature_battle_action_space() -> None:
    env = DuelMastersGymEnv(DuelMastersGymConfig(seed=1))
    observation, info = env.reset()
    next_observation, reward, terminated, truncated, next_info = env.step(info["legal_action_ids"][0])

    assert observation.shape == next_observation.shape
    assert isinstance(reward, float)
    assert isinstance(terminated, bool)
    assert isinstance(truncated, bool)
    assert len(next_info["action_mask"]) == ACTION_SPACE_SIZE
