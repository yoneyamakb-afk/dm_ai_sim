from __future__ import annotations

from functools import lru_cache
from typing import Iterable

from dm_ai_sim.ability_handlers.base import AbilityHandler
from dm_ai_sim.ability_handlers.g_strike import GStrikeHandler
from dm_ai_sim.ability_handlers.speed_attacker import SpeedAttackerHandler


class AbilityRegistry:
    def __init__(self) -> None:
        self._handlers_by_tag: dict[str, list[AbilityHandler]] = {}

    def register(self, handler: AbilityHandler) -> None:
        if not handler.tag:
            raise ValueError("AbilityHandler.tag must be set.")
        self._handlers_by_tag.setdefault(handler.tag, []).append(handler)

    def get_handler(self, tag: str) -> AbilityHandler | None:
        handlers = self._handlers_by_tag.get(tag, [])
        return handlers[0] if handlers else None

    def get_handlers_for_tags(self, tags: Iterable[str]) -> list[AbilityHandler]:
        handlers: list[AbilityHandler] = []
        for tag in tags:
            handlers.extend(self._handlers_by_tag.get(str(tag), []))
        return handlers

    def get_handlers_for_card(self, card_or_creature) -> list[AbilityHandler]:
        return [
            handler
            for handlers in self._handlers_by_tag.values()
            for handler in handlers
            if handler.can_handle(card_or_creature)
        ]


@lru_cache(maxsize=1)
def get_default_ability_registry() -> AbilityRegistry:
    registry = AbilityRegistry()
    registry.register(SpeedAttackerHandler())
    registry.register(GStrikeHandler())
    return registry
