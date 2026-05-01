from __future__ import annotations

from typing import Any

from dm_ai_sim.state import Creature, GameState, Phase


def can_creature_attack(env: Any, player_id: int, creature_index: int) -> bool:
    state = getattr(env, "state", None)
    if state is None:
        return False
    return can_creature_attack_in_state(
        state,
        player_id,
        creature_index,
        registry=getattr(env, "ability_registry", None),
    )


def get_attackable_creatures(env: Any, player_id: int) -> list[int]:
    state = getattr(env, "state", None)
    if state is None or player_id < 0 or player_id >= len(state.players):
        return []
    return [
        index
        for index in range(len(state.players[player_id].battle_zone))
        if can_creature_attack(env, player_id, index)
    ]


def can_be_gstrike_target(env: Any, attacker_player: int, creature_index: int) -> bool:
    return can_creature_attack(env, attacker_player, creature_index)


def get_gstrike_targets(env: Any, attacker_player: int) -> list[int]:
    state = getattr(env, "state", None)
    if state is None or attacker_player < 0 or attacker_player >= len(state.players):
        return []
    return [
        index
        for index in range(len(state.players[attacker_player].battle_zone))
        if can_be_gstrike_target(env, attacker_player, index)
    ]


def can_creature_attack_in_state(
    state: GameState,
    player_id: int,
    creature_index: int,
    registry: Any | None = None,
) -> bool:
    if state.phase != Phase.ATTACK:
        return False
    if state.pending_attack is not None:
        return False
    if state.done or state.winner is not None:
        return False
    if player_id != state.current_player:
        return False
    if player_id < 0 or player_id >= len(state.players):
        return False
    battle_zone = state.players[player_id].battle_zone
    if creature_index < 0 or creature_index >= len(battle_zone):
        return False
    return creature_has_attack_permission(battle_zone[creature_index], state, player_id, registry=registry)


def get_attackable_creatures_in_state(
    state: GameState,
    player_id: int,
    registry: Any | None = None,
) -> list[int]:
    if player_id < 0 or player_id >= len(state.players):
        return []
    return [
        index
        for index in range(len(state.players[player_id].battle_zone))
        if can_creature_attack_in_state(state, player_id, index, registry=registry)
    ]


def creature_has_attack_permission(
    creature: Creature,
    state: GameState,
    player_id: int,
    registry: Any | None = None,
) -> bool:
    if creature.tapped or creature.cannot_attack_this_turn:
        return False
    handler_allows_attack = False
    for handler in _ability_registry(registry).get_handlers_for_card(creature):
        modified = handler.modifies_attack_permission(creature, state, player_id)
        if modified is False:
            return False
        if modified is True:
            handler_allows_attack = True
    if handler_allows_attack:
        return True
    tags = set(creature.card.ability_tags)
    has_attack_ready_evolution = bool({"INVASION", "ATTACKING_CREATURE_EVOLUTION"} & tags)
    return has_attack_ready_evolution or creature.summoned_turn < state.turn_number


def _ability_registry(registry: Any | None) -> Any:
    if registry is not None:
        return registry
    from dm_ai_sim.ability_handlers.registry import get_default_ability_registry

    return get_default_ability_registry()
