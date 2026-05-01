from __future__ import annotations

from collections import Counter
from itertools import permutations

from dm_ai_sim.card import Card, VALID_CIVILIZATIONS, is_multicolor
from dm_ai_sim.state import CostReductionEffect, ManaCard, PlayerState


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


def active_creature_cost_reductions(player: PlayerState) -> list[CostReductionEffect]:
    return [
        effect
        for effect in player.pending_cost_reductions
        if not effect.used and effect.applies_to == "CREATURE" and effect.amount > 0
    ]


def pending_creature_cost_reduction_amount(player: PlayerState) -> int:
    return sum(effect.amount for effect in active_creature_cost_reductions(player))


def effective_summon_cost(player: PlayerState, card: Card) -> int:
    return max(0, card.cost - pending_creature_cost_reduction_amount(player))


def payment_mana_count(card: Card, effective_cost: int | None = None) -> int:
    cost = card.cost if effective_cost is None else max(0, effective_cost)
    return max(cost, len(required_civilizations(card)))


def mana_payment_plan(player: PlayerState, card: Card, effective_cost: int | None = None) -> list[int] | None:
    untapped = [index for index, mana_card in enumerate(player.mana) if not mana_card.tapped]
    mana_count = payment_mana_count(card, effective_cost)
    if len(untapped) < mana_count:
        return None
    required = required_civilizations(card)
    if mana_count < len(required):
        return None
    if not required:
        return _fill_remaining(player, [], mana_count)

    for ordered_required in dict.fromkeys(permutations(required)):
        selected: list[int] = []
        if _assign_required_civilizations(player, list(ordered_required), selected):
            plan = _fill_remaining(player, selected, mana_count)
            if plan is not None:
                return plan
    return None


def can_pay_for_card(player: PlayerState, card: Card, effective_cost: int | None = None) -> bool:
    return mana_payment_plan(player, card, effective_cost=effective_cost) is not None


def can_pay_for_summon(player: PlayerState, card: Card) -> bool:
    return mana_payment_plan(player, card, effective_cost=effective_summon_cost(player, card)) is not None


def tap_mana_for_card(player: PlayerState, card: Card, effective_cost: int | None = None) -> list[int]:
    plan = mana_payment_plan(player, card, effective_cost=effective_cost)
    if plan is None:
        raise RuntimeError(f"Cannot pay for card: {card.name}")
    for index in plan:
        player.mana[index].tapped = True
    return plan


def tap_mana_for_summon(player: PlayerState, card: Card) -> list[int]:
    return tap_mana_for_card(player, card, effective_cost=effective_summon_cost(player, card))


def playable_hand_counts(player: PlayerState) -> dict[str, int]:
    playable = 0
    civilization_shortfall = 0
    cost_shortfall = 0
    untapped = untapped_mana_count(player)
    for card in player.hand:
        payment_options = _playable_payment_options(player, card)
        if any(can_pay_for_card(player, option_card, effective_cost=effective_cost) for option_card, effective_cost in payment_options):
            playable += 1
            continue
        cheapest_payment = min(
            (payment_mana_count(option_card, effective_cost) for option_card, effective_cost in payment_options),
            default=card.cost,
        )
        if untapped < cheapest_payment:
            cost_shortfall += 1
        else:
            civilization_shortfall += 1
    return {
        "playable": playable,
        "civilization_shortfall": civilization_shortfall,
        "cost_shortfall": cost_shortfall,
    }


def _playable_payment_options(player: PlayerState, card: Card) -> list[tuple[Card, int | None]]:
    if card.is_twinpact:
        options: list[tuple[Card, int | None]] = []
        if card.top_side is not None and card.top_side.card_type == "CREATURE":
            top_card = card.side_as_card("top")
            options.append((top_card, effective_summon_cost(player, top_card)))
        if card.bottom_side is not None and card.bottom_side.card_type == "SPELL":
            options.append((card.side_as_card("bottom"), None))
        return options or [(card, None)]
    if card.card_type == "CREATURE":
        return [(card, effective_summon_cost(player, card))]
    return [(card, None)]


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
