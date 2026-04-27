import json
from pathlib import Path

import pytest

from dm_ai_sim.card import Card
from dm_ai_sim.card_database import load_card_database
from dm_ai_sim.deck_compatibility import analyze_deck_compatibility
from dm_ai_sim.deck_loader import DeckList, DeckEntry, deck_to_runtime_cards, load_deck
from dm_ai_sim.inspect_card_database import main as inspect_card_database_main
from dm_ai_sim.ruleset import Ruleset, load_ruleset, validate_deck_against_ruleset


ROOT = Path(__file__).resolve().parents[1]
CARDS = ROOT / "data/cards/sample_cards.json"
DECK = ROOT / "data/decks/sample_deck.json"
RULESET = ROOT / "data/rulesets/sample_ruleset.json"


def test_sample_cards_load() -> None:
    database = load_card_database(CARDS)

    assert len(database.cards) == 10
    assert database.get("DM_SAMPLE_001").name == "Sample Fire Creature"


def test_find_by_name() -> None:
    database = load_card_database(CARDS)

    results = database.find_by_name("water")

    assert any(card.card_id == "DM_SAMPLE_004" for card in results)


def test_to_runtime_card_returns_card_and_strict_rejects_unsupported() -> None:
    database = load_card_database(CARDS)

    runtime = database.to_runtime_card("DM_SAMPLE_002")
    assert isinstance(runtime, Card)
    with pytest.warns(RuntimeWarning):
        relaxed = database.to_runtime_card("DM_SAMPLE_001", strict=False)
    assert relaxed.name == "Sample Fire Creature"
    with pytest.raises(ValueError):
        database.to_runtime_card("DM_SAMPLE_001", strict=True)


def test_sample_deck_loads_and_expands_runtime_cards() -> None:
    database = load_card_database(CARDS)
    deck = load_deck(DECK, database)
    runtime_cards = deck_to_runtime_cards(deck, database, strict=False, allow_placeholder=True)

    assert deck.total_cards == 40
    assert len(runtime_cards) == 40


def test_deck_40_card_check(tmp_path: Path) -> None:
    database = load_card_database(CARDS)
    bad_deck = tmp_path / "bad_deck.json"
    bad_deck.write_text(
        json.dumps({"name": "Bad", "format": "sample", "cards": [{"card_id": "DM_SAMPLE_002", "count": 39}]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="40"):
        load_deck(bad_deck, database)


def test_deck_compatibility_report() -> None:
    database = load_card_database(CARDS)
    deck = load_deck(DECK, database)

    report = analyze_deck_compatibility(deck, database)

    assert report["deck_name"] == "Sample Deck"
    assert report["total_cards"] == 40
    assert report["unsupported_count"] > 0
    assert "SPEED_ATTACKER" in report["unsupported_tags_summary"]
    assert report["reliability"] in {"High", "Medium", "Low"}


def test_ruleset_loads_and_detects_banned_card() -> None:
    database = load_card_database(CARDS)
    deck = load_deck(DECK, database)
    ruleset = load_ruleset(RULESET)
    assert ruleset.ruleset_id == "dm_sample_2026_04"

    banned_ruleset = Ruleset(
        ruleset_id="test",
        name="Test",
        comprehensive_rules_version="",
        banlist_effective_date="",
        allowed_card_ids=(),
        banned_card_ids=("DM_SAMPLE_002",),
        restricted_card_ids=("DM_SAMPLE_003",),
    )
    violations = validate_deck_against_ruleset(deck, banned_ruleset)

    assert violations["banned"] == ["DM_SAMPLE_002"]
    assert violations["restricted"] == ["DM_SAMPLE_003"]


def test_inspect_card_database_runs(capsys) -> None:
    inspect_card_database_main(CARDS, DECK)
    output = capsys.readouterr().out

    assert "cards: 10" in output
    assert "deck_compatibility:" in output
    assert "unsupported_tags:" in output
