from __future__ import annotations

from pathlib import Path

import pytest

from dm_ai_sim.action_encoder import encode_action
from dm_ai_sim.actions import Action, ActionType
from dm_ai_sim.agents.heuristic_agent import HeuristicAgent
from dm_ai_sim.analyze_revolution_change_logs import main as analyze_revolution_change_logs_main
from dm_ai_sim.card import Card
from dm_ai_sim.card_database import load_card_database
from dm_ai_sim.diagnose_reference_deck_02 import main as diagnose_reference_deck_02_main
from dm_ai_sim.env import Env, EnvConfig
from dm_ai_sim.evaluate_revolution_change import main as evaluate_revolution_change_main
from dm_ai_sim.state import Creature, Phase


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_CARDS = ROOT / "data/cards/reference_cards.json"


def test_revolution_change_action_encodes() -> None:
    action = Action(ActionType.REVOLUTION_CHANGE, hand_index=1, attacker_index=2)
    assert encode_action(action) == 394


def test_revolution_change_legal_and_resolves_without_payment() -> None:
    env = _revolution_env()
    state = env.state
    assert state is not None
    action = Action(ActionType.REVOLUTION_CHANGE, hand_index=0, attacker_index=0)

    assert action in env.legal_actions()
    before_count = _zone_count(env)
    _obs, _reward, _done, info = env.step(action)

    assert info["revolution_change"] is True
    assert info["revolution_change_card_name"] == "轟く革命 レッドギラゾーン"
    assert info["revolution_change_returned_card_name"] == "特攻の忠剣ハチ公"
    assert len(state.players[0].mana) == 0
    assert state.players[0].hand[-1].name == "特攻の忠剣ハチ公"
    assert state.players[0].battle_zone[-1].card.name == "轟く革命 レッドギラゾーン"
    assert _zone_count(env) == before_count


def test_revolution_change_blocked_during_pending_attack() -> None:
    env = _revolution_env(with_blocker=True)
    env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))

    assert all(action.type != ActionType.REVOLUTION_CHANGE for action in env.legal_actions())
    with pytest.raises(ValueError):
        env.step(Action(ActionType.REVOLUTION_CHANGE, hand_index=0, attacker_index=0))


def test_revolution_change_action_mask() -> None:
    env = _revolution_env(include_action_mask=True)
    action = Action(ActionType.REVOLUTION_CHANGE, hand_index=0, attacker_index=0)
    observation = env.get_observation(include_action_mask=True)

    assert action in env.legal_actions()
    assert observation["action_mask"][encode_action(action)] == 1


def test_heuristic_agent_uses_revolution_change_without_error() -> None:
    env = _revolution_env()
    action = HeuristicAgent().act(env.legal_actions(), env.get_observation())

    assert action.type == ActionType.REVOLUTION_CHANGE


def test_revolution_change_clis_run(tmp_path: Path, capsys) -> None:
    evaluate_revolution_change_main(games=1)
    assert "revolution_change_activations:" in capsys.readouterr().out

    analyze_revolution_change_logs_main(games=1, output_path=tmp_path / "revolution.jsonl")
    output = capsys.readouterr().out
    assert "red_girazon_entries:" in output
    assert (tmp_path / "revolution.jsonl").exists()


def test_diagnose_revolution_change_is_implemented(capsys) -> None:
    diagnose_reference_deck_02_main()
    output = capsys.readouterr().out
    unsupported_section = output.split("unsupported_tag_summary:", 1)[1].split("unsupported_counts_by_tag:", 1)[0]
    assert "REVOLUTION_CHANGE" not in unsupported_section


def _revolution_env(with_blocker: bool = False, include_action_mask: bool = False) -> Env:
    database = load_card_database(REFERENCE_CARDS)
    red = database.to_runtime_card("DM_REF_015", strict=False)
    hachiko = database.to_runtime_card("DM_REF_014", strict=True)
    deck = [Card(id=1000 + i, name=f"C{i}", cost=1, power=1000, civilizations=("FIRE",)) for i in range(40)]
    env = Env(deck0=list(deck), deck1=list(deck), config=EnvConfig(seed=1, include_action_mask=include_action_mask))
    env.reset()
    state = env.state
    assert state is not None
    state.current_player = 0
    state.phase = Phase.ATTACK
    state.players[0].hand = [red]
    state.players[0].mana = []
    state.players[0].battle_zone = [Creature(card=hachiko, tapped=False, summoned_turn=state.turn_number)]
    state.players[1].battle_zone = []
    state.players[1].shields = [Card(id=9999, name="Shield", cost=1, power=1000, civilizations=("FIRE",))]
    if with_blocker:
        state.players[1].battle_zone = [Creature(card=Card(id=3000, name="Blocker", cost=1, power=1000, civilizations=("FIRE",), blocker=True))]
    return env


def _zone_count(env: Env) -> int:
    assert env.state is not None
    return sum(
        len(player.deck) + len(player.hand) + len(player.mana) + len(player.battle_zone) + len(player.graveyard) + len(player.shields)
        for player in env.state.players
    )
