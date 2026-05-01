from __future__ import annotations

from dm_ai_sim.actions import Action, ActionType
from dm_ai_sim.card import Card
from dm_ai_sim.env import Env, EnvConfig
from dm_ai_sim.shield_breaks import break_one_shield, break_shields
from dm_ai_sim.state import Creature, Phase


def test_break_one_shield_adds_normal_card_to_hand() -> None:
    shield = _card(200, "Normal Shield")
    env = _shield_break_env([shield])
    info: dict = {}

    result = break_one_shield(env, 0, 1, 0, 0, info)

    assert result["shield_broken"]
    assert result["card_added_to_hand"]
    assert shield in env.state.players[1].hand
    assert info["broken_shield_card"] == "Normal Shield"


def test_break_one_shield_activates_shield_trigger_and_moves_spell_to_graveyard() -> None:
    shield = Card(id=201, name="Draw Trigger", cost=1, power=0, shield_trigger=True, card_type="SPELL", trigger_effect="DRAW_1")
    env = _shield_break_env([shield])
    info: dict = {}

    result = break_one_shield(env, 0, 1, 0, 0, info)

    assert result["trigger_activated"]
    assert result["trigger_effect"] == "DRAW_1"
    assert result["moved_to_graveyard"]
    assert shield in env.state.players[1].graveyard
    assert info["trigger_activated"]


def test_break_one_shield_activates_gstrike_and_adds_card_to_hand() -> None:
    shield = _card(202, "G Strike", tags=("G_STRIKE",))
    env = _shield_break_env([shield])
    env.state.players[0].battle_zone.append(
        Creature(card=_card(203, "Ready Speed", tags=("SPEED_ATTACKER",)), summoned_turn=env.state.turn_number)
    )
    info: dict = {}

    result = break_one_shield(env, 0, 1, 0, 0, info)

    assert result["g_strike_activated"]
    assert result["card_added_to_hand"]
    assert shield in env.state.players[1].hand
    assert info["g_strike_target_name"] == "Ready Speed"


def test_blocked_attack_does_not_break_shield() -> None:
    shield = _card(204, "Protected Shield")
    env = _shield_break_env([shield], with_blocker=True)
    shields_before = len(env.state.players[1].shields)

    env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))
    _obs, _reward, _done, info = env.step(Action(ActionType.BLOCK, blocker_index=0))

    assert info["blocked"]
    assert len(env.state.players[1].shields) == shields_before
    assert shield in env.state.players[1].shields


def test_break_shields_can_process_two_cards_in_order() -> None:
    bottom = _card(205, "Bottom Shield")
    top = _card(206, "Top Shield")
    env = _shield_break_env([bottom, top])
    info: dict = {}

    results = break_shields(env, 0, 1, 2, 0, info)

    assert [result["broken_card_name"] for result in results] == ["Top Shield", "Bottom Shield"]
    assert all(result["removed_from_shield_zone_before_resolution"] for result in results)
    assert [result["break_index"] for result in results] == [0, 1]
    assert [result["simultaneous_count"] for result in results] == [2, 2]
    assert top in env.state.players[1].hand
    assert bottom in env.state.players[1].hand
    assert len(env.state.players[1].shields) == 0


def test_break_shields_count_two_with_one_shield_does_not_fail() -> None:
    shield = _card(207, "Only Shield")
    env = _shield_break_env([shield])
    info: dict = {}

    results = break_shields(env, 0, 1, 2, 0, info)

    assert len(results) == 1
    assert results[0]["broken_card_name"] == "Only Shield"
    assert len(env.state.players[1].shields) == 0


def test_destroy_attacker_trigger_preserves_info() -> None:
    shield = Card(
        id=208,
        name="Destroy Trigger",
        cost=1,
        power=0,
        shield_trigger=True,
        card_type="SPELL",
        trigger_effect="DESTROY_ATTACKER",
    )
    env = _shield_break_env([shield])
    info: dict = {}

    result = break_one_shield(env, 0, 1, 0, 0, info)

    assert result["attacker_destroyed_by_trigger"]
    assert info["attacker_destroyed_by_trigger"]
    assert shield in env.state.players[1].graveyard
    assert not env.state.players[0].battle_zone


def test_break_shields_count_two_processes_trigger_and_normal_even_if_attacker_destroyed() -> None:
    destroy = Card(
        id=209,
        name="Destroy Trigger",
        cost=1,
        power=0,
        shield_trigger=True,
        card_type="SPELL",
        trigger_effect="DESTROY_ATTACKER",
    )
    normal = _card(210, "Normal After Destroy")
    env = _shield_break_env([normal, destroy])
    info: dict = {}

    results = break_shields(env, 0, 1, 2, 0, info)

    assert [result["broken_card_name"] for result in results] == ["Destroy Trigger", "Normal After Destroy"]
    assert results[0]["attacker_destroyed_by_trigger"]
    assert results[1]["card_added_to_hand"]
    assert normal in env.state.players[1].hand
    assert destroy in env.state.players[1].graveyard
    assert not env.state.players[0].battle_zone
    assert len(env.state.players[1].shields) == 0


def test_break_shields_count_two_processes_gstrike_and_keeps_card_in_hand() -> None:
    normal = _card(211, "Normal Shield")
    gstrike = _card(212, "G Strike Shield", tags=("G_STRIKE",))
    env = _shield_break_env([normal, gstrike])
    env.state.players[0].battle_zone.append(
        Creature(card=_card(213, "Ready Speed", tags=("SPEED_ATTACKER",)), summoned_turn=env.state.turn_number)
    )
    info: dict = {}

    results = break_shields(env, 0, 1, 2, 0, info)

    assert results[0]["g_strike_activated"]
    assert gstrike in env.state.players[1].hand
    assert normal in env.state.players[1].hand
    assert info["g_strike_target_name"] == "Ready Speed"


def test_break_shields_count_two_removes_all_targets_before_resolution() -> None:
    normal = _card(214, "Normal Shield")
    gain = Card(id=215, name="Gain Shield", cost=1, power=0, shield_trigger=True, card_type="SPELL", trigger_effect="GAIN_SHIELD")
    env = _shield_break_env([normal, gain])
    shields_before = len(env.state.players[1].shields)
    info: dict = {}

    results = break_shields(env, 0, 1, 2, 0, info)

    assert len(results) == 2
    assert all(result["simultaneous_count"] == 2 for result in results)
    assert gain in env.state.players[1].graveyard
    assert normal in env.state.players[1].hand
    assert len(env.state.players[1].shields) == shields_before - 1


def _shield_break_env(shields: list[Card], with_blocker: bool = False) -> Env:
    deck0 = [_card(1000 + index, f"A{index}") for index in range(40)]
    deck1 = [_card(2000 + index, f"D{index}") for index in range(40)]
    env = Env(deck0=deck0, deck1=deck1, config=EnvConfig(seed=1))
    env.reset()
    state = env.state
    assert state is not None
    state.current_player = 0
    state.phase = Phase.ATTACK
    state.turn_number = 2
    state.players[0].battle_zone = [Creature(card=_card(100, "Attacker"), summoned_turn=1)]
    state.players[1].battle_zone = []
    state.players[1].shields = list(shields)
    if with_blocker:
        state.players[1].battle_zone.append(Creature(card=_card(101, "Blocker", blocker=True), summoned_turn=1))
    return env


def _card(card_id: int, name: str, tags: tuple[str, ...] = (), blocker: bool = False) -> Card:
    return Card(id=card_id, name=name, cost=1, power=1000, civilizations=("FIRE",), ability_tags=tags, blocker=blocker)
