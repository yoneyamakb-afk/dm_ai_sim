from __future__ import annotations

from dm_ai_sim.actions import Action, ActionType
from dm_ai_sim.mana import can_pay_for_card, untapped_mana_count
from dm_ai_sim.state import GameState, Phase, PlayerState


def can_attack(creature_index: int, state: GameState) -> bool:
    creature = state.players[state.current_player].battle_zone[creature_index]
    return not creature.tapped and creature.summoned_turn < state.turn_number


def spell_effect(card) -> str | None:
    return card.spell_effect or card.trigger_effect


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

        actions.extend(
            Action(ActionType.SUMMON, card_index=index)
            for index, card in enumerate(player.hand)
            if card.card_type == "CREATURE" and can_pay_for_card(player, card)
        )
        for index, card in enumerate(player.hand):
            if card.card_type != "SPELL" or not can_pay_for_card(player, card):
                continue
            effect = spell_effect(card)
            if effect == "DESTROY_TARGET":
                actions.extend(
                    Action(ActionType.CAST_SPELL, hand_index=index, target_index=target_index)
                    for target_index in range(len(opponent.battle_zone))
                )
            elif effect in {"DRAW_1", "GAIN_SHIELD", "MANA_BOOST"}:
                actions.append(Action(ActionType.CAST_SPELL, hand_index=index))
        actions.append(Action(ActionType.END_MAIN))
        return actions

    if state.phase == Phase.ATTACK:
        for index in range(len(player.battle_zone)):
            if not can_attack(index, state):
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
