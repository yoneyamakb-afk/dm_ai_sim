from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Card:
    id: int
    name: str
    cost: int
    power: int
    civilization: str = "colorless"


def make_vanilla_deck(size: int = 40, base_id: int = 0) -> list[Card]:
    cards: list[Card] = []
    for i in range(size):
        cost = 1 + (i % 5)
        cards.append(
            Card(
                id=base_id + i,
                name=f"Vanilla Creature {base_id + i}",
                cost=cost,
                power=1000 + cost * 1000,
            )
        )
    return cards
