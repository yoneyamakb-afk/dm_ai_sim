from __future__ import annotations

from collections import Counter
from pathlib import Path

from dm_ai_sim.card_database import load_card_database
from dm_ai_sim.deck_compatibility import analyze_deck_compatibility
from dm_ai_sim.deck_loader import load_deck


DEFAULT_CARD_DB = Path("data/cards/sample_cards.json")
DEFAULT_DECK = Path("data/decks/sample_deck.json")


def main(card_db_path: Path = DEFAULT_CARD_DB, deck_path: Path = DEFAULT_DECK) -> None:
    database = load_card_database(card_db_path)
    cards = list(database.cards.values())
    ability_tags: Counter[str] = Counter(tag for card in cards for tag in card.ability_tags)
    unsupported_tags: Counter[str] = Counter(tag for card in cards for tag in card.unsupported_tags)
    deck = load_deck(deck_path, database, strict=False)
    compatibility = analyze_deck_compatibility(deck, database)

    print(f"cards: {len(cards)}")
    print(f"supported: {len(database.list_supported())}")
    print(f"unsupported: {len(database.list_unsupported())}")
    print("ability_tags:")
    for tag, count in sorted(ability_tags.items()):
        print(f"  {tag}: {count}")
    print("unsupported_tags:")
    for tag, count in sorted(unsupported_tags.items()):
        print(f"  {tag}: {count}")
    print("deck_compatibility:")
    for key in (
        "deck_name",
        "total_cards",
        "unique_cards",
        "fully_supported_count",
        "partially_supported_count",
        "unsupported_count",
        "reliability",
    ):
        print(f"  {key}: {compatibility[key]}")
    print("  unsupported_tags_summary:")
    for tag, count in compatibility["unsupported_tags_summary"].items():
        print(f"    {tag}: {count}")


if __name__ == "__main__":
    main()

