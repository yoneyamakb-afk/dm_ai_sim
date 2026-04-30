from __future__ import annotations

from pathlib import Path

from dm_ai_sim.actions import Action, ActionType
from dm_ai_sim.analyze_gstrike_logs import main as analyze_gstrike_logs_main
from dm_ai_sim.card import Card
from dm_ai_sim.card_database import load_card_database
from dm_ai_sim.diagnose_reference_deck_02 import main as diagnose_reference_deck_02_main
from dm_ai_sim.env import Env, EnvConfig
from dm_ai_sim.evaluate_gstrike import main as evaluate_gstrike_main
from dm_ai_sim.state import Creature, Phase


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_CARDS = ROOT / "data/cards/reference_cards.json"


def test_gstrike_from_shield_activates_and_adds_to_hand() -> None:
    prin = load_card_database(REFERENCE_CARDS).to_runtime_card("DM_REF_020", strict=True)
    env = _gstrike_env(prin)

    _obs, _reward, _done, info = env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))

    state = env.state
    assert state is not None
    assert info["g_strike_activated"] is True
    assert info["g_strike_card_name"] == "綺羅王女プリン / ハンター☆エイリアン仲良しビーム"
    assert state.players[1].hand[-1].name == "綺羅王女プリン / ハンター☆エイリアン仲良しビーム"


def test_gstrike_target_cannot_attack_until_turn_changes() -> None:
    prin = load_card_database(REFERENCE_CARDS).to_runtime_card("DM_REF_020", strict=True)
    env = _gstrike_env(prin)
    state = env.state
    assert state is not None

    env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))

    assert state.players[0].battle_zone[0].cannot_attack_this_turn is True
    assert all(action.attacker_index != 0 for action in env.legal_actions() if action.type in {ActionType.ATTACK_SHIELD, ActionType.ATTACK_PLAYER})
    env.step(Action(ActionType.END_ATTACK))
    assert state.players[0].battle_zone[0].cannot_attack_this_turn is False


def test_gstrike_target_selection_prefers_attack_capable_speed_attacker() -> None:
    prin = load_card_database(REFERENCE_CARDS).to_runtime_card("DM_REF_020", strict=True)
    env = _gstrike_env(prin)
    state = env.state
    assert state is not None
    state.players[0].battle_zone = [
        Creature(card=Card(id=11, name="Old Big", cost=5, power=9000, civilizations=("FIRE",)), tapped=False, summoned_turn=state.turn_number),
        Creature(card=Card(id=12, name="Speed Small", cost=2, power=1000, civilizations=("FIRE",), ability_tags=("SPEED_ATTACKER",)), tapped=False, summoned_turn=state.turn_number),
    ]

    _obs, _reward, _done, info = env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=1))

    assert info["g_strike_target_name"] == "Speed Small"


def test_gachinko_prin_ruling_logs_bottom_spell_cost() -> None:
    database = load_card_database(REFERENCE_CARDS)
    hachiko = database.to_runtime_card("DM_REF_014", strict=True)
    prin = database.to_runtime_card("DM_REF_020", strict=True)
    env = _gstrike_env(Card(id=99, name="Shield", cost=1, power=1000, civilizations=("FIRE",)))
    state = env.state
    assert state is not None
    state.players[0].battle_zone = [Creature(card=hachiko, tapped=False, summoned_turn=state.turn_number)]
    state.players[0].deck = [hachiko, prin]
    state.players[1].deck = [Card(id=100, name="Judge Low", cost=1, power=1000, civilizations=("FIRE",))]

    _obs, _reward, _done, info = env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))

    assert info["gachinko_revealed_twinpact"] is True
    assert info["gachinko_revealed_card_name"] == "綺羅王女プリン / ハンター☆エイリアン仲良しビーム"
    assert info["gachinko_judge_cost_source"] == "bottom_spell_cost"
    assert info["gachinko_prin_ruling_applicable"] is True
    assert info["gachinko_attacker_cost"] == 5


def test_gstrike_clis_run(tmp_path: Path, capsys) -> None:
    evaluate_gstrike_main(games=1)
    assert "g_strike_activations:" in capsys.readouterr().out

    analyze_gstrike_logs_main(games=1, output_path=tmp_path / "gstrike.jsonl")
    output = capsys.readouterr().out
    assert "attacks_prevented:" in output
    assert (tmp_path / "gstrike.jsonl").exists()


def test_diagnose_gstrike_is_implemented(capsys) -> None:
    diagnose_reference_deck_02_main()
    output = capsys.readouterr().out

    assert "G_STRIKE" not in output.split("unsupported_tag_summary:", 1)[1].split("unsupported_counts_by_tag:", 1)[0]
    assert "runtime_convertible_count: 21" in output


def _gstrike_env(shield_card: Card) -> Env:
    deck = [Card(id=1000 + i, name=f"C{i}", cost=1, power=1000, civilizations=("FIRE",)) for i in range(40)]
    env = Env(deck0=list(deck), deck1=list(deck), config=EnvConfig(seed=1))
    env.reset()
    state = env.state
    assert state is not None
    state.current_player = 0
    state.phase = Phase.ATTACK
    state.players[0].battle_zone = [
        Creature(card=Card(id=1, name="特攻の忠剣ハチ公", cost=4, power=3000, civilizations=("FIRE",), ability_tags=("SPEED_ATTACKER",)), tapped=False, summoned_turn=state.turn_number)
    ]
    state.players[1].battle_zone = []
    state.players[1].shields = [shield_card]
    return env
