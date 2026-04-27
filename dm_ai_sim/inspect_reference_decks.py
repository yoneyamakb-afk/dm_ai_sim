from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
from typing import Any

from dm_ai_sim.card_database import CardDatabase, load_card_database
from dm_ai_sim.deck_compatibility import analyze_deck_compatibility
from dm_ai_sim.deck_loader import DeckList, load_deck
from dm_ai_sim.ruleset import load_ruleset, validate_deck_against_ruleset


CARD_DB_PATH = Path("data/cards/reference_cards.json")
DECK_PATHS = [Path("data/decks/reference_deck_01.json"), Path("data/decks/reference_deck_02.json")]
RULESET_PATH = Path("data/rulesets/reference_ruleset.json")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    database = load_card_database(CARD_DB_PATH)
    ruleset = load_ruleset(RULESET_PATH)
    needed_tags: Counter[str] = Counter()

    for deck_path in DECK_PATHS:
        deck = load_deck(deck_path, database, strict=False)
        report = analyze_deck_compatibility(deck, database, ruleset=ruleset)
        violations = validate_deck_against_ruleset(deck, ruleset)
        over_limit = _over_limit_entries(deck, ruleset.max_copies_per_card)
        exception_candidates = _same_name_exception_candidates(deck, database)
        needed_tags.update(report["unsupported_tags_summary"])

        print(f"deck: {deck.name}")
        if deck.name == "Reference Deck 02":
            print("priority_target: true")
        print(f"source: {deck_path.name}")
        print("cards:")
        for entry in deck.cards:
            card = database.get(entry.card_id)
            print(f"  {card.name} ({entry.card_id}) x{entry.count}")
        print(f"total_cards: {deck.total_cards}")
        print(f"unique_cards: {len(deck.cards)}")
        print("over_4_cards:")
        for entry in over_limit:
            card = database.get(entry["card_id"])
            allowed = entry["card_id"] in ruleset.same_name_exception_card_ids
            if allowed:
                print(f"  {card.name} ({entry['card_id']}) x{entry['count']} - allowed by SAME_NAME_MORE_THAN_4_ALLOWED")
            else:
                print(f"  {card.name} ({entry['card_id']}) x{entry['count']} - violation")
        print("same_name_exception_candidates:")
        for card_id in exception_candidates:
            card = database.get(card_id)
            print(f"  {card.name} ({card_id})")
        print(f"ruleset_too_many_copies: {violations['too_many_copies']}")
        print(f"construction_legal: {report['construction_legal']}")
        print(f"same_name_exceptions_used: {report['same_name_exceptions_used']}")
        print(f"unsupported_count: {report['unsupported_count']}")
        print(f"unknown_data_count: {report['unknown_data_count']}")
        print(f"runtime_convertible_count: {report['runtime_convertible_count']}")
        print(f"runtime_blocked_count: {report['runtime_blocked_count']}")
        print(f"simulation_readiness: {report['simulation_readiness']}")
        print(f"reliability: {report['reliability']}")
        print("ability_tags_summary:")
        for tag, count in report["ability_tags_summary"].items():
            print(f"  {tag}: {count}")
        print("unsupported_tags_summary:")
        for tag, count in report["unsupported_tags_summary"].items():
            print(f"  {tag}: {count}")
        print("high_priority_missing_tags:")
        for tag in report["high_priority_missing_tags"]:
            print(f"  {tag}")
        print()

    print("required_before_competitive_evaluation:")
    for tag, count in sorted(needed_tags.items()):
        print(f"  {tag}: {count}")


def _over_limit_entries(deck: DeckList, max_copies: int) -> list[dict[str, Any]]:
    return [
        {"card_id": entry.card_id, "count": entry.count}
        for entry in deck.cards
        if entry.count > max_copies
    ]


def _same_name_exception_candidates(deck: DeckList, database: CardDatabase) -> list[str]:
    candidates: list[str] = []
    for entry in deck.cards:
        card = database.get(entry.card_id)
        if "SAME_NAME_MORE_THAN_4_ALLOWED" in card.ability_tags or entry.count > 4:
            candidates.append(entry.card_id)
    return candidates


if __name__ == "__main__":
    main()
