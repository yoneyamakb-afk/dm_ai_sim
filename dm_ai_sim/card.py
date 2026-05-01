from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


CardType = Literal["CREATURE", "SPELL"]
TriggerEffect = Literal["DRAW_1", "DESTROY_ATTACKER", "SUMMON_SELF", "GAIN_SHIELD"]
Civilization = Literal["LIGHT", "WATER", "DARKNESS", "FIRE", "NATURE", "COLORLESS"]
VALID_CIVILIZATIONS = ("LIGHT", "WATER", "DARKNESS", "FIRE", "NATURE", "COLORLESS")


@dataclass(frozen=True, slots=True)
class CardSide:
    name: str
    cost: int | None
    civilizations: tuple[str, ...]
    card_type: str
    power: int | None
    races: tuple[str, ...] = ()
    text: str = ""
    ability_tags: tuple[str, ...] = ()
    spell_effect: str | None = None
    trigger_effect: TriggerEffect | None = None
    shield_trigger: bool = False
    blocker: bool = False

    def __post_init__(self) -> None:
        normalized = tuple(dict.fromkeys(_normalize_civilization(value) for value in self.civilizations))
        object.__setattr__(self, "civilizations", normalized or ("COLORLESS",))
        object.__setattr__(self, "ability_tags", tuple(dict.fromkeys(str(tag) for tag in self.ability_tags)))


@dataclass(frozen=True, slots=True)
class Card:
    id: int
    name: str
    cost: int
    power: int
    civilization: str = "COLORLESS"
    civilizations: tuple[str, ...] | None = None
    blocker: bool = False
    shield_trigger: bool = False
    card_type: CardType = "CREATURE"
    trigger_effect: TriggerEffect | None = None
    spell_effect: str | None = None
    ability_tags: tuple[str, ...] = ()
    breaker_count: int = 1
    is_twinpact: bool = False
    top_side: CardSide | None = None
    bottom_side: CardSide | None = None

    def __post_init__(self) -> None:
        civilizations = self.civilizations
        if civilizations is None:
            civilizations = (self.civilization,)
        normalized = tuple(dict.fromkeys(_normalize_civilization(value) for value in civilizations))
        if not normalized:
            normalized = ("COLORLESS",)
        if "COLORLESS" in normalized and len(normalized) > 1:
            normalized = tuple(value for value in normalized if value != "COLORLESS")
        object.__setattr__(self, "civilizations", normalized)
        object.__setattr__(self, "civilization", normalized[0])
        object.__setattr__(self, "ability_tags", tuple(dict.fromkeys(str(tag) for tag in self.ability_tags)))
        if self.breaker_count < 1:
            object.__setattr__(self, "breaker_count", 1)
        tags = set(self.ability_tags)
        if self.breaker_count == 1 and "TRIPLE_BREAKER" in tags:
            object.__setattr__(self, "breaker_count", 3)
        elif self.breaker_count == 1 and "DOUBLE_BREAKER" in tags:
            object.__setattr__(self, "breaker_count", 2)

    def side_as_card(self, side: str) -> "Card":
        card_side = self.top_side if side == "top" else self.bottom_side if side == "bottom" else None
        if card_side is None:
            raise ValueError(f"{self.name} does not have side: {side}")
        if card_side.cost is None or card_side.power is None and card_side.card_type == "CREATURE":
            raise ValueError(f"{self.name} side {side} has incomplete runtime data")
        return Card(
            id=self.id,
            name=card_side.name,
            cost=card_side.cost,
            power=card_side.power or 0,
            civilizations=card_side.civilizations,
            blocker=card_side.blocker,
            shield_trigger=card_side.shield_trigger,
            card_type=card_side.card_type if card_side.card_type in {"CREATURE", "SPELL"} else "CREATURE",  # type: ignore[arg-type]
            trigger_effect=card_side.trigger_effect,
            spell_effect=card_side.spell_effect,
            ability_tags=card_side.ability_tags,
            breaker_count=3 if "TRIPLE_BREAKER" in card_side.ability_tags else 2 if "DOUBLE_BREAKER" in card_side.ability_tags else 1,
        )


def make_vanilla_deck(size: int = 40, base_id: int = 0) -> list[Card]:
    cards: list[Card] = []
    for i in range(size):
        cost = 1 + (i % 5)
        spell_effect = _spell_effect_for_index(i)
        is_blocker = i % 4 == 0
        trigger_effect = _trigger_effect_for_index(i)
        card_type: CardType = "SPELL" if spell_effect is not None else "CREATURE"
        is_blocker = is_blocker and card_type == "CREATURE"
        power = 0 if card_type == "SPELL" else 1000 + cost * 1000 if not is_blocker else 1000 + cost * 800
        cards.append(
            Card(
                id=base_id + i,
                name=f"{_card_name_prefix(is_blocker, trigger_effect, spell_effect)} {base_id + i}",
                cost=cost,
                power=power,
                blocker=is_blocker,
                shield_trigger=trigger_effect is not None,
                card_type=card_type,
                trigger_effect=trigger_effect,
                spell_effect=spell_effect,
                civilizations=_civilizations_for_index(i),
            )
        )
    return cards


def is_multicolor(card: Card) -> bool:
    return len(card.civilizations or ()) > 1


def _normalize_civilization(value: str) -> str:
    normalized = value.upper()
    if normalized == "DARK":
        normalized = "DARKNESS"
    if normalized not in VALID_CIVILIZATIONS:
        normalized = "COLORLESS"
    return normalized


def _civilizations_for_index(index: int) -> tuple[str, ...]:
    multicolor: dict[int, tuple[str, ...]] = {
        2: ("FIRE", "NATURE"),
        5: ("LIGHT", "WATER"),
        8: ("DARKNESS", "FIRE"),
        11: ("FIRE", "NATURE"),
        14: ("WATER", "NATURE"),
        17: ("LIGHT", "FIRE"),
        20: ("FIRE", "NATURE"),
        23: ("FIRE", "NATURE"),
        26: ("DARKNESS", "NATURE"),
        29: ("DARKNESS", "FIRE"),
        32: ("LIGHT", "NATURE"),
        35: ("LIGHT", "WATER"),
    }
    if index in multicolor:
        return multicolor[index]
    if index in {6, 18, 30, 39}:
        return ("COLORLESS",)
    cycle = ("FIRE", "NATURE", "FIRE", "NATURE", "LIGHT", "WATER", "FIRE", "NATURE")
    return (cycle[index % len(cycle)],)


def _trigger_effect_for_index(index: int) -> TriggerEffect | None:
    effects: dict[int, TriggerEffect] = {
        3: "DRAW_1",
        9: "SUMMON_SELF",
        15: "GAIN_SHIELD",
        21: "DRAW_1",
        27: "SUMMON_SELF",
        33: "DESTROY_ATTACKER",
        37: "GAIN_SHIELD",
    }
    return effects.get(index)


def _spell_effect_for_index(index: int) -> str | None:
    effects: dict[int, str] = {
        3: "DRAW_1",
        7: "MANA_BOOST",
        11: "DESTROY_TARGET",
        15: "GAIN_SHIELD",
        19: "DRAW_1",
        23: "MANA_BOOST",
        29: "DESTROY_TARGET",
        33: "DESTROY_TARGET",
        35: "GAIN_SHIELD",
        37: "GAIN_SHIELD",
    }
    return effects.get(index)


def _card_name_prefix(is_blocker: bool, trigger_effect: TriggerEffect | None, spell_effect: str | None) -> str:
    if spell_effect is not None:
        return "Shield Trigger Spell" if trigger_effect is not None else "Spell"
    if trigger_effect is None:
        return "Blocker Creature" if is_blocker else "Vanilla Creature"
    if trigger_effect == "SUMMON_SELF":
        return "Shield Trigger Creature"
    return "Shield Trigger Spell"
