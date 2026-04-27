from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from dm_ai_sim.card import Card
from dm_ai_sim.card_database import CardData, CardDatabase, unknown_data_fields


@dataclass(frozen=True, slots=True)
class DeckEntry:
    card_id: str
    count: int


@dataclass(frozen=True, slots=True)
class DeckList:
    name: str
    format: str
    cards: tuple[DeckEntry, ...]

    @property
    def total_cards(self) -> int:
        return sum(entry.count for entry in self.cards)


def load_deck(path: str | Path, card_database: CardDatabase, strict: bool = False) -> DeckList:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    deck = DeckList(
        name=str(raw["name"]),
        format=str(raw.get("format", "")),
        cards=tuple(DeckEntry(str(item["card_id"]), int(item["count"])) for item in raw.get("cards", ())),
    )
    _validate_decklist(deck, card_database, strict=strict)
    return deck


def deck_to_runtime_cards(
    decklist: DeckList,
    card_database: CardDatabase,
    strict: bool = False,
    allow_placeholder: bool = False,
) -> list[Card]:
    _validate_decklist(decklist, card_database, strict=strict)
    cards: list[Card] = []
    for entry in decklist.cards:
        card_data = card_database.get(entry.card_id)
        reasons = runtime_blocked_reasons(card_data)
        if reasons and not allow_placeholder:
            raise ValueError(f"{entry.card_id} cannot be converted to runtime Card: {', '.join(reasons)}")
        runtime = card_database.to_runtime_card(entry.card_id, strict=strict)
        cards.extend([runtime] * entry.count)
    return cards


def runtime_blocked_reasons(card: CardData) -> list[str]:
    fields = set(unknown_data_fields(card))
    reasons: list[str] = []
    if "cost" in fields:
        reasons.append("missing_cost")
    if "civilizations" in fields:
        reasons.append("missing_civilizations")
    if "card_type" in fields:
        reasons.append("missing_card_type")
    if "power" in fields:
        reasons.append("unknown_power")
    if card.unsupported_tags:
        reasons.append("unsupported_tags")
    return reasons


def _validate_decklist(decklist: DeckList, card_database: CardDatabase, strict: bool) -> None:
    if decklist.total_cards != 40:
        raise ValueError(f"Deck must contain exactly 40 cards, got {decklist.total_cards}.")
    for entry in decklist.cards:
        if entry.count <= 0:
            raise ValueError(f"Card count must be positive for {entry.card_id}.")
        card = card_database.get(entry.card_id)
        if strict and card.unsupported_tags:
            raise ValueError(f"{entry.card_id} has unsupported tags: {', '.join(card.unsupported_tags)}")
