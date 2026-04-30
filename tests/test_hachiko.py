from __future__ import annotations

from pathlib import Path

from dm_ai_sim.actions import Action, ActionType
from dm_ai_sim.analyze_hachiko_logs import main as analyze_hachiko_logs_main
from dm_ai_sim.card import Card
from dm_ai_sim.card_database import load_card_database
from dm_ai_sim.deck_compatibility import analyze_deck_compatibility
from dm_ai_sim.deck_loader import load_deck
from dm_ai_sim.diagnose_reference_deck_02 import main as diagnose_reference_deck_02_main
from dm_ai_sim.env import Env, EnvConfig
from dm_ai_sim.evaluate_hachiko import main as evaluate_hachiko_main
from dm_ai_sim.ruleset import load_ruleset, validate_deck_against_ruleset
from dm_ai_sim.state import Creature, Phase


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_CARDS = ROOT / "data/cards/reference_cards.json"
REFERENCE_DECK_02 = ROOT / "data/decks/reference_deck_02.json"
REFERENCE_RULESET = ROOT / "data/rulesets/reference_ruleset.json"


def test_speed_attacker_can_attack_on_summoned_turn() -> None:
    speed = Card(id=1, name="Speed", cost=1, power=1000, ability_tags=("SPEED_ATTACKER",))
    env = Env(deck0=[speed] * 40, deck1=[_vanilla(100 + i) for i in range(40)], config=EnvConfig(seed=1))
    env.reset()
    state = env.state
    assert state is not None
    state.players[0].battle_zone.append(Creature(card=speed, summoned_turn=state.turn_number))
    state.phase = Phase.ATTACK

    assert any(action.type == ActionType.ATTACK_SHIELD for action in env.legal_actions())


def test_non_speed_attacker_cannot_attack_on_summoned_turn() -> None:
    vanilla = _vanilla(1)
    env = Env(deck0=[vanilla] * 40, deck1=[_vanilla(100 + i) for i in range(40)], config=EnvConfig(seed=1))
    env.reset()
    state = env.state
    assert state is not None
    state.players[0].battle_zone.append(Creature(card=vanilla, summoned_turn=state.turn_number))
    state.phase = Phase.ATTACK

    assert all(action.type != ActionType.ATTACK_SHIELD for action in env.legal_actions())


def test_hachiko_nine_copies_remain_legal_and_runtime_convertible() -> None:
    database = load_card_database(REFERENCE_CARDS)
    deck = load_deck(REFERENCE_DECK_02, database)
    ruleset = load_ruleset(REFERENCE_RULESET)
    hachiko = database.to_runtime_card("DM_REF_014", strict=True)

    assert validate_deck_against_ruleset(deck, ruleset)["too_many_copies"] == []
    assert hachiko.name == "特攻の忠剣ハチ公"
    assert "SPEED_ATTACKER" in hachiko.ability_tags
    assert "GACHINKO_JUDGE" in hachiko.ability_tags


def test_hachiko_attack_runs_gachinko_and_summons_same_name() -> None:
    hachiko = load_card_database(REFERENCE_CARDS).to_runtime_card("DM_REF_014", strict=True)
    env = _prepared_hachiko_env(hachiko)

    _obs, _reward, _done, info = env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))

    state = env.state
    assert state is not None
    assert info["gachinko_judge"] is True
    assert info["gachinko_won"] is True
    assert info["same_name_summoned"] is True
    assert sum(1 for creature in state.players[0].battle_zone if creature.card.name == "特攻の忠剣ハチ公") == 2
    summoned = state.players[0].battle_zone[-1]
    assert summoned.tapped is False
    assert summoned.summoned_turn == state.turn_number


def test_gachinko_revealed_cards_move_to_deck_bottom_on_loss() -> None:
    hachiko = load_card_database(REFERENCE_CARDS).to_runtime_card("DM_REF_014", strict=True)
    env = _prepared_hachiko_env(hachiko, attacker_judge=_vanilla(900, cost=1), defender_judge=_vanilla(901, cost=5), same_name=False)

    _obs, _reward, _done, info = env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))

    state = env.state
    assert state is not None
    assert info["gachinko_judge"] is True
    assert info["gachinko_won"] is False
    assert state.players[0].deck[0].name == "C900"
    assert state.players[1].deck[0].name == "C901"


def test_gachinko_unknown_cost_safely_skips() -> None:
    hachiko = load_card_database(REFERENCE_CARDS).to_runtime_card("DM_REF_014", strict=True)
    env = _prepared_hachiko_env(hachiko, attacker_judge=_vanilla(902, cost=0), same_name=True)

    _obs, _reward, _done, info = env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))

    assert info["gachinko_judge"] is True
    assert info["gachinko_won"] is False
    assert info["same_name_summoned"] is False


def test_gachinko_no_same_name_safely_continues() -> None:
    hachiko = load_card_database(REFERENCE_CARDS).to_runtime_card("DM_REF_014", strict=True)
    env = _prepared_hachiko_env(hachiko, same_name=False)

    _obs, _reward, _done, info = env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))

    assert info["gachinko_judge"] is True
    assert info["gachinko_won"] is True
    assert info["same_name_summoned"] is False


def test_analyze_hachiko_logs_runs(tmp_path: Path) -> None:
    analyze_hachiko_logs_main(games=1, output_path=tmp_path / "hachiko.jsonl")
    assert (tmp_path / "hachiko.jsonl").exists()


def test_evaluate_hachiko_runs(capsys) -> None:
    evaluate_hachiko_main(games=1)
    output = capsys.readouterr().out
    assert "gachinko_judges:" in output
    assert "same_name_summons:" in output


def test_diagnose_reference_deck_02_runtime_convertible_count_increased(capsys) -> None:
    database = load_card_database(REFERENCE_CARDS)
    deck = load_deck(REFERENCE_DECK_02, database)
    report = analyze_deck_compatibility(deck, database, ruleset=load_ruleset(REFERENCE_RULESET))
    assert report["runtime_convertible_count"] >= 9

    diagnose_reference_deck_02_main()
    output = capsys.readouterr().out
    assert "runtime_convertible_count: 21" in output


def _prepared_hachiko_env(
    hachiko: Card,
    attacker_judge: Card | None = None,
    defender_judge: Card | None = None,
    same_name: bool = True,
) -> Env:
    deck0 = [_vanilla(1000 + i) for i in range(40)]
    deck1 = [_vanilla(2000 + i) for i in range(40)]
    env = Env(deck0=deck0, deck1=deck1, config=EnvConfig(seed=1))
    env.reset()
    state = env.state
    assert state is not None
    state.current_player = 0
    state.phase = Phase.ATTACK
    state.players[0].battle_zone = [Creature(card=hachiko, summoned_turn=state.turn_number)]
    state.players[1].battle_zone = []
    state.players[1].shields = [_vanilla(3000)]
    state.players[0].deck = [_vanilla(1100 + i) for i in range(10)]
    if same_name:
        state.players[0].deck.append(hachiko)
    state.players[0].deck.append(attacker_judge or _vanilla(910, cost=6))
    state.players[1].deck = [_vanilla(2100 + i) for i in range(10)]
    state.players[1].deck.append(defender_judge or _vanilla(911, cost=1))
    return env


def _vanilla(card_id: int, cost: int = 1) -> Card:
    return Card(id=card_id, name=f"C{card_id}", cost=cost, power=1000, civilizations=("FIRE",))
