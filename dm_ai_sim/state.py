from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from dm_ai_sim.card import Card


class Phase(str, Enum):
    MAIN = "main"
    ATTACK = "attack"
    GAME_OVER = "game_over"


@dataclass(slots=True)
class ManaCard:
    card: Card
    tapped: bool = False


@dataclass(slots=True)
class Creature:
    card: Card
    tapped: bool = False
    summoned_turn: int = 0


@dataclass(slots=True)
class PlayerState:
    deck: list[Card]
    hand: list[Card] = field(default_factory=list)
    shields: list[Card] = field(default_factory=list)
    mana: list[ManaCard] = field(default_factory=list)
    battle_zone: list[Creature] = field(default_factory=list)
    graveyard: list[Card] = field(default_factory=list)
    charged_mana_this_turn: bool = False


@dataclass(slots=True)
class PendingAttack:
    attacker_player: int
    defender_player: int
    attacker_index: int
    target_type: str
    target_index: int | None
    original_phase: Phase
    context_id: int = 0


@dataclass(slots=True)
class GameState:
    players: list[PlayerState]
    current_player: int = 0
    phase: Phase = Phase.MAIN
    turn_number: int = 1
    winner: int | None = None
    done: bool = False
    first_turn: bool = True
    pending_attack: PendingAttack | None = None
    next_attack_context_id: int = 1
    last_trigger_activated: bool = False
    last_trigger_effect: str | None = None
    last_trigger_player: int | None = None
    last_spell_cast: bool = False
    last_spell_effect: str | None = None
    last_spell_player: int | None = None

    @property
    def opponent(self) -> int:
        return 1 - self.current_player
