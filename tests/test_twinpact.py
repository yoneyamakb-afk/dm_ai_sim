from __future__ import annotations

import json
from pathlib import Path

import pytest

from dm_ai_sim.action_encoder import encode_action
from dm_ai_sim.actions import Action, ActionType
from dm_ai_sim.analyze_twinpact_logs import main as analyze_twinpact_logs_main
from dm_ai_sim.card import Card
from dm_ai_sim.card_database import load_card_database
from dm_ai_sim.deck_compatibility import analyze_deck_compatibility
from dm_ai_sim.deck_loader import load_deck
from dm_ai_sim.env import Env, EnvConfig
from dm_ai_sim.evaluate_twinpact import main as evaluate_twinpact_main
from dm_ai_sim.ruleset import load_ruleset
from dm_ai_sim.state import Creature, ManaCard, Phase


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_CARDS = ROOT / "data/cards/reference_cards.json"
REFERENCE_DECK_02 = ROOT / "data/decks/reference_deck_02.json"
REFERENCE_RULESET = ROOT / "data/rulesets/reference_ruleset.json"


def test_twinpact_carddata_and_runtime_conversion() -> None:
    database = load_card_database(REFERENCE_CARDS)
    card = database.get("DM_REF_017")
    runtime = database.to_runtime_card("DM_REF_017", strict=True)

    assert card.is_twinpact is True
    assert runtime.is_twinpact is True
    assert runtime.top_side is not None
    assert runtime.bottom_side is not None


def test_incomplete_twinpact_runtime_conversion_blocks(tmp_path: Path) -> None:
    path = tmp_path / "cards.json"
    path.write_text(
        json.dumps(
            [
                {
                    "card_id": "BAD_TWIN",
                    "name": "Bad Twin",
                    "cost": None,
                    "civilizations": ["UNKNOWN"],
                    "card_type": "UNKNOWN",
                    "power": None,
                    "ability_tags": ["TWINPACT"],
                    "implemented_tags": ["TWINPACT"],
                    "unsupported_tags": [],
                    "is_twinpact": True,
                    "top_side": {"name": "Top", "cost": None, "civilizations": ["UNKNOWN"], "card_type": "CREATURE", "power": None},
                    "bottom_side": {"name": "Bottom", "cost": 2, "civilizations": ["NATURE"], "card_type": "SPELL", "power": None},
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    database = load_card_database(path)

    with pytest.raises(ValueError, match="incomplete twinpact"):
        database.to_runtime_card("BAD_TWIN", strict=True)


def test_top_side_creature_summon_moves_one_card_to_battle_zone() -> None:
    twin = load_card_database(REFERENCE_CARDS).to_runtime_card("DM_REF_017", strict=True)
    env = _env_with_hand(twin)
    state = env.state
    assert state is not None
    state.players[0].mana = [ManaCard(Card(id=9000 + i, name=f"M{i}", cost=1, power=1000, civilizations=("NATURE",))) for i in range(5)]

    action = Action(ActionType.SUMMON, card_index=0, side="top")
    _obs, _reward, _done, info = env.step(action)

    assert info["side_used"] == "top"
    assert len(state.players[0].hand) == 0
    assert len(state.players[0].battle_zone) == 1
    assert state.players[0].battle_zone[0].card.name == "配球の超人"
    assert state.players[0].battle_zone[0].original_card.name == "配球の超人 / 記録的剛球"


def test_bottom_side_spell_cast_moves_one_card_to_graveyard() -> None:
    twin = load_card_database(REFERENCE_CARDS).to_runtime_card("DM_REF_017", strict=True)
    env = _env_with_hand(twin)
    state = env.state
    assert state is not None
    state.players[0].mana = [ManaCard(Card(id=9100 + i, name=f"M{i}", cost=1, power=1000, civilizations=("NATURE",))) for i in range(2)]

    action = Action(ActionType.CAST_SPELL, hand_index=0, side="bottom")
    _obs, _reward, _done, info = env.step(action)

    assert info["side_used"] == "bottom"
    assert info["spell_cast"] is True
    assert len(state.players[0].hand) == 0
    assert state.players[0].graveyard[-1].name == "配球の超人 / 記録的剛球"


def test_twinpact_mana_charge_is_one_card() -> None:
    twin = load_card_database(REFERENCE_CARDS).to_runtime_card("DM_REF_017", strict=True)
    env = _env_with_hand(twin)
    state = env.state
    assert state is not None

    env.step(Action(ActionType.CHARGE_MANA, card_index=0))

    assert len(state.players[0].hand) == 0
    assert len(state.players[0].mana) == 1
    assert state.players[0].mana[0].card.name == "配球の超人 / 記録的剛球"


def test_twinpact_shield_trigger_uses_bottom_effect() -> None:
    twin = load_card_database(REFERENCE_CARDS).to_runtime_card("DM_REF_018", strict=True)
    env = _env_with_hand(Card(id=1, name="Attacker", cost=1, power=1000, civilizations=("FIRE",)))
    state = env.state
    assert state is not None
    state.phase = Phase.ATTACK
    state.players[0].battle_zone = [Creature(card=Card(id=2, name="A", cost=1, power=1000, civilizations=("FIRE",)), summoned_turn=0)]
    state.players[1].shields = [twin]

    _obs, _reward, _done, info = env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))

    assert info["trigger_activated"] is True
    assert info["trigger_effect"] == "DESTROY_ATTACKER"
    assert info["attacker_destroyed_by_trigger"] is True
    assert state.players[1].graveyard[-1].name == "D2V3 終断のレッドトロン / フォビドゥン・ハンド"


def test_action_mask_reflects_twinpact_summon_and_cast() -> None:
    twin = load_card_database(REFERENCE_CARDS).to_runtime_card("DM_REF_017", strict=True)
    env = _env_with_hand(twin, include_action_mask=True)
    state = env.state
    assert state is not None
    state.players[0].mana = [ManaCard(Card(id=9200 + i, name=f"M{i}", cost=1, power=1000, civilizations=("NATURE",))) for i in range(5)]
    obs = env.get_observation(include_action_mask=True)
    actions = env.legal_actions()

    summon = Action(ActionType.SUMMON, card_index=0, side="top")
    cast = Action(ActionType.CAST_SPELL, hand_index=0, side="bottom")
    assert summon in actions
    assert cast in actions
    assert obs["action_mask"][encode_action(summon)] == 1
    assert obs["action_mask"][encode_action(cast)] == 1


def test_twinpact_zone_count_consistency() -> None:
    twin = load_card_database(REFERENCE_CARDS).to_runtime_card("DM_REF_017", strict=True)
    env = _env_with_hand(twin)
    before = _zone_count(env)
    env.step(Action(ActionType.CHARGE_MANA, card_index=0))
    assert _zone_count(env) == before


def test_twinpact_clis_run(tmp_path: Path, capsys) -> None:
    evaluate_twinpact_main(games=1)
    assert "top_side_summons:" in capsys.readouterr().out

    analyze_twinpact_logs_main(games=1, output_path=tmp_path / "twinpact.jsonl")
    output = capsys.readouterr().out
    assert "bottom_side_cast:" in output
    assert (tmp_path / "twinpact.jsonl").exists()


def test_reference_deck_02_runtime_convertible_count_increased_by_twinpact() -> None:
    database = load_card_database(REFERENCE_CARDS)
    deck = load_deck(REFERENCE_DECK_02, database)
    report = analyze_deck_compatibility(deck, database, ruleset=load_ruleset(REFERENCE_RULESET))

    assert report["runtime_convertible_count"] >= 17
    assert report["twinpact_blocked_count"] == 0


def _env_with_hand(card: Card, include_action_mask: bool = False) -> Env:
    deck = [Card(id=100 + i, name=f"C{i}", cost=1, power=1000, civilizations=("FIRE",)) for i in range(40)]
    env = Env(deck0=deck, deck1=list(deck), config=EnvConfig(seed=1, include_action_mask=include_action_mask))
    env.reset()
    state = env.state
    assert state is not None
    state.current_player = 0
    state.phase = Phase.MAIN
    state.players[0].hand = [card]
    state.players[0].mana = []
    return env


def _zone_count(env: Env) -> int:
    assert env.state is not None
    return sum(
        len(player.deck) + len(player.hand) + len(player.mana) + len(player.battle_zone) + len(player.graveyard) + len(player.shields)
        for player in env.state.players
    )
