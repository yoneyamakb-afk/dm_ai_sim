from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ActionType(str, Enum):
    CHARGE_MANA = "CHARGE_MANA"
    SUMMON = "SUMMON"
    ATTACK_SHIELD = "ATTACK_SHIELD"
    ATTACK_PLAYER = "ATTACK_PLAYER"
    END_MAIN = "END_MAIN"
    END_ATTACK = "END_ATTACK"


@dataclass(frozen=True, slots=True)
class Action:
    type: ActionType
    card_index: int | None = None
    attacker_index: int | None = None
