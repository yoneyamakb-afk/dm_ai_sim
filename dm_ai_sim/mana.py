from __future__ import annotations

from collections import Counter
from itertools import permutations

from dm_ai_sim.card import Card, VALID_CIVILIZATIONS, is_multicolor
from dm_ai_sim.state import ManaCard, PlayerState


NON_COLORLESS = tuple(civ for civ in VALID_CIVILIZATIONS if civ != "COLORLESS")


def enters_mana_tapped(card: Card) -> bool:
    return is_multicolor(card)


def required_civilizations(card: Card) -> tuple[str, ...]:
    return tuple(civ for civ in (card.civilizations or ("COLORLESS",)) if civ != "COLORLESS")


def mana_civilizations(mana_card: ManaCard) -> tuple[str, ...]:
    return mana_card.card.civilizations or ("COLORLESS",)


def civilization_counts(mana: list[ManaCard], untapped_only: bool = False) -> dict[str, int]:
    counts = {civilization: 0 for civilization in VALID_CIVILIZATIONS}
    for mana_card in mana:
        if untapped_only and mana_card.tapped:
            continue
        for civilization in mana_civilizations(mana_card):
            counts[civilization] += 1
    return counts


def multicolor_mana_count(mana: list[ManaCard]) -> int:
    return sum(1 for mana_card in mana if is_multicolor(mana_card.card))


def untapped_mana_count(player: PlayerState) -> int:
    return sum(1 for mana_card in player.mana if not mana_card.tapped)


def mana_payment_plan(player: PlayerState, card: Card) -> list[int] | None:
    untapped = [index for index, mana_card in enumerate(player.mana) if not mana_card.tapped]
    if len(untapped) < card.cost:
        return None
    required = required_civilizations(card)
    if card.cost < len(required):
        return None
    if not required:
        return _fill_remaining(player, [], card.cost)

    for ordered_required in dict.fromkeys(permutations(required)):
        selected: list[int] = []
        if _assign_required_civilizations(player, list(ordered_required), selected):
            plan = _fill_remaining(player, selected, card.cost)
            if plan is not None:
                return plan
    return None


def can_pay_for_card(player: PlayerState, card: Card) -> bool:
    return mana_payment_plan(player, card) is not None


def tap_mana_for_card(player: PlayerState, card: Card) -> None:
    plan = mana_payment_plan(player, card)
    if plan is None:
        raise RuntimeError(f"Cannot pay for card: {card.name}")
    for index in plan:
        player.mana[index].tapped = True


def playable_hand_counts(player: PlayerState) -> dict[str, int]:
    playable = 0
    civilization_shortfall = 0
    cost_shortfall = 0
    untapped = untapped_mana_count(player)
    for card in player.hand:
        if can_pay_for_card(player, card):
            playable += 1
            continue
        if untapped < card.cost:
            cost_shortfall += 1
        else:
            civilization_shortfall += 1
    return {
        "playable": playable,
        "civilization_shortfall": civilization_shortfall,
        "cost_shortfall": cost_shortfall,
    }


def _assign_required_civilizations(player: PlayerState, required: list[str], selected: list[int]) -> bool:
    if not required:
        return True
    civilization = required[0]
    candidates = _candidate_indices_for_civilization(player, civilization, selected)
    for index in candidates:
        selected.append(index)
        if _assign_required_civilizations(player, required[1:], selected):
            return True
        selected.pop()
    return False


def _candidate_indices_for_civilization(player: PlayerState, civilization: str, selected: list[int]) -> list[int]:
    candidates = [
        index
        for index, mana_card in enumerate(player.mana)
        if not mana_card.tapped
        and index not in selected
        and civilization in mana_civilizations(mana_card)
    ]
    return sorted(candidates, key=lambda index: (is_multicolor(player.mana[index].card), index))


def _fill_remaining(player: PlayerState, selected: list[int], cost: int) -> list[int] | None:
    if len(selected) > cost:
        return None
    remaining = [
        index
        for index, mana_card in enumerate(player.mana)
        if not mana_card.tapped and index not in selected
    ]
    remaining = sorted(remaining, key=lambda index: (is_multicolor(player.mana[index].card), index))
    needed = cost - len(selected)
    if len(remaining) < needed:
        return None
    return selected + remaining[:needed]


def hand_civilization_counts(cards: list[Card]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for card in cards:
        for civilization in required_civilizations(card) or ("COLORLESS",):
            counts[civilization] += 1
    return counts

