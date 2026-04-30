from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class EventType(StrEnum):
    TURN_START = "TURN_START"
    TURN_END = "TURN_END"
    CARD_DRAWN = "CARD_DRAWN"
    MANA_CHARGED = "MANA_CHARGED"
    CARD_CAST = "CARD_CAST"
    CREATURE_SUMMONED = "CREATURE_SUMMONED"
    ATTACK_DECLARED = "ATTACK_DECLARED"
    ATTACK_RESOLVED = "ATTACK_RESOLVED"
    CREATURE_BATTLE_RESOLVED = "CREATURE_BATTLE_RESOLVED"
    SHIELD_BROKEN = "SHIELD_BROKEN"
    CARD_REVEALED_FOR_GACHINKO = "CARD_REVEALED_FOR_GACHINKO"
    GACHINKO_JUDGE_RESOLVED = "GACHINKO_JUDGE_RESOLVED"
    CREATURE_DESTROYED = "CREATURE_DESTROYED"
    CARD_MOVED = "CARD_MOVED"
    ACTION_GENERATION = "ACTION_GENERATION"
    ATTACK_PERMISSION_CHECK = "ATTACK_PERMISSION_CHECK"


@dataclass(slots=True)
class Event:
    type: EventType
    player: int | None = None
    opponent: int | None = None
    card: Any | None = None
    source: Any | None = None
    payload: dict[str, Any] = field(default_factory=dict)
