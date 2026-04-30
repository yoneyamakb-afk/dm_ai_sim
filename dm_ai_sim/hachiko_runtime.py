from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from dm_ai_sim.card import Card
from dm_ai_sim.card_database import load_card_database


HACHIKO_ID = "DM_REF_014"
CARD_DB_PATH = Path("data/cards/reference_cards.json")
DECK_PATH = Path("data/decks/hachiko_runtime_test_deck.json")


def hachiko_runtime_card() -> Card:
    return load_card_database(CARD_DB_PATH).to_runtime_card(HACHIKO_ID, strict=True)


def hachiko_runtime_test_deck(base_id: int = 50_000) -> list[Card]:
    hachiko = hachiko_runtime_card()
    cards: list[Card] = []
    for index in range(20):
        cards.append(replace(hachiko, id=base_id + index))
    for index in range(20):
        cards.append(
            Card(
                id=base_id + 20 + index,
                name=f"Runtime Fire Vanilla {index}",
                cost=1 + (index % 3),
                power=1000 + (index % 3) * 1000,
                civilizations=("FIRE",),
                card_type="CREATURE",
            )
        )
    return cards
