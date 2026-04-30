from __future__ import annotations

from typing import Any


class AbilityHandler:
    tag: str = ""

    def modifies_attack_permission(self, creature: Any, game_state: Any, player_id: int) -> bool | None:
        return None

    def on_event(self, event: Any, env: Any, info: dict[str, Any]) -> None:
        return None

    def generate_actions(self, env: Any, player_id: int) -> list[Any]:
        return []

    def can_handle(self, card_or_creature: Any) -> bool:
        return self.tag in _ability_tags(card_or_creature)


def _ability_tags(card_or_creature: Any) -> tuple[str, ...]:
    card = getattr(card_or_creature, "card", card_or_creature)
    return tuple(getattr(card, "ability_tags", ()) or ())
