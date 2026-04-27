from __future__ import annotations

from collections import Counter

from dm_ai_sim.card import make_vanilla_deck, is_multicolor


def main() -> None:
    deck = make_vanilla_deck()
    type_counts = Counter(card.card_type for card in deck)
    cost_counts = Counter(card.cost for card in deck)
    civilization_counts: Counter[str] = Counter()
    for card in deck:
        for civilization in card.civilizations or (card.civilization,):
            civilization_counts[civilization] += 1

    print(f"deck_size: {len(deck)}")
    print(f"creatures: {type_counts['CREATURE']}")
    print(f"spells: {type_counts['SPELL']}")
    print(f"shield_triggers: {sum(1 for card in deck if card.shield_trigger)}")
    print(f"multicolor_cards: {sum(1 for card in deck if is_multicolor(card))}")
    print("civilizations:")
    for civilization, count in sorted(civilization_counts.items()):
        print(f"  {civilization}: {count}")
    print("costs:")
    for cost, count in sorted(cost_counts.items()):
        print(f"  {cost}: {count}")
    print("turn2_candidates:")
    for card in deck:
        if card.cost <= 2:
            print(f"  {card.name}: cost={card.cost} type={card.card_type} civilizations={','.join(card.civilizations or ())}")
    print("turn3_candidates:")
    for card in deck:
        if card.cost <= 3:
            print(f"  {card.name}: cost={card.cost} type={card.card_type} civilizations={','.join(card.civilizations or ())}")


if __name__ == "__main__":
    main()

