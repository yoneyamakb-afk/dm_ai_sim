from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ActionType(str, Enum):
    CHARGE_MANA = "CHARGE_MANA"
    SUMMON = "SUMMON"
    CAST_SPELL = "CAST_SPELL"
    REVOLUTION_CHANGE = "REVOLUTION_CHANGE"
    INVASION = "INVASION"
    ATTACK_SHIELD = "ATTACK_SHIELD"
    ATTACK_PLAYER = "ATTACK_PLAYER"
    ATTACK_CREATURE = "ATTACK_CREATURE"
    BLOCK = "BLOCK"
    DECLINE_BLOCK = "DECLINE_BLOCK"
    END_MAIN = "END_MAIN"
    END_ATTACK = "END_ATTACK"


@dataclass(frozen=True, slots=True)
class Action:
    type: ActionType
    card_index: int | None = None
    hand_index: int | None = None
    attacker_index: int | None = None
    target_index: int | None = None
    blocker_index: int | None = None
    side: str | None = None
