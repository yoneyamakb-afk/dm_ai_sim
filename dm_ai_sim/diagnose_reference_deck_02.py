from __future__ import annotations

import sys
from pathlib import Path

from dm_ai_sim.card_database import load_card_database
from dm_ai_sim.deck_compatibility import analyze_deck_compatibility
from dm_ai_sim.deck_loader import deck_to_runtime_cards, load_deck
from dm_ai_sim.ruleset import load_ruleset, validate_deck_against_ruleset


CARD_DB_PATH = Path("data/cards/reference_cards.json")
DECK_PATH = Path("data/decks/reference_deck_02.json")
RULESET_PATH = Path("data/rulesets/reference_ruleset.json")
HACHIKO_ID = "DM_REF_014"
PRIORITY_TAGS = (
    "SAME_NAME_MORE_THAN_4_ALLOWED",
    "TWINPACT",
    "SPEED_ATTACKER",
    "REVOLUTION_CHANGE",
    "INVASION",
    "G_STRIKE",
    "SHIELD_TRIGGER",
    "COST_REDUCTION",
    "DESTROY",
    "MANA_BOOST",
    "GAIN_SHIELD",
    "SEARCH",
    "LOCK",
    "META_EFFECT",
)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    database = load_card_database(CARD_DB_PATH)
    deck = load_deck(DECK_PATH, database, strict=False)
    ruleset = load_ruleset(RULESET_PATH)
    report = analyze_deck_compatibility(deck, database, ruleset=ruleset)
    violations = validate_deck_against_ruleset(deck, ruleset)

    print(f"deck_name: {deck.name}")
    print(f"total_cards: {deck.total_cards}")
    hachiko = next(entry for entry in deck.cards if entry.card_id == HACHIKO_ID)
    print(f"hachiko_count: {hachiko.count}")
    print(f"hachiko_same_name_exception: {HACHIKO_ID in ruleset.same_name_exception_card_ids}")
    print(f"construction_legal: {report['construction_legal']}")
    print(f"ruleset_too_many_copies: {violations['too_many_copies']}")
    print(f"runtime_convertible_count: {report['runtime_convertible_count']}")
    print(f"runtime_blocked_count: {report['runtime_blocked_count']}")
    print(f"unknown_data_count: {report['unknown_data_count']}")
    print(f"official_data_complete_count: {report['official_data_complete_count']}")
    print(f"missing_official_data_count: {report['missing_official_data_count']}")
    print(f"cost_known_count: {deck.total_cards - report['missing_fields_summary'].get('cost', 0)}")
    print(f"civilizations_known_count: {deck.total_cards - report['missing_fields_summary'].get('civilizations', 0)}")
    print(f"card_type_known_count: {deck.total_cards - report['missing_fields_summary'].get('card_type', 0)}")
    power_needed_count, power_known_count = _power_completion_counts(deck, database)
    print(f"power_known_among_power_needed: {power_known_count}/{power_needed_count}")
    print(f"twinpact_count: {report['twinpact_count']}")
    print(f"twinpact_blocked_count: {report['twinpact_blocked_count']}")
    print("missing_fields_summary:")
    for field, count in report["missing_fields_summary"].items():
        print(f"  {field}: {count}")
    print("unsupported_tag_summary:")
    for tag, count in report["unsupported_tags_summary"].items():
        print(f"  {tag}: {count}")
    print("unsupported_counts_by_tag:")
    for tag, count in report["unsupported_tags_summary"].items():
        print(f"  {tag}: {count}")
    print("high_priority_missing_tags:")
    for tag in report["high_priority_missing_tags"]:
        print(f"  {tag}")
    print("next_ability_tag_priority:")
    for tag in _next_priority_tags(report["unsupported_tags_summary"]):
        print(f"  {tag}: {report['unsupported_tags_summary'][tag]}")
    print("blocked_reasons:")
    for reason, count in report["blocked_reasons"].items():
        print(f"  {reason}: {count}")
    print(f"simulation_readiness: {report['simulation_readiness']}")

    try:
        deck_to_runtime_cards(deck, database, strict=False, allow_placeholder=False)
        print("runtime_conversion: ok")
    except ValueError as exc:
        print("runtime_conversion: blocked")
        print(f"runtime_conversion_reason: {exc}")

    if report["simulation_readiness"] == "Ready":
        print("can_enter_simulation: true")
    else:
        print("can_enter_simulation: false")
        print("cannot_enter_reason: unknown official data and unsupported high-priority ability tags remain")
        print("provisional_risk: placeholder conversion would hide missing card text, costs, civilizations, and twinpact/invasion/revolution mechanics")


def _power_completion_counts(deck, database) -> tuple[int, int]:
    needed = 0
    known = 0
    for entry in deck.cards:
        card = database.get(entry.card_id)
        sides = (card.top_side, card.bottom_side) if card.is_twinpact else ()
        if sides:
            side_needs_power = False
            side_known_power = True
            for side in sides:
                if side is not None and side.card_type == "CREATURE":
                    side_needs_power = True
                    if side.power is None:
                        side_known_power = False
            if side_needs_power:
                needed += entry.count
                if side_known_power:
                    known += entry.count
        elif card.card_type == "CREATURE":
            needed += entry.count
            if card.power is not None:
                known += entry.count
    return needed, known


def _next_priority_tags(unsupported_tags_summary: dict[str, int]) -> list[str]:
    priority = [tag for tag in PRIORITY_TAGS if tag in unsupported_tags_summary]
    remaining = sorted(tag for tag in unsupported_tags_summary if tag not in PRIORITY_TAGS)
    return priority + remaining


if __name__ == "__main__":
    main()
