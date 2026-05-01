from __future__ import annotations

from dm_ai_sim.actions import Action, ActionType
from dm_ai_sim.attack_permissions import can_creature_attack_in_state, get_attackable_creatures_in_state
from dm_ai_sim.mana import can_pay_for_card, can_pay_for_summon
from dm_ai_sim.state import GameState, Phase, PlayerState


def can_attack(creature_index: int, state: GameState) -> bool:
    return can_creature_attack_in_state(state, state.current_player, creature_index)


def spell_effect(card) -> str | None:
    effect = card.spell_effect or card.trigger_effect
    if effect is None and "NEXT_CREATURE_COST_REDUCTION" in card.ability_tags:
        return "NEXT_CREATURE_COST_REDUCTION"
    return effect


def legal_actions(state: GameState) -> list[Action]:
    if state.phase == Phase.GAME_OVER or state.winner is not None:
        return []

    player = state.players[state.current_player]
    if state.pending_attack is not None:
        actions = [
            Action(ActionType.BLOCK, blocker_index=index)
            for index, creature in enumerate(player.battle_zone)
            if creature.card.blocker and not creature.tapped
        ]
        actions.append(Action(ActionType.DECLINE_BLOCK))
        return actions

    opponent = state.players[state.opponent]
    actions: list[Action] = []

    if state.phase == Phase.MAIN:
        if not player.charged_mana_this_turn:
            actions.extend(
                Action(ActionType.CHARGE_MANA, card_index=index)
                for index in range(len(player.hand))
            )

        for index, card in enumerate(player.hand):
            if card.is_twinpact:
                if card.top_side is not None and card.top_side.card_type == "CREATURE":
                    top_card = card.side_as_card("top")
                    if can_pay_for_summon(player, top_card):
                        actions.append(Action(ActionType.SUMMON, card_index=index, side="top"))
                if card.bottom_side is not None and card.bottom_side.card_type == "SPELL":
                    bottom_card = card.side_as_card("bottom")
                    if can_pay_for_card(player, bottom_card):
                        _append_spell_actions(actions, index, bottom_card, opponent, side="bottom")
                continue
            if card.card_type == "CREATURE" and can_pay_for_summon(player, card):
                actions.append(Action(ActionType.SUMMON, card_index=index))
                continue
            if card.card_type != "SPELL" or not can_pay_for_card(player, card):
                continue
            _append_spell_actions(actions, index, card, opponent)
        actions.append(Action(ActionType.END_MAIN))
        return actions

    if state.phase == Phase.ATTACK:
        attackable_indices = get_attackable_creatures_in_state(state, state.current_player)
        attackable_set = set(attackable_indices)
        if not state.invaded_this_turn:
            for hand_index, card in enumerate(player.hand):
                if card.card_type != "CREATURE" or "INVASION" not in card.ability_tags:
                    continue
                actions.extend(
                    Action(ActionType.INVASION, hand_index=hand_index, attacker_index=attacker_index)
                    for attacker_index in attackable_indices
                )
        if not state.revolution_changed_this_turn:
            for hand_index, card in enumerate(player.hand):
                if card.card_type != "CREATURE" or "REVOLUTION_CHANGE" not in card.ability_tags:
                    continue
                actions.extend(
                    Action(ActionType.REVOLUTION_CHANGE, hand_index=hand_index, attacker_index=attacker_index)
                    for attacker_index in attackable_indices
                )
        for index in range(len(player.battle_zone)):
            if index not in attackable_set:
                continue
            actions.extend(
                Action(ActionType.ATTACK_CREATURE, attacker_index=index, target_index=target_index)
                for target_index in range(len(opponent.battle_zone))
            )
            if opponent.shields:
                actions.append(Action(ActionType.ATTACK_SHIELD, attacker_index=index))
            else:
                actions.append(Action(ActionType.ATTACK_PLAYER, attacker_index=index))
        actions.append(Action(ActionType.END_ATTACK))
        return actions

    return actions


def _append_spell_actions(actions: list[Action], index: int, card, opponent: PlayerState, side: str | None = None) -> None:
    effect = spell_effect(card)
    if effect == "DESTROY_TARGET":
        actions.extend(
            Action(ActionType.CAST_SPELL, hand_index=index, target_index=target_index, side=side)
            for target_index in range(len(opponent.battle_zone))
        )
    elif effect in {"DRAW_1", "GAIN_SHIELD", "MANA_BOOST", "NEXT_CREATURE_COST_REDUCTION"}:
        actions.append(Action(ActionType.CAST_SPELL, hand_index=index, side=side))
