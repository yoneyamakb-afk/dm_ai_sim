from dm_ai_sim.action_encoder import ACTION_SPACE_SIZE, encode_action, legal_action_mask
from dm_ai_sim.actions import Action, ActionType
from dm_ai_sim.card import Card
from dm_ai_sim.env import Env, EnvConfig
from dm_ai_sim.gym_env import DuelMastersGymConfig, DuelMastersGymEnv
from dm_ai_sim.selfplay_env import DuelMastersSelfPlayEnv, SelfPlayConfig
from dm_ai_sim.state import Creature, ManaCard, Phase


def _deck(base_id: int = 0) -> list[Card]:
    return [Card(id=base_id + i, name=f"C{base_id + i}", cost=1, power=1000) for i in range(40)]


def _spell_env(spell: Card, opponent_creature: Creature | None = None, mana_count: int = 3) -> Env:
    env = Env(deck0=_deck(0), deck1=_deck(1000), config=EnvConfig(seed=1))
    env.reset()
    assert env.state is not None
    state = env.state
    state.phase = Phase.MAIN
    state.current_player = 0
    state.players[0].hand = [spell]
    state.players[0].mana = [ManaCard(Card(id=8000 + i, name=f"M{i}", cost=1, power=1000)) for i in range(mana_count)]
    state.players[0].graveyard.clear()
    state.players[1].battle_zone.clear()
    if opponent_creature is not None:
        state.players[1].battle_zone.append(opponent_creature)
    return env


def _spell(effect: str, cost: int = 1) -> Card:
    return Card(id=9000, name=f"{effect} Spell", cost=cost, power=0, card_type="SPELL", spell_effect=effect)


def test_cast_spell_action_can_be_created() -> None:
    action = Action(ActionType.CAST_SPELL, hand_index=1, target_index=2)

    assert action.hand_index == 1
    assert action.target_index == 2


def test_draw_1_spell_draws_and_goes_to_graveyard() -> None:
    env = _spell_env(_spell("DRAW_1"))
    player = env.state.players[0]
    hand_before = len(player.hand)

    _obs, _reward, _done, info = env.step(Action(ActionType.CAST_SPELL, hand_index=0))

    assert info["spell_cast"]
    assert info["spell_effect"] == "DRAW_1"
    assert len(player.hand) == hand_before
    assert player.graveyard[-1].spell_effect == "DRAW_1"
    assert player.mana[0].tapped


def test_destroy_target_spell_destroys_opponent_creature() -> None:
    target = Creature(Card(id=9100, name="Target", cost=1, power=3000, blocker=True), summoned_turn=1)
    env = _spell_env(_spell("DESTROY_TARGET"), opponent_creature=target)

    _obs, _reward, _done, info = env.step(Action(ActionType.CAST_SPELL, hand_index=0, target_index=0))

    assert info["spell_effect"] == "DESTROY_TARGET"
    assert len(env.state.players[1].battle_zone) == 0
    assert env.state.players[1].graveyard[-1].name == "Target"
    assert env.state.players[0].graveyard[-1].spell_effect == "DESTROY_TARGET"


def test_gain_shield_spell_adds_shield() -> None:
    env = _spell_env(_spell("GAIN_SHIELD"))
    shields_before = len(env.state.players[0].shields)

    _obs, _reward, _done, info = env.step(Action(ActionType.CAST_SPELL, hand_index=0))

    assert info["spell_effect"] == "GAIN_SHIELD"
    assert len(env.state.players[0].shields) == shields_before + 1


def test_mana_boost_spell_adds_mana() -> None:
    env = _spell_env(_spell("MANA_BOOST"))
    mana_before = len(env.state.players[0].mana)

    _obs, _reward, _done, info = env.step(Action(ActionType.CAST_SPELL, hand_index=0))

    assert info["spell_effect"] == "MANA_BOOST"
    assert len(env.state.players[0].mana) == mana_before + 1
    assert not env.state.players[0].mana[-1].tapped


def test_spell_is_not_legal_without_enough_mana() -> None:
    env = _spell_env(_spell("DRAW_1", cost=3), mana_count=2)

    assert not any(action.type == ActionType.CAST_SPELL for action in env.legal_actions())


def test_target_spell_requires_target() -> None:
    env = _spell_env(_spell("DESTROY_TARGET"), opponent_creature=None)

    assert not any(action.type == ActionType.CAST_SPELL for action in env.legal_actions())


def test_cast_spell_illegal_during_pending_attack() -> None:
    env = _spell_env(_spell("DRAW_1"))
    assert env.state is not None
    env.state.pending_attack = object()  # type: ignore[assignment]

    try:
        env.step(Action(ActionType.CAST_SPELL, hand_index=0))
    except ValueError:
        pass
    else:
        raise AssertionError("CAST_SPELL should fail during pending attack.")


def test_cast_spell_action_id_and_mask() -> None:
    env = _spell_env(_spell("DRAW_1"))
    action = Action(ActionType.CAST_SPELL, hand_index=0)
    action_id = encode_action(action)
    mask = legal_action_mask(env)

    assert action_id == 256
    assert action_id in env.legal_action_ids()
    assert mask[action_id] == 1
    assert len(mask) == ACTION_SPACE_SIZE


def test_gym_and_selfplay_envs_survive_spells() -> None:
    gym_env = DuelMastersGymEnv(DuelMastersGymConfig(seed=1, opponent="heuristic"))
    gym_obs, gym_info = gym_env.reset()
    selfplay_env = DuelMastersSelfPlayEnv(SelfPlayConfig(seed=1, fixed_opponent="heuristic"))
    selfplay_obs, selfplay_info = selfplay_env.reset()

    assert gym_obs.shape == gym_env.observation_space.shape
    assert selfplay_obs.shape == selfplay_env.observation_space.shape
    assert len(gym_info["action_mask"]) == ACTION_SPACE_SIZE
    assert len(selfplay_info["action_mask"]) == ACTION_SPACE_SIZE
