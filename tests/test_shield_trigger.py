from dm_ai_sim.actions import Action, ActionType
from dm_ai_sim.action_encoder import ACTION_SPACE_SIZE
from dm_ai_sim.card import Card, make_vanilla_deck
from dm_ai_sim.env import Env, EnvConfig
from dm_ai_sim.gym_env import DuelMastersGymConfig, DuelMastersGymEnv
from dm_ai_sim.selfplay_env import DuelMastersSelfPlayEnv, SelfPlayConfig
from dm_ai_sim.state import Creature, Phase


def _deck(base_id: int = 0) -> list[Card]:
    return [Card(id=base_id + i, name=f"C{base_id + i}", cost=1, power=1000) for i in range(40)]


def _trigger_env(shield_card: Card, attacker_power: int = 3000, blocker: Creature | None = None) -> Env:
    env = Env(deck0=_deck(0), deck1=_deck(1000), config=EnvConfig(seed=1))
    env.reset()
    assert env.state is not None
    env.state.phase = Phase.ATTACK
    env.state.turn_number = 2
    env.state.players[0].battle_zone.clear()
    env.state.players[1].battle_zone.clear()
    env.state.players[0].battle_zone.append(
        Creature(Card(id=9001, name="Attacker", cost=1, power=attacker_power), summoned_turn=1)
    )
    env.state.players[1].shields = [Card(id=2000 + i, name=f"S{i}", cost=1, power=1000) for i in range(4)]
    env.state.players[1].shields.append(shield_card)
    if blocker is not None:
        env.state.players[1].battle_zone.append(blocker)
    return env


def _blocker() -> Creature:
    return Creature(Card(id=9100, name="Blocker", cost=1, power=5000, blocker=True), summoned_turn=1)


def test_card_and_deck_can_have_shield_triggers() -> None:
    card = Card(
        id=1,
        name="Burst",
        cost=1,
        power=0,
        shield_trigger=True,
        card_type="SPELL",
        trigger_effect="DRAW_1",
    )
    deck = make_vanilla_deck()

    assert card.shield_trigger
    assert card.card_type == "SPELL"
    assert card.trigger_effect == "DRAW_1"
    assert 6 <= sum(1 for deck_card in deck if deck_card.shield_trigger) <= 8


def test_normal_shield_break_adds_card_to_hand_not_graveyard() -> None:
    shield = Card(id=3001, name="Normal Shield", cost=1, power=1000)
    env = _trigger_env(shield)
    defender = env.state.players[1]
    hand_before = len(defender.hand)

    _obs, _reward, _done, info = env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))

    assert info["shield_broken"]
    assert not info["trigger_activated"]
    assert shield in defender.hand
    assert shield not in defender.graveyard
    assert len(defender.hand) == hand_before + 1


def test_draw_1_trigger_draws_and_goes_to_graveyard() -> None:
    shield = Card(id=3002, name="Draw Trigger", cost=1, power=0, shield_trigger=True, card_type="SPELL", trigger_effect="DRAW_1")
    env = _trigger_env(shield)
    defender = env.state.players[1]
    hand_before = len(defender.hand)

    _obs, _reward, _done, info = env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))

    assert info["trigger_activated"]
    assert info["trigger_effect"] == "DRAW_1"
    assert shield in defender.graveyard
    assert len(defender.hand) == hand_before + 1


def test_destroy_attacker_trigger_destroys_attacker() -> None:
    shield = Card(
        id=3003,
        name="Destroy Trigger",
        cost=1,
        power=0,
        shield_trigger=True,
        card_type="SPELL",
        trigger_effect="DESTROY_ATTACKER",
    )
    env = _trigger_env(shield)

    _obs, _reward, _done, info = env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))

    assert info["trigger_activated"]
    assert info["attacker_destroyed_by_trigger"]
    assert len(env.state.players[0].battle_zone) == 0
    assert shield in env.state.players[1].graveyard


def test_summon_self_trigger_enters_battle_zone() -> None:
    shield = Card(
        id=3004,
        name="Creature Trigger",
        cost=1,
        power=2000,
        shield_trigger=True,
        card_type="CREATURE",
        trigger_effect="SUMMON_SELF",
    )
    env = _trigger_env(shield)

    _obs, _reward, _done, info = env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))

    assert info["trigger_activated"]
    assert info["trigger_effect"] == "SUMMON_SELF"
    assert env.state.players[1].battle_zone[-1].card == shield
    assert not env.state.players[1].battle_zone[-1].tapped


def test_gain_shield_trigger_replaces_broken_shield() -> None:
    shield = Card(id=3005, name="Shield Trigger", cost=1, power=0, shield_trigger=True, card_type="SPELL", trigger_effect="GAIN_SHIELD")
    env = _trigger_env(shield)
    defender = env.state.players[1]
    shields_before = len(defender.shields)

    _obs, _reward, _done, info = env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))

    assert info["trigger_activated"]
    assert info["trigger_effect"] == "GAIN_SHIELD"
    assert len(defender.shields) == shields_before
    assert shield in defender.graveyard


def test_block_prevents_shield_trigger_and_decline_allows_it() -> None:
    shield = Card(
        id=3006,
        name="Destroy Trigger",
        cost=1,
        power=0,
        shield_trigger=True,
        card_type="SPELL",
        trigger_effect="DESTROY_ATTACKER",
    )
    blocked_env = _trigger_env(shield, blocker=_blocker())
    blocked_env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))
    _obs, _reward, _done, block_info = blocked_env.step(Action(ActionType.BLOCK, blocker_index=0))

    assert block_info["blocked"]
    assert not block_info.get("trigger_activated", False)
    assert shield in blocked_env.state.players[1].shields

    declined_env = _trigger_env(shield, blocker=_blocker())
    declined_env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))
    _obs, _reward, _done, decline_info = declined_env.step(Action(ActionType.DECLINE_BLOCK))

    assert decline_info["declined_block"]
    assert decline_info["trigger_activated"]
    assert decline_info["trigger_effect"] == "DESTROY_ATTACKER"


def test_gym_and_selfplay_envs_survive_shield_triggers() -> None:
    gym_env = DuelMastersGymEnv(DuelMastersGymConfig(seed=1, opponent="heuristic"))
    gym_obs, gym_info = gym_env.reset()
    selfplay_env = DuelMastersSelfPlayEnv(SelfPlayConfig(seed=1, fixed_opponent="heuristic"))
    selfplay_obs, selfplay_info = selfplay_env.reset()

    assert gym_obs.shape == gym_env.observation_space.shape
    assert selfplay_obs.shape == selfplay_env.observation_space.shape
    assert len(gym_info["action_mask"]) == ACTION_SPACE_SIZE
    assert len(selfplay_info["action_mask"]) == ACTION_SPACE_SIZE
