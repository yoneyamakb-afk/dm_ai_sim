from __future__ import annotations

from dm_ai_sim.actions import Action, ActionType
from dm_ai_sim.state import GameState, Phase, PlayerState


def untapped_mana_count(player: PlayerState) -> int:
    return sum(1 for mana_card in player.mana if not mana_card.tapped)


def can_attack(creature_index: int, state: GameState) -> bool:
    creature = state.players[state.current_player].battle_zone[creature_index]
    return not creature.tapped and creature.summoned_turn < state.turn_number


def legal_actions(state: GameState) -> list[Action]:
    if state.phase == Phase.GAME_OVER or state.winner is not None:
        return []

    player = state.players[state.current_player]
    opponent = state.players[state.opponent]
    actions: list[Action] = []

    if state.phase == Phase.MAIN:
        if not player.charged_mana_this_turn:
            actions.extend(
                Action(ActionType.CHARGE_MANA, card_index=index)
                for index in range(len(player.hand))
            )

        available_mana = untapped_mana_count(player)
        actions.extend(
            Action(ActionType.SUMMON, card_index=index)
            for index, card in enumerate(player.hand)
            if card.cost <= available_mana
        )
        actions.append(Action(ActionType.END_MAIN))
        return actions

    if state.phase == Phase.ATTACK:
        for index in range(len(player.battle_zone)):
            if not can_attack(index, state):
                continue
            if opponent.shields:
                actions.append(Action(ActionType.ATTACK_SHIELD, attacker_index=index))
            else:
                actions.append(Action(ActionType.ATTACK_PLAYER, attacker_index=index))
        actions.append(Action(ActionType.END_ATTACK))
        return actions

    return actions
