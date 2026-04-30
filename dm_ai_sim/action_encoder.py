from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dm_ai_sim.actions import Action, ActionType

MAX_HAND_SLOTS = 40
MAX_CREATURE_SLOTS = 40
MAX_ATTACK_CREATURE_ATTACKERS = 10
MAX_ATTACK_CREATURE_TARGETS = 8
MAX_BLOCKER_SLOTS = 8
MAX_CAST_SPELL_HAND_SLOTS = 40
MAX_CAST_SPELL_TARGET_HAND_SLOTS = 10
MAX_CAST_SPELL_TARGETS = 8
MAX_REVOLUTION_CHANGE_HAND_SLOTS = 10
MAX_REVOLUTION_CHANGE_ATTACKERS = 8
MAX_INVASION_HAND_SLOTS = 10
MAX_INVASION_ATTACKERS = 8

CHARGE_MANA_OFFSET = 0
SUMMON_OFFSET = 40
ATTACK_SHIELD_OFFSET = 80
ATTACK_PLAYER_OFFSET = 120
END_MAIN_ID = 160
END_ATTACK_ID = 161
ATTACK_CREATURE_OFFSET = 162
ATTACK_CREATURE_SIZE = MAX_ATTACK_CREATURE_ATTACKERS * MAX_ATTACK_CREATURE_TARGETS
BLOCK_OFFSET = 242
DECLINE_BLOCK_ID = 250
CAST_SPELL_OFFSET = 256
CAST_SPELL_TARGET_OFFSET = 296
CAST_SPELL_TARGET_SIZE = MAX_CAST_SPELL_TARGET_HAND_SLOTS * MAX_CAST_SPELL_TARGETS
REVOLUTION_CHANGE_OFFSET = 384
REVOLUTION_CHANGE_SIZE = MAX_REVOLUTION_CHANGE_HAND_SLOTS * MAX_REVOLUTION_CHANGE_ATTACKERS
INVASION_OFFSET = 512
INVASION_SIZE = MAX_INVASION_HAND_SLOTS * MAX_INVASION_ATTACKERS

ACTION_SPACE_SIZE = 640
SUPPORTED_ACTION_IDS = INVASION_OFFSET + INVASION_SIZE


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
    if normalized.type == ActionType.CAST_SPELL:
        hand_index = normalized.hand_index if normalized.hand_index is not None else normalized.card_index
        if normalized.target_index is None:
            return CAST_SPELL_OFFSET + _require_range(hand_index, MAX_CAST_SPELL_HAND_SLOTS)
        return (
            CAST_SPELL_TARGET_OFFSET
            + _require_range(hand_index, MAX_CAST_SPELL_TARGET_HAND_SLOTS) * MAX_CAST_SPELL_TARGETS
            + _require_range(normalized.target_index, MAX_CAST_SPELL_TARGETS)
        )
    if normalized.type == ActionType.REVOLUTION_CHANGE:
        hand_index = normalized.hand_index if normalized.hand_index is not None else normalized.card_index
        return (
            REVOLUTION_CHANGE_OFFSET
            + _require_range(hand_index, MAX_REVOLUTION_CHANGE_HAND_SLOTS) * MAX_REVOLUTION_CHANGE_ATTACKERS
            + _require_range(normalized.attacker_index, MAX_REVOLUTION_CHANGE_ATTACKERS)
        )
    if normalized.type == ActionType.INVASION:
        hand_index = normalized.hand_index if normalized.hand_index is not None else normalized.card_index
        return (
            INVASION_OFFSET
            + _require_range(hand_index, MAX_INVASION_HAND_SLOTS) * MAX_INVASION_ATTACKERS
            + _require_range(normalized.attacker_index, MAX_INVASION_ATTACKERS)
        )
    if normalized.type == ActionType.BLOCK:
        return BLOCK_OFFSET + _require_range(normalized.blocker_index, MAX_BLOCKER_SLOTS)
    if normalized.type == ActionType.DECLINE_BLOCK:
        return DECLINE_BLOCK_ID
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
    if BLOCK_OFFSET <= action_id < BLOCK_OFFSET + MAX_BLOCKER_SLOTS:
        return Action(ActionType.BLOCK, blocker_index=action_id - BLOCK_OFFSET)
    if action_id == DECLINE_BLOCK_ID:
        return Action(ActionType.DECLINE_BLOCK)
    if CAST_SPELL_OFFSET <= action_id < CAST_SPELL_OFFSET + MAX_CAST_SPELL_HAND_SLOTS:
        return Action(ActionType.CAST_SPELL, hand_index=action_id - CAST_SPELL_OFFSET)
    if CAST_SPELL_TARGET_OFFSET <= action_id < CAST_SPELL_TARGET_OFFSET + CAST_SPELL_TARGET_SIZE:
        encoded = action_id - CAST_SPELL_TARGET_OFFSET
        return Action(
            ActionType.CAST_SPELL,
            hand_index=encoded // MAX_CAST_SPELL_TARGETS,
            target_index=encoded % MAX_CAST_SPELL_TARGETS,
        )
    if REVOLUTION_CHANGE_OFFSET <= action_id < REVOLUTION_CHANGE_OFFSET + REVOLUTION_CHANGE_SIZE:
        encoded = action_id - REVOLUTION_CHANGE_OFFSET
        return Action(
            ActionType.REVOLUTION_CHANGE,
            hand_index=encoded // MAX_REVOLUTION_CHANGE_ATTACKERS,
            attacker_index=encoded % MAX_REVOLUTION_CHANGE_ATTACKERS,
        )
    if INVASION_OFFSET <= action_id < INVASION_OFFSET + INVASION_SIZE:
        encoded = action_id - INVASION_OFFSET
        return Action(
            ActionType.INVASION,
            hand_index=encoded // MAX_INVASION_ATTACKERS,
            attacker_index=encoded % MAX_INVASION_ATTACKERS,
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
            hand_index=action.get("hand_index"),
            attacker_index=action.get("attacker_index"),
            target_index=action.get("target_index"),
            blocker_index=action.get("blocker_index"),
            side=action.get("side"),
        )
    raise ValueError(f"Unsupported action object: {action!r}")


def _require_range(value: int | None, upper_bound: int) -> int:
    if value is None:
        raise ValueError("Action index is required for this action type.")
    if value < 0 or value >= upper_bound:
        raise ValueError(f"Action index out of range: {value}")
    return value
