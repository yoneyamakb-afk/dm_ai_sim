from __future__ import annotations

from pathlib import Path

from dm_ai_sim.actions import Action, ActionType
from dm_ai_sim.agents.heuristic_agent import HeuristicAgent
from dm_ai_sim.analyze_cost_reduction_logs import main as analyze_cost_reduction_logs_main
from dm_ai_sim.card import Card
from dm_ai_sim.card_database import load_card_database
from dm_ai_sim.diagnose_reference_deck_02 import main as diagnose_reference_deck_02_main
from dm_ai_sim.env import Env, EnvConfig
from dm_ai_sim.evaluate_cost_reduction import main as evaluate_cost_reduction_main
from dm_ai_sim.state import CostReductionEffect, Creature, ManaCard, Phase


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_CARDS = ROOT / "data/cards/reference_cards.json"


def test_fairy_gift_cast_creates_next_creature_cost_reduction() -> None:
    gift = _fairy_gift()
    env = _main_env([gift], [_mana("N", "NATURE")])

    _obs, _reward, _done, info = env.step(Action(ActionType.CAST_SPELL, hand_index=0))

    player = env.state.players[0]
    assert info["cost_reduction_created"] is True
    assert info["cost_reduction_source"] == "フェアリー・ギフト"
    assert info["cost_reduction_amount"] == 3
    assert info["cost_reduction_applies_to"] == "CREATURE"
    assert player.pending_cost_reductions[0].amount == 3
    assert player.graveyard[-1].name == "フェアリー・ギフト"


def test_next_creature_summon_uses_reduction_and_clears_effect() -> None:
    gift = _fairy_gift()
    creature = _creature(10, "Fire Four", cost=4, civilization="FIRE")
    env = _main_env([gift, creature], [_mana("N", "NATURE"), _mana("F", "FIRE")])

    env.step(Action(ActionType.CAST_SPELL, hand_index=0))
    action = Action(ActionType.SUMMON, card_index=0)
    assert action in env.legal_actions()
    _obs, _reward, _done, info = env.step(action)

    player = env.state.players[0]
    assert info["cost_reduction_used"] is True
    assert info["original_cost"] == 4
    assert info["effective_cost"] == 1
    assert info["mana_paid"] == 1
    assert info["summons_enabled_by_reduction"] is True
    assert not player.pending_cost_reductions


def test_cost_reduction_does_not_remove_civilization_requirement() -> None:
    gift = _fairy_gift()
    creature = _creature(20, "Fire Four", cost=4, civilization="FIRE")
    env = _main_env([gift, creature], [_mana("N", "NATURE"), _mana("W", "WATER")])

    env.step(Action(ActionType.CAST_SPELL, hand_index=0))

    assert Action(ActionType.SUMMON, card_index=0) not in env.legal_actions()


def test_reduced_summon_pays_fewer_mana() -> None:
    gift = _fairy_gift()
    creature = _creature(30, "Nature Five", cost=5, civilization="NATURE")
    mana = [_mana("N0", "NATURE"), _mana("N1", "NATURE"), _mana("N2", "NATURE")]
    env = _main_env([gift, creature], mana)

    env.step(Action(ActionType.CAST_SPELL, hand_index=0))
    _obs, _reward, _done, info = env.step(Action(ActionType.SUMMON, card_index=0))

    assert info["effective_cost"] == 2
    assert info["mana_paid"] == 2


def test_unused_cost_reduction_expires_at_turn_end() -> None:
    gift = _fairy_gift()
    env = _main_env([gift], [_mana("N", "NATURE")])

    env.step(Action(ActionType.CAST_SPELL, hand_index=0))
    env.step(Action(ActionType.END_MAIN))
    _obs, _reward, _done, info = env.step(Action(ActionType.END_ATTACK))

    assert info["cost_reduction_expired"] is True
    assert not env.state.players[0].pending_cost_reductions


def test_cost_reduction_does_not_apply_to_spell_casts() -> None:
    gift = _fairy_gift()
    spell = Card(id=40, name="Fire Draw", cost=4, power=0, civilizations=("FIRE",), card_type="SPELL", spell_effect="DRAW_1")
    env = _main_env([gift, spell], [_mana("N", "NATURE"), _mana("F", "FIRE")])

    env.step(Action(ActionType.CAST_SPELL, hand_index=0))

    assert all(action.type != ActionType.CAST_SPELL for action in env.legal_actions())
    assert env.state.players[0].pending_cost_reductions


def test_cost_reduction_applies_to_twinpact_top_creature_summon() -> None:
    gift = _fairy_gift()
    twin = load_card_database(REFERENCE_CARDS).to_runtime_card("DM_REF_017", strict=True)
    env = _main_env([gift, twin], [_mana("N0", "NATURE"), _mana("N1", "NATURE"), _mana("N2", "NATURE")])

    env.step(Action(ActionType.CAST_SPELL, hand_index=0))
    action = Action(ActionType.SUMMON, card_index=0, side="top")
    assert action in env.legal_actions()
    _obs, _reward, _done, info = env.step(action)

    assert info["side_used"] == "top"
    assert info["cost_reduction_used"] is True
    assert info["original_cost"] == 5
    assert info["effective_cost"] == 2


def test_cost_reduction_does_not_apply_to_revolution_change() -> None:
    env = _attack_env_with_pending_reduction()
    change = _creature(50, "Change", cost=8, civilization="FIRE", tags=("REVOLUTION_CHANGE",))
    env.state.players[0].hand = [change]

    _obs, _reward, _done, info = env.step(Action(ActionType.REVOLUTION_CHANGE, hand_index=0, attacker_index=0))

    assert info["revolution_change"] is True
    assert info["cost_reduction_used"] is False
    assert env.state.players[0].pending_cost_reductions


def test_cost_reduction_does_not_apply_to_invasion() -> None:
    env = _attack_env_with_pending_reduction()
    invasion = _creature(60, "Invasion", cost=6, civilization="FIRE", tags=("INVASION",))
    env.state.players[0].hand = [invasion]

    _obs, _reward, _done, info = env.step(Action(ActionType.INVASION, hand_index=0, attacker_index=0))

    assert info["invasion"] is True
    assert info["cost_reduction_used"] is False
    assert env.state.players[0].pending_cost_reductions


def test_cost_reduction_does_not_apply_to_shield_trigger_summon_self() -> None:
    trigger = Card(id=70, name="Trigger Creature", cost=4, power=2000, civilizations=("NATURE",), shield_trigger=True, card_type="CREATURE", trigger_effect="SUMMON_SELF")
    env = _attack_env_with_pending_reduction(player_id=1)
    env.state.players[1].shields = [trigger]

    env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))

    assert env.state.players[1].battle_zone[-1].card.name == "Trigger Creature"
    assert env.state.players[1].pending_cost_reductions


def test_cost_reduction_does_not_apply_to_hachiko_same_name_summon() -> None:
    database = load_card_database(REFERENCE_CARDS)
    hachiko = database.to_runtime_card("DM_REF_014", strict=True)
    env = _attack_env_with_pending_reduction()
    state = env.state
    state.players[0].battle_zone = [Creature(card=hachiko, tapped=False, summoned_turn=state.turn_number)]
    state.players[0].deck = [hachiko]
    state.players[1].deck = [_creature(80, "Judge Low", cost=1, civilization="FIRE")]

    env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))

    assert len(state.players[0].battle_zone) >= 1
    assert state.players[0].pending_cost_reductions


def test_legal_actions_and_step_use_same_reduced_cost() -> None:
    gift = _fairy_gift()
    creature = _creature(90, "Fire Four", cost=4, civilization="FIRE")
    env = _main_env([gift, creature], [_mana("N", "NATURE"), _mana("F", "FIRE")])

    assert Action(ActionType.SUMMON, card_index=1) not in env.legal_actions()
    env.step(Action(ActionType.CAST_SPELL, hand_index=0))
    action = Action(ActionType.SUMMON, card_index=0)
    assert action in env.legal_actions()
    env.step(action)

    assert not env.validate_invariants()


def test_heuristic_agent_uses_cost_reduction_without_error() -> None:
    gift = _fairy_gift()
    creature = _creature(100, "Fire Four", cost=4, civilization="FIRE")
    env = _main_env([gift, creature], [_mana("N", "NATURE"), _mana("F", "FIRE")])

    action = HeuristicAgent().act(env.legal_actions(), env.get_observation())

    assert action.type == ActionType.CAST_SPELL
    assert action.hand_index == 0


def test_cost_reduction_clis_run(tmp_path: Path, capsys) -> None:
    evaluate_cost_reduction_main(games=1)
    assert "cost_reduction_casts:" in capsys.readouterr().out

    analyze_cost_reduction_logs_main(games=1, output_path=tmp_path / "cost_reduction.jsonl")
    output = capsys.readouterr().out
    assert "summons_enabled_by_reduction:" in output
    assert (tmp_path / "cost_reduction.jsonl").exists()


def test_diagnose_cost_reduction_is_implemented(capsys) -> None:
    diagnose_reference_deck_02_main()
    output = capsys.readouterr().out
    unsupported_section = output.split("unsupported_tag_summary:", 1)[1].split("unsupported_counts_by_tag:", 1)[0]

    assert "COST_REDUCTION" not in unsupported_section


def _fairy_gift() -> Card:
    return load_card_database(REFERENCE_CARDS).to_runtime_card("DM_REF_021", strict=True)


def _main_env(hand: list[Card], mana_cards: list[Card]) -> Env:
    deck = [_creature(1000 + index, f"D{index}", cost=1, civilization="FIRE") for index in range(40)]
    env = Env(deck0=list(deck), deck1=list(deck), config=EnvConfig(seed=1))
    env.reset()
    state = env.state
    assert state is not None
    state.current_player = 0
    state.phase = Phase.MAIN
    state.turn_number = 2
    state.players[0].hand = list(hand)
    state.players[0].mana = [ManaCard(card=card) for card in mana_cards]
    state.players[0].battle_zone = []
    state.players[0].graveyard = []
    state.players[0].deck = [
        _creature(6000 + index, f"P0D{index}", cost=1, civilization="FIRE")
        for index in range(40 - len(state.players[0].hand) - len(state.players[0].mana) - len(state.players[0].shields))
    ]
    return env


def _attack_env_with_pending_reduction(player_id: int = 0) -> Env:
    deck = [_creature(2000 + index, f"D{index}", cost=1, civilization="FIRE") for index in range(40)]
    env = Env(deck0=list(deck), deck1=list(deck), config=EnvConfig(seed=1))
    env.reset()
    state = env.state
    assert state is not None
    state.current_player = 0
    state.phase = Phase.ATTACK
    state.turn_number = 2
    state.players[0].hand = []
    state.players[0].battle_zone = [Creature(card=_creature(3000, "Source", cost=4, civilization="FIRE"), tapped=False, summoned_turn=1)]
    state.players[0].mana = []
    state.players[0].graveyard = []
    state.players[0].deck = [
        _creature(7000 + index, f"P0D{index}", cost=1, civilization="FIRE")
        for index in range(40 - len(state.players[0].battle_zone) - len(state.players[0].shields))
    ]
    state.players[1].battle_zone = []
    state.players[1].shields = [_creature(4000, "Shield", cost=1, civilization="FIRE")]
    state.players[1].hand = []
    state.players[1].mana = []
    state.players[1].graveyard = []
    state.players[1].deck = [
        _creature(8000 + index, f"P1D{index}", cost=1, civilization="FIRE")
        for index in range(40 - len(state.players[1].shields))
    ]
    state.players[player_id].pending_cost_reductions = [
        CostReductionEffect(source_card_name="フェアリー・ギフト", amount=3)
    ]
    return env


def _mana(name: str, civilization: str) -> Card:
    return _creature(5000 + hash(name) % 1000, name, cost=1, civilization=civilization)


def _creature(card_id: int, name: str, cost: int, civilization: str, tags: tuple[str, ...] = ()) -> Card:
    return Card(id=card_id, name=name, cost=cost, power=3000, civilizations=(civilization,), ability_tags=tags)
