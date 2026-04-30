from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from dm_ai_sim.card import Card
from dm_ai_sim.card_database import load_card_database


CARD_DB_PATH = Path("data/cards/reference_cards.json")


def gstrike_runtime_test_deck(base_id: int = 170_000) -> list[Card]:
    database = load_card_database(CARD_DB_PATH)
    paired_cards = [
        (database.to_runtime_card("DM_REF_020", strict=True), 12),
        (database.to_runtime_card("DM_REF_014", strict=True), 16),
        (database.to_runtime_card("DM_REF_017", strict=True), 12),
    ]
    cards: list[Card] = []
    offset = 0
    for card, count in paired_cards:
        for index in range(count):
            cards.append(replace(card, id=base_id + offset + index))
        offset += count
    return cards
