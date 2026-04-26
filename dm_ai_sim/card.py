from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Card:
    id: int
    name: str
    cost: int
    power: int
    civilization: str = "colorless"
    blocker: bool = False


def make_vanilla_deck(size: int = 40, base_id: int = 0) -> list[Card]:
    cards: list[Card] = []
    for i in range(size):
        cost = 1 + (i % 5)
        is_blocker = i % 4 == 0
        cards.append(
            Card(
                id=base_id + i,
                name=f"{'Blocker' if is_blocker else 'Vanilla'} Creature {base_id + i}",
                cost=cost,
                power=1000 + cost * 1000 if not is_blocker else 1000 + cost * 800,
                blocker=is_blocker,
            )
        )
    return cards
