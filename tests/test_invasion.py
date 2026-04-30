from __future__ import annotations

from pathlib import Path

import pytest

from dm_ai_sim.action_encoder import encode_action
from dm_ai_sim.actions import Action, ActionType
from dm_ai_sim.agents.heuristic_agent import HeuristicAgent
from dm_ai_sim.analyze_invasion_logs import main as analyze_invasion_logs_main
from dm_ai_sim.card import Card
from dm_ai_sim.card_database import load_card_database
from dm_ai_sim.diagnose_reference_deck_02 import main as diagnose_reference_deck_02_main
from dm_ai_sim.env import Env, EnvConfig
from dm_ai_sim.evaluate_invasion import main as evaluate_invasion_main
from dm_ai_sim.state import Creature, Phase


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_CARDS = ROOT / "data/cards/reference_cards.json"


def test_invasion_action_encodes() -> None:
    action = Action(ActionType.INVASION, hand_index=1, attacker_index=2)
    assert encode_action(action) == 522


def test_invasion_legal_and_resolves_without_payment() -> None:
    env = _invasion_env()
    state = env.state
    assert state is not None
    action = Action(ActionType.INVASION, hand_index=0, attacker_index=0)

    assert action in env.legal_actions()
    before_count = _zone_count(env)
    _obs, _reward, _done, info = env.step(action)

    assert info["invasion"] is True
    assert info["invasion_card_name"] == "熱き侵略 レッドゾーンZ"
    assert info["invasion_source_card_name"] == "特攻の忠剣ハチ公"
    assert len(state.players[0].mana) == 0
    assert len(state.players[0].hand) == 0
    evolved = state.players[0].battle_zone[-1]
    assert evolved.card.name == "熱き侵略 レッドゾーンZ"
    assert [card.name for card in evolved.evolution_sources] == ["特攻の忠剣ハチ公"]
    assert _zone_count(env) == before_count
    assert not env.validate_invariants()


def test_invasion_creature_is_attackable_after_entering() -> None:
    env = _invasion_env()
    env.step(Action(ActionType.INVASION, hand_index=0, attacker_index=0))

    assert any(action.type == ActionType.ATTACK_SHIELD and action.attacker_index == 0 for action in env.legal_actions())


def test_evolved_creature_destruction_moves_top_and_sources_to_graveyard() -> None:
    env = _invasion_env()
    state = env.state
    assert state is not None
    env.step(Action(ActionType.INVASION, hand_index=0, attacker_index=0))
    state.players[1].deck.pop()
    state.players[1].battle_zone = [
        Creature(card=Card(id=5000, name="Large Defender", cost=7, power=12000, civilizations=("FIRE",)), summoned_turn=0)
    ]

    env.step(Action(ActionType.ATTACK_CREATURE, attacker_index=0, target_index=0))

    graveyard_names = [card.name for card in state.players[0].graveyard]
    assert "熱き侵略 レッドゾーンZ" in graveyard_names
    assert "特攻の忠剣ハチ公" in graveyard_names
    assert not env.validate_invariants()


def test_invasion_blocked_during_pending_attack() -> None:
    env = _invasion_env(with_blocker=True)
    env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))

    assert all(action.type != ActionType.INVASION for action in env.legal_actions())
    with pytest.raises(ValueError):
        env.step(Action(ActionType.INVASION, hand_index=0, attacker_index=0))


def test_invasion_action_mask() -> None:
    env = _invasion_env(include_action_mask=True)
    action = Action(ActionType.INVASION, hand_index=0, attacker_index=0)
    observation = env.get_observation(include_action_mask=True)

    assert action in env.legal_actions()
    assert observation["action_mask"][encode_action(action)] == 1


def test_heuristic_agent_uses_invasion_without_error() -> None:
    env = _invasion_env()
    action = HeuristicAgent().act(env.legal_actions(), env.get_observation())

    assert action.type == ActionType.INVASION


def test_invasion_clis_run(tmp_path: Path, capsys) -> None:
    evaluate_invasion_main(games=1)
    assert "invasion_activations:" in capsys.readouterr().out

    analyze_invasion_logs_main(games=1, output_path=tmp_path / "invasion.jsonl")
    output = capsys.readouterr().out
    assert "red_zone_z_entries:" in output
    assert (tmp_path / "invasion.jsonl").exists()


def test_diagnose_invasion_is_implemented(capsys) -> None:
    diagnose_reference_deck_02_main()
    output = capsys.readouterr().out
    unsupported_section = output.split("unsupported_tag_summary:", 1)[1].split("unsupported_counts_by_tag:", 1)[0]
    implemented_section = output.split("blocked_reasons:", 1)[0]
    assert "INVASION" not in unsupported_section
    assert "EVOLUTION" not in unsupported_section
    assert "INVASION" not in implemented_section.split("high_priority_missing_tags:", 1)[1]


def _invasion_env(with_blocker: bool = False, include_action_mask: bool = False) -> Env:
    database = load_card_database(REFERENCE_CARDS)
    red_zone = database.to_runtime_card("DM_REF_016", strict=False)
    hachiko = database.to_runtime_card("DM_REF_014", strict=True)
    deck = [Card(id=1000 + i, name=f"C{i}", cost=1, power=1000, civilizations=("FIRE",)) for i in range(40)]
    env = Env(deck0=list(deck), deck1=list(deck), config=EnvConfig(seed=1, include_action_mask=include_action_mask))
    env.reset()
    state = env.state
    assert state is not None
    state.current_player = 0
    state.phase = Phase.ATTACK
    state.players[0].deck = [Card(id=10_000 + i, name=f"P0D{i}", cost=1, power=1000, civilizations=("FIRE",)) for i in range(33)]
    state.players[0].hand = [red_zone]
    state.players[0].mana = []
    state.players[0].battle_zone = [Creature(card=hachiko, tapped=False, summoned_turn=state.turn_number)]
    state.players[0].graveyard = []
    state.players[0].shields = [Card(id=11_000 + i, name=f"P0S{i}", cost=1, power=1000, civilizations=("FIRE",)) for i in range(5)]
    state.players[1].deck = [Card(id=12_000 + i, name=f"P1D{i}", cost=1, power=1000, civilizations=("FIRE",)) for i in range(34)]
    state.players[1].hand = []
    state.players[1].mana = []
    state.players[1].battle_zone = []
    state.players[1].graveyard = []
    state.players[1].shields = [Card(id=13_000 + i, name=f"P1S{i}", cost=1, power=1000, civilizations=("FIRE",)) for i in range(6)]
    if with_blocker:
        state.players[1].deck.pop()
        state.players[1].battle_zone = [
            Creature(card=Card(id=3000, name="Blocker", cost=1, power=1000, civilizations=("FIRE",), blocker=True))
        ]
    return env


def _zone_count(env: Env) -> int:
    assert env.state is not None
    return sum(
        len(player.deck)
        + len(player.hand)
        + len(player.mana)
        + sum(1 + len(creature.evolution_sources) for creature in player.battle_zone)
        + len(player.graveyard)
        + len(player.shields)
        for player in env.state.players
    )
