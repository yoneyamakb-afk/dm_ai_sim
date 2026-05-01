from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from dm_ai_sim.card import Card
from dm_ai_sim.state import Creature


@dataclass(slots=True)
class ShieldBreakResult:
    shield_broken: bool = False
    broken_card_name: str | None = None
    card_added_to_hand: bool = False
    moved_to_graveyard: bool = False
    trigger_activated: bool = False
    trigger_effect: str | None = None
    g_strike_activated: bool = False
    g_strike_target_name: str | None = None
    attacker_destroyed_by_trigger: bool = False
    gained_shield: bool = False
    batch_id: int | None = None
    break_index: int | None = None
    simultaneous_count: int = 1
    removed_from_shield_zone_before_resolution: bool = False
    added_to_hand_before_trigger_resolution: bool = False
    trigger_resolution_order: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class BrokenShieldContext:
    card: Card
    batch_id: int
    break_index: int
    simultaneous_count: int
    removed_from_shield_zone_before_resolution: bool = True
    added_to_hand_before_trigger_resolution: bool = False


def break_one_shield(
    env: Any,
    attacker_player: int,
    defender_player: int,
    shield_index: int,
    attacker_instance: Any,
    info: dict[str, Any],
) -> dict[str, Any]:
    state = env.state
    if state is None:
        raise RuntimeError("Call reset() before breaking shields.")
    defender = state.players[defender_player]
    _set_break_defaults(info)
    if shield_index < 0 or shield_index >= len(defender.shields):
        return ShieldBreakResult().to_dict()

    card = defender.shields.pop(shield_index)
    context = BrokenShieldContext(
        card=card,
        batch_id=_next_batch_id(info),
        break_index=0,
        simultaneous_count=1,
    )
    result = _resolve_broken_shield_context(
        env,
        attacker_player,
        defender_player,
        context,
        attacker_instance,
        info,
        trigger_resolution_order=0,
    )
    info["shield_break_results"] = [result]
    return result


def collect_shields_to_break(env: Any, defender_player: int, count: int, info: dict[str, Any] | None = None) -> list[BrokenShieldContext]:
    state = env.state
    if state is None:
        raise RuntimeError("Call reset() before breaking shields.")
    defender = state.players[defender_player]
    planned_breaks = min(max(count, 0), len(defender.shields))
    batch_id = _next_batch_id(info)
    contexts: list[BrokenShieldContext] = []
    for break_index in range(planned_breaks):
        card = defender.shields.pop()
        contexts.append(
            BrokenShieldContext(
                card=card,
                batch_id=batch_id,
                break_index=break_index,
                simultaneous_count=planned_breaks,
            )
        )
    return contexts


def resolve_broken_shields(
    env: Any,
    attacker_player: int,
    defender_player: int,
    contexts: list[BrokenShieldContext],
    attacker_instance: Any,
    info: dict[str, Any],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for order, context in enumerate(contexts):
        results.append(
            _resolve_broken_shield_context(
                env,
                attacker_player,
                defender_player,
                context,
                attacker_instance,
                info,
                trigger_resolution_order=order,
            )
        )
    info["shield_break_results"] = results
    return results


def _resolve_broken_shield_context(
    env: Any,
    attacker_player: int,
    defender_player: int,
    context: BrokenShieldContext,
    attacker_instance: Any,
    info: dict[str, Any],
    trigger_resolution_order: int,
) -> dict[str, Any]:
    state = env.state
    if state is None:
        raise RuntimeError("Call reset() before breaking shields.")
    defender = state.players[defender_player]
    card = context.card
    result = ShieldBreakResult(
        shield_broken=True,
        broken_card_name=card.name,
        batch_id=context.batch_id,
        break_index=context.break_index,
        simultaneous_count=context.simultaneous_count,
        removed_from_shield_zone_before_resolution=context.removed_from_shield_zone_before_resolution,
        added_to_hand_before_trigger_resolution=context.added_to_hand_before_trigger_resolution,
        trigger_resolution_order=trigger_resolution_order,
    )
    info["shield_broken"] = True
    info["broken_shield_card"] = card.name

    trigger_card = card.side_as_card("bottom") if _can_use_twinpact_shield_trigger(card) else card
    if not trigger_card.shield_trigger or trigger_card.trigger_effect is None:
        if _has_g_strike(card):
            g_info = _resolve_g_strike(env, card, defender_player, attacker_player)
            info.update(g_info)
            result.g_strike_activated = bool(g_info.get("g_strike_activated"))
            result.g_strike_target_name = g_info.get("g_strike_target_name")
        defender.hand.append(card)
        result.card_added_to_hand = True
        return result.to_dict()

    effect = trigger_card.trigger_effect
    result.trigger_activated = True
    result.trigger_effect = effect
    info["trigger_activated"] = True
    info["trigger_effect"] = effect
    state.last_trigger_activated = True
    state.last_trigger_effect = effect
    state.last_trigger_player = defender_player

    if effect == "DRAW_1":
        defender.graveyard.append(card)
        result.moved_to_graveyard = True
        _draw_card(defender)
        return result.to_dict()

    if effect == "DESTROY_ATTACKER":
        defender.graveyard.append(card)
        result.moved_to_graveyard = True
        attacker_index = _attacker_index(state, attacker_player, attacker_instance)
        attacker_zone = state.players[attacker_player].battle_zone
        if attacker_index is not None and 0 <= attacker_index < len(attacker_zone):
            destroyed = attacker_zone.pop(attacker_index)
            state.players[attacker_player].graveyard.extend(_creature_zone_cards(destroyed))
            info["attacker_destroyed_by_trigger"] = True
            result.attacker_destroyed_by_trigger = True
        return result.to_dict()

    if effect == "SUMMON_SELF" and trigger_card.card_type == "CREATURE":
        defender.battle_zone.append(
            Creature(
                card=trigger_card,
                summoned_turn=state.turn_number,
                original_card=card if card.is_twinpact else None,
            )
        )
        return result.to_dict()

    if effect == "GAIN_SHIELD":
        defender.graveyard.append(card)
        result.moved_to_graveyard = True
        if defender.deck:
            defender.shields.append(defender.deck.pop())
            result.gained_shield = True
        return result.to_dict()

    defender.hand.append(card)
    result.card_added_to_hand = True
    result.trigger_activated = False
    result.trigger_effect = None
    info["trigger_activated"] = False
    info["trigger_effect"] = None
    _clear_last_trigger(state)
    return result.to_dict()


def break_shields(
    env: Any,
    attacker_player: int,
    defender_player: int,
    count: int,
    attacker_instance: Any,
    info: dict[str, Any],
) -> list[dict[str, Any]]:
    state = env.state
    if state is None:
        raise RuntimeError("Call reset() before breaking shields.")
    _set_break_defaults(info)
    contexts = collect_shields_to_break(env, defender_player, count, info=info)
    return resolve_broken_shields(env, attacker_player, defender_player, contexts, attacker_instance, info)


def _set_break_defaults(info: dict[str, Any]) -> None:
    info.setdefault("shield_broken", False)
    info.setdefault("broken_shield_card", None)
    info.setdefault("trigger_activated", False)
    info.setdefault("trigger_effect", None)
    info.setdefault("attacker_destroyed_by_trigger", False)
    info.setdefault("g_strike_activated", False)
    info.setdefault("g_strike_card_name", None)
    info.setdefault("g_strike_target_index", None)
    info.setdefault("g_strike_target_name", None)
    info.setdefault("g_strike_prevented_attack", False)
    info.setdefault("g_strike_source_zone", None)
    info.setdefault("shield_break_results", [])


def _resolve_g_strike(env: Any, card: Card, defender_player: int, attacker_player: int) -> dict[str, Any]:
    info: dict[str, Any] = {
        "g_strike_activated": True,
        "g_strike_card_name": card.name,
        "g_strike_target_index": None,
        "g_strike_target_name": None,
        "g_strike_prevented_attack": False,
        "g_strike_source_zone": "shield",
    }
    handler = env.ability_registry.get_handler("G_STRIKE")
    if handler is not None and hasattr(handler, "apply_g_strike"):
        return handler.apply_g_strike(env, card, defender_player, attacker_player, info)
    return info


def _can_use_twinpact_shield_trigger(card: Card) -> bool:
    return (
        card.is_twinpact
        and card.bottom_side is not None
        and card.bottom_side.card_type == "SPELL"
        and card.bottom_side.shield_trigger
        and card.bottom_side.trigger_effect is not None
    )


def _has_g_strike(card: Card) -> bool:
    return any(handler.tag == "G_STRIKE" for handler in _default_registry().get_handlers_for_card(card))


def _default_registry():
    from dm_ai_sim.ability_handlers.registry import get_default_ability_registry

    return get_default_ability_registry()


def _draw_card(player) -> bool:
    if not player.deck:
        return False
    player.hand.append(player.deck.pop())
    return True


def _attacker_index(state, attacker_player: int, attacker_instance: Any) -> int | None:
    if isinstance(attacker_instance, int):
        return attacker_instance
    if attacker_instance is None:
        return None
    for index, creature in enumerate(state.players[attacker_player].battle_zone):
        if creature is attacker_instance:
            return index
    return None


def _creature_zone_cards(creature: Creature) -> list[Card]:
    return [creature.original_card or creature.card] + list(creature.evolution_sources)


def _clear_last_trigger(state) -> None:
    state.last_trigger_activated = False
    state.last_trigger_effect = None
    state.last_trigger_player = None


def _next_batch_id(info: dict[str, Any] | None) -> int:
    if info is None:
        return 1
    batch_id = int(info.get("_next_shield_break_batch_id", 1))
    info["_next_shield_break_batch_id"] = batch_id + 1
    return batch_id
