from __future__ import annotations

import json
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dm_ai_sim.card import Card
from dm_ai_sim.card_tags import KNOWN_ABILITY_TAGS


@dataclass(frozen=True, slots=True)
class TwinpactSideData:
    name: str
    cost: int | None
    civilizations: tuple[str, ...]
    card_type: str
    power: int | None
    races: tuple[str, ...] = ()
    text: str = ""
    ability_tags: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, raw: dict[str, Any] | None) -> "TwinpactSideData | None":
        if raw is None:
            return None
        ability_tags = tuple(str(tag) for tag in raw.get("ability_tags", ()))
        unknown = [tag for tag in ability_tags if tag not in KNOWN_ABILITY_TAGS]
        if unknown:
            warnings.warn(f"Unknown ability tags on twinpact side {raw.get('name')}: {unknown}", RuntimeWarning, stacklevel=2)
        return cls(
            name=str(raw.get("name", "")),
            cost=int(raw["cost"]) if raw.get("cost") is not None else None,
            civilizations=tuple(str(value).upper() for value in raw.get("civilizations", ["UNKNOWN"])),
            card_type=str(raw.get("card_type", "UNKNOWN")).upper(),
            power=int(raw["power"]) if raw.get("power") is not None else None,
            races=tuple(str(value) for value in raw.get("races", ())),
            text=str(raw.get("text", "")),
            ability_tags=ability_tags,
        )


@dataclass(frozen=True, slots=True)
class CardData:
    card_id: str
    name: str
    name_kana: str
    cost: int | None
    civilizations: tuple[str, ...]
    card_type: str
    power: int | None
    races: tuple[str, ...] = ()
    text: str = ""
    shield_trigger: bool = False
    blocker: bool = False
    spell_effect: str | None = None
    trigger_effect: str | None = None
    ability_tags: tuple[str, ...] = ()
    implemented_tags: tuple[str, ...] = ()
    unsupported_tags: tuple[str, ...] = ()
    regulation: dict[str, Any] = field(default_factory=dict)
    notes: str = ""
    is_twinpact: bool = False
    top_side: TwinpactSideData | None = None
    bottom_side: TwinpactSideData | None = None

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "CardData":
        ability_tags = tuple(str(tag) for tag in raw.get("ability_tags", ()))
        unknown = [tag for tag in ability_tags if tag not in KNOWN_ABILITY_TAGS]
        if unknown:
            warnings.warn(f"Unknown ability tags on {raw.get('card_id')}: {unknown}", RuntimeWarning, stacklevel=2)
        return cls(
            card_id=str(raw["card_id"]),
            name=str(raw["name"]),
            name_kana=str(raw.get("name_kana", "")),
            cost=int(raw["cost"]) if raw.get("cost") is not None else None,
            civilizations=tuple(str(value).upper() for value in raw.get("civilizations", ["COLORLESS"])),
            card_type=str(raw.get("card_type", "CREATURE")).upper(),
            power=int(raw["power"]) if raw.get("power") is not None else None,
            races=tuple(str(value) for value in raw.get("races", ())),
            text=str(raw.get("text", "")),
            shield_trigger=bool(raw.get("shield_trigger", False)),
            blocker=bool(raw.get("blocker", False)),
            spell_effect=raw.get("spell_effect"),
            trigger_effect=raw.get("trigger_effect"),
            ability_tags=ability_tags,
            implemented_tags=tuple(str(tag) for tag in raw.get("implemented_tags", ())),
            unsupported_tags=tuple(str(tag) for tag in raw.get("unsupported_tags", ())),
            regulation=dict(raw.get("regulation", {})),
            notes=str(raw.get("notes", "")),
            is_twinpact=bool(raw.get("is_twinpact", False)),
            top_side=TwinpactSideData.from_mapping(raw.get("top_side")),
            bottom_side=TwinpactSideData.from_mapping(raw.get("bottom_side")),
        )


@dataclass(slots=True)
class CardDatabase:
    cards: dict[str, CardData]

    def get(self, card_id: str) -> CardData:
        try:
            return self.cards[card_id]
        except KeyError as exc:
            raise KeyError(f"Unknown card_id: {card_id}") from exc

    def find_by_name(self, name: str) -> list[CardData]:
        normalized = name.casefold()
        return [card for card in self.cards.values() if normalized in card.name.casefold()]

    def list_supported(self) -> list[CardData]:
        return [card for card in self.cards.values() if not card.unsupported_tags]

    def list_unsupported(self) -> list[CardData]:
        return [card for card in self.cards.values() if card.unsupported_tags]

    def to_runtime_card(self, card_id: str, strict: bool = False) -> Card:
        card = self.get(card_id)
        if card.is_twinpact:
            message = f"{card.card_id} is a twinpact card and runtime twinpact conversion is not supported"
            if strict:
                raise ValueError(message)
            warnings.warn(message, RuntimeWarning, stacklevel=2)
            raise ValueError(message)
        unknown_fields = unknown_data_fields(card)
        if card.unsupported_tags or unknown_fields:
            parts = []
            if card.unsupported_tags:
                parts.append(f"unsupported tags: {', '.join(card.unsupported_tags)}")
            if unknown_fields:
                parts.append(f"unknown data: {', '.join(unknown_fields)}")
            message = f"{card.card_id} has " + "; ".join(parts)
            if strict:
                raise ValueError(message)
            warnings.warn(message, RuntimeWarning, stacklevel=2)
        return Card(
            id=_stable_runtime_id(card.card_id),
            name=card.name,
            cost=card.cost or 0,
            power=card.power or 0,
            civilizations=tuple(civ for civ in card.civilizations if civ != "UNKNOWN") or ("COLORLESS",),
            blocker=card.blocker,
            shield_trigger=card.shield_trigger,
            card_type=card.card_type if card.card_type in {"CREATURE", "SPELL"} else "CREATURE",  # type: ignore[arg-type]
            trigger_effect=card.trigger_effect,  # type: ignore[arg-type]
            spell_effect=card.spell_effect,
            ability_tags=card.ability_tags,
        )


def load_card_database(path: str | Path) -> CardDatabase:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Card database JSON must be a list.")
    cards = [CardData.from_mapping(item) for item in raw]
    by_id: dict[str, CardData] = {}
    for card in cards:
        if card.card_id in by_id:
            raise ValueError(f"Duplicate card_id: {card.card_id}")
        by_id[card.card_id] = card
    return CardDatabase(by_id)


def unknown_data_fields(card: CardData) -> tuple[str, ...]:
    fields: list[str] = []
    if card.is_twinpact:
        return tuple(missing_official_data_fields(card))
    if card.cost is None:
        fields.append("cost")
    if card.power is None and card.card_type == "CREATURE":
        fields.append("power")
    if not card.civilizations or "UNKNOWN" in card.civilizations:
        fields.append("civilizations")
    if card.card_type not in {"CREATURE", "SPELL"}:
        fields.append("card_type")
    return tuple(fields)


def missing_official_data_fields(card: CardData) -> tuple[str, ...]:
    fields: list[str] = []
    if card.is_twinpact:
        _extend_missing_side_fields(fields, "top_side", card.top_side)
        _extend_missing_side_fields(fields, "bottom_side", card.bottom_side)
        return tuple(fields)
    if card.cost is None:
        fields.append("cost")
    if not card.civilizations or "UNKNOWN" in card.civilizations:
        fields.append("civilizations")
    if card.card_type not in {"CREATURE", "SPELL"}:
        fields.append("card_type")
    if card.card_type == "CREATURE" and card.power is None:
        fields.append("power")
    if not card.text:
        fields.append("text")
    return tuple(fields)


def _extend_missing_side_fields(fields: list[str], prefix: str, side: TwinpactSideData | None) -> None:
    if side is None:
        fields.append(prefix)
        return
    if side.cost is None:
        fields.append("cost")
    if not side.civilizations or "UNKNOWN" in side.civilizations:
        fields.append("civilizations")
    if side.card_type not in {"CREATURE", "SPELL"}:
        fields.append("card_type")
    if side.card_type == "CREATURE" and side.power is None:
        fields.append("power")
    if not side.text:
        fields.append("text")


def _stable_runtime_id(card_id: str) -> int:
    return sum((index + 1) * ord(char) for index, char in enumerate(card_id)) % 1_000_000
