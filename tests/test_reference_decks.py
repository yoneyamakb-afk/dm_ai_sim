from pathlib import Path

from dm_ai_sim.card_database import load_card_database
from dm_ai_sim.deck_compatibility import analyze_deck_compatibility
from dm_ai_sim.deck_loader import DeckEntry, DeckList, deck_to_runtime_cards, load_deck
from dm_ai_sim.inspect_reference_decks import main as inspect_reference_decks_main
from dm_ai_sim.diagnose_reference_deck_02 import main as diagnose_reference_deck_02_main
from dm_ai_sim.ruleset import load_ruleset, validate_deck_against_ruleset
import pytest


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_CARDS = ROOT / "data/cards/reference_cards.json"
REFERENCE_DECK_01 = ROOT / "data/decks/reference_deck_01.json"
REFERENCE_DECK_02 = ROOT / "data/decks/reference_deck_02.json"
REFERENCE_RULESET = ROOT / "data/rulesets/reference_ruleset.json"
REFERENCE_REPORT = ROOT / "REFERENCE_DECK_COMPATIBILITY.md"
REFERENCE_DECK_02_AUDIT = ROOT / "REFERENCE_DECK_02_DATA_AUDIT.md"


def test_reference_cards_load() -> None:
    database = load_card_database(REFERENCE_CARDS)

    assert len(database.cards) == 24
    assert database.get("DM_REF_014").name == "特攻の忠剣ハチ公"
    assert database.get("DM_REF_019").is_twinpact is True
    assert database.get("DM_REF_019").top_side is not None
    assert database.get("DM_REF_019").bottom_side is not None


def test_reference_decks_are_40_cards() -> None:
    database = load_card_database(REFERENCE_CARDS)
    deck1 = load_deck(REFERENCE_DECK_01, database)
    deck2 = load_deck(REFERENCE_DECK_02, database)

    assert deck1.total_cards == 40
    assert deck2.total_cards == 40


def test_over_four_card_and_exception_candidate() -> None:
    database = load_card_database(REFERENCE_CARDS)
    deck = load_deck(REFERENCE_DECK_02, database)
    ruleset = load_ruleset(REFERENCE_RULESET)

    hachiko = next(entry for entry in deck.cards if entry.card_id == "DM_REF_014")
    assert hachiko.count == 9
    assert "SAME_NAME_MORE_THAN_4_ALLOWED" in database.get("DM_REF_014").ability_tags
    assert "DM_REF_014" in ruleset.same_name_exception_card_ids
    assert validate_deck_against_ruleset(deck, ruleset)["too_many_copies"] == []


def test_non_exception_over_four_is_violation() -> None:
    ruleset = load_ruleset(REFERENCE_RULESET)
    deck = DeckList(
        name="Bad Over Four",
        format="test",
        cards=(
            DeckEntry("DM_REF_015", 5),
            DeckEntry("DM_REF_014", 35),
        ),
    )

    violations = validate_deck_against_ruleset(deck, ruleset)

    assert violations["too_many_copies"] == ["DM_REF_015"]


def test_deck_compatibility_reports_unknown_data_count() -> None:
    database = load_card_database(REFERENCE_CARDS)
    deck = load_deck(REFERENCE_DECK_01, database)
    ruleset = load_ruleset(REFERENCE_RULESET)
    report = analyze_deck_compatibility(deck, database, ruleset=ruleset)

    assert report["unknown_data_count"] == 40
    assert report["unknown_cards"]
    assert "construction_legal" in report
    assert "simulation_readiness" in report
    assert report["simulation_readiness"] != "Ready"
    assert "ability_tags_summary" in report
    assert report["reliability"] == "Low"


def test_deck_compatibility_reports_missing_fields_summary() -> None:
    database = load_card_database(REFERENCE_CARDS)
    deck = load_deck(REFERENCE_DECK_02, database)
    ruleset = load_ruleset(REFERENCE_RULESET)
    report = analyze_deck_compatibility(deck, database, ruleset=ruleset)

    assert "missing_fields_summary" in report
    assert "official_data_complete_count" in report
    assert "twinpact_count" in report
    assert report["twinpact_count"] == 20
    assert report["twinpact_blocked_count"] == 0


def test_twinpact_with_unsupported_tags_strict_runtime_conversion_is_blocked() -> None:
    database = load_card_database(REFERENCE_CARDS)

    with pytest.raises(ValueError, match="unsupported tags"):
        database.to_runtime_card("DM_REF_019", strict=True)


def test_non_twinpact_with_required_info_can_convert() -> None:
    database = load_card_database(REFERENCE_CARDS)
    runtime = database.to_runtime_card("DM_REF_021", strict=False)

    assert runtime.name == "フェアリー・ギフト"
    assert runtime.cost == 1
    assert runtime.card_type == "SPELL"


def test_allow_placeholder_false_blocks_unknown_reference_cards() -> None:
    database = load_card_database(REFERENCE_CARDS)
    deck = load_deck(REFERENCE_DECK_02, database)

    with pytest.raises(ValueError, match="cannot be converted"):
        deck_to_runtime_cards(deck, database, strict=False, allow_placeholder=False)


def test_inspect_reference_decks_runs(capsys) -> None:
    inspect_reference_decks_main()
    output = capsys.readouterr().out

    assert "deck: Reference Deck 01" in output
    assert "deck: Reference Deck 02" in output
    assert "特攻の忠剣ハチ公" in output
    assert "allowed by SAME_NAME_MORE_THAN_4_ALLOWED" in output
    assert "priority_target: true" in output
    assert "required_before_competitive_evaluation:" in output


def test_diagnose_reference_deck_02_runs(capsys) -> None:
    diagnose_reference_deck_02_main()
    output = capsys.readouterr().out

    assert "deck_name: Reference Deck 02" in output
    assert "hachiko_same_name_exception: True" in output
    assert "simulation_readiness: Blocked" in output
    assert "runtime_conversion: blocked" in output
    assert "official_data_complete_count:" in output
    assert "twinpact_blocked_count:" in output


def test_reference_deck_compatibility_document_exists() -> None:
    assert REFERENCE_REPORT.exists()
    text = REFERENCE_REPORT.read_text(encoding="utf-8")
    assert "Reference Deck 01" in text
    assert "Reference Deck 02" in text


def test_reference_deck_02_data_audit_exists() -> None:
    assert REFERENCE_DECK_02_AUDIT.exists()
    text = REFERENCE_DECK_02_AUDIT.read_text(encoding="utf-8")
    assert "Reference Deck 02" in text
    assert "ツインパクト" in text
