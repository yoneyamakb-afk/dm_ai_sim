from __future__ import annotations

from typing import Any

from dm_ai_sim.ability_handlers.base import AbilityHandler


class SpeedAttackerHandler(AbilityHandler):
    tag = "SPEED_ATTACKER"

    def modifies_attack_permission(self, creature: Any, game_state: Any, player_id: int) -> bool | None:
        if not self.can_handle(creature):
            return None
        if creature.tapped or creature.cannot_attack_this_turn:
            return False
        return True
