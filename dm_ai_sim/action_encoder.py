from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dm_ai_sim.actions import Action, ActionType

MAX_HAND_SLOTS = 40
MAX_CREATURE_SLOTS = 40
MAX_ATTACK_CREATURE_ATTACKERS = 10
MAX_ATTACK_CREATURE_TARGETS = 8

CHARGE_MANA_OFFSET = 0
SUMMON_OFFSET = 40
ATTACK_SHIELD_OFFSET = 80
ATTACK_PLAYER_OFFSET = 120
END_MAIN_ID = 160
END_ATTACK_ID = 161
ATTACK_CREATURE_OFFSET = 162
ATTACK_CREATURE_SIZE = MAX_ATTACK_CREATURE_ATTACKERS * MAX_ATTACK_CREATURE_TARGETS

ACTION_SPACE_SIZE = 256
SUPPORTED_ACTION_IDS = ATTACK_CREATURE_OFFSET + ATTACK_CREATURE_SIZE


def encode_action(action: Action | Mapping[str, Any]) -> int:
    normalized = _normalize_action(action)

    if normalized.type == ActionType.CHARGE_MANA:
        return CHARGE_MANA_OFFSET + _require_range(normalized.card_index, MAX_HAND_SLOTS)
    if normalized.type == ActionType.SUMMON:
        return SUMMON_OFFSET + _require_range(normalized.card_index, MAX_HAND_SLOTS)
    if normalized.type == ActionType.ATTACK_SHIELD:
        return ATTACK_SHIELD_OFFSET + _require_range(normalized.attacker_index, MAX_CREATURE_SLOTS)
    if normalized.type == ActionType.ATTACK_PLAYER:
        return ATTACK_PLAYER_OFFSET + _require_range(normalized.attacker_index, MAX_CREATURE_SLOTS)
    if normalized.type == ActionType.ATTACK_CREATURE:
        attacker_index = _require_range(normalized.attacker_index, MAX_ATTACK_CREATURE_ATTACKERS)
        target_index = _require_range(normalized.target_index, MAX_ATTACK_CREATURE_TARGETS)
        return ATTACK_CREATURE_OFFSET + attacker_index * MAX_ATTACK_CREATURE_TARGETS + target_index
    if normalized.type == ActionType.END_MAIN:
        return END_MAIN_ID
    if normalized.type == ActionType.END_ATTACK:
        return END_ATTACK_ID

    raise ValueError(f"Unsupported action type: {normalized.type}")


def decode_action(action_id: int) -> Action:
    if not isinstance(action_id, int):
        raise ValueError(f"action_id must be int, got {type(action_id).__name__}")
    if action_id < 0 or action_id >= ACTION_SPACE_SIZE:
        raise ValueError(f"action_id out of range: {action_id}")

    if CHARGE_MANA_OFFSET <= action_id < SUMMON_OFFSET:
        return Action(ActionType.CHARGE_MANA, card_index=action_id - CHARGE_MANA_OFFSET)
    if SUMMON_OFFSET <= action_id < ATTACK_SHIELD_OFFSET:
        return Action(ActionType.SUMMON, card_index=action_id - SUMMON_OFFSET)
    if ATTACK_SHIELD_OFFSET <= action_id < ATTACK_PLAYER_OFFSET:
        return Action(ActionType.ATTACK_SHIELD, attacker_index=action_id - ATTACK_SHIELD_OFFSET)
    if ATTACK_PLAYER_OFFSET <= action_id < END_MAIN_ID:
        return Action(ActionType.ATTACK_PLAYER, attacker_index=action_id - ATTACK_PLAYER_OFFSET)
    if action_id == END_MAIN_ID:
        return Action(ActionType.END_MAIN)
    if action_id == END_ATTACK_ID:
        return Action(ActionType.END_ATTACK)
    if ATTACK_CREATURE_OFFSET <= action_id < ATTACK_CREATURE_OFFSET + ATTACK_CREATURE_SIZE:
        encoded = action_id - ATTACK_CREATURE_OFFSET
        return Action(
            ActionType.ATTACK_CREATURE,
            attacker_index=encoded // MAX_ATTACK_CREATURE_TARGETS,
            target_index=encoded % MAX_ATTACK_CREATURE_TARGETS,
        )

    raise ValueError(f"Reserved action_id is not currently decodable: {action_id}")


def legal_action_mask(env: Any) -> list[int]:
    mask = [0] * ACTION_SPACE_SIZE
    for action_id in env.legal_action_ids():
        mask[action_id] = 1
    return mask


def _normalize_action(action: Action | Mapping[str, Any]) -> Action:
    if isinstance(action, Action):
        return action
    if isinstance(action, Mapping):
        raw_type = action.get("type")
        action_type = raw_type if isinstance(raw_type, ActionType) else ActionType(str(raw_type))
        return Action(
            action_type,
            card_index=action.get("card_index"),
            attacker_index=action.get("attacker_index"),
            target_index=action.get("target_index"),
        )
    raise ValueError(f"Unsupported action object: {action!r}")


def _require_range(value: int | None, upper_bound: int) -> int:
    if value is None:
        raise ValueError("Action index is required for this action type.")
    if value < 0 or value >= upper_bound:
        raise ValueError(f"Action index out of range: {value}")
    return value
