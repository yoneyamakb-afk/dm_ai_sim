from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from dm_ai_sim.action_encoder import decode_action, encode_action, legal_action_mask
from dm_ai_sim.actions import Action, ActionType
from dm_ai_sim.ability_handlers.registry import get_default_ability_registry
from dm_ai_sim.card import Card, make_vanilla_deck
from dm_ai_sim.mana import (
    active_creature_cost_reductions,
    civilization_counts,
    enters_mana_tapped,
    effective_summon_cost,
    mana_payment_plan,
    mana_civilizations,
    multicolor_mana_count,
    playable_hand_counts,
    tap_mana_for_card,
    tap_mana_for_summon,
)
from dm_ai_sim.rules import legal_actions as compute_legal_actions
from dm_ai_sim.shield_breaks import break_shields
from dm_ai_sim.state import CostReductionEffect, Creature, GameState, ManaCard, PendingAttack, Phase, PlayerState


@dataclass(slots=True)
class EnvConfig:
    first_player_draw: bool = False
    intermediate_rewards: bool = False
    include_action_mask: bool = False
    max_turns: int = 200
    seed: int | None = None


class Env:
    def __init__(
        self,
        deck0: list[Card] | None = None,
        deck1: list[Card] | None = None,
        config: EnvConfig | None = None,
    ) -> None:
        self.config = config or EnvConfig()
        self.random = random.Random(self.config.seed)
        self.ability_registry = get_default_ability_registry()
        self.initial_decks = [
            list(deck0) if deck0 is not None else make_vanilla_deck(base_id=0),
            list(deck1) if deck1 is not None else make_vanilla_deck(base_id=1000),
        ]
        self.state: GameState | None = None

    def reset(self) -> dict[str, Any]:
        decks = [list(deck) for deck in self.initial_decks]
        for deck in decks:
            if len(deck) != 40:
                raise ValueError("Each deck must contain exactly 40 cards.")
            self.random.shuffle(deck)

        players = [PlayerState(deck=decks[0]), PlayerState(deck=decks[1])]
        self.state = GameState(players=players)
        for player in players:
            self._move_cards(player.deck, player.hand, 5)
            self._move_cards(player.deck, player.shields, 5)
        self._start_turn(draw_card=self.config.first_player_draw)
        return self.get_observation()

    def step(self, action: Action) -> tuple[dict[str, Any], float, bool, dict[str, Any]]:
        state = self._require_state()
        if action not in self.legal_actions():
            raise ValueError(f"Illegal action: {action}")

        acting_player = state.current_player
        reward = 0.0
        info: dict[str, Any] = {}
        info["blocked"] = False
        info["declined_block"] = False
        info["shield_broken"] = False
        info["broken_shield_card"] = None
        info["trigger_activated"] = False
        info["trigger_effect"] = None
        info["attacker_destroyed_by_trigger"] = False
        info["breaker_count"] = 1
        info["shields_to_break"] = 0
        info["shields_broken_count"] = 0
        info["multi_break"] = False
        info["shield_break_results"] = []
        info["spell_cast"] = False
        info["spell_name"] = None
        info["spell_effect"] = None
        info["spell_target_index"] = None
        info["cost_reduction_created"] = False
        info["cost_reduction_source"] = None
        info["cost_reduction_amount"] = 0
        info["cost_reduction_applies_to"] = None
        info["cost_reduction_used"] = False
        info["cost_reduction_expired"] = False
        info["cost_reduced_by"] = 0
        info["summon_card_name"] = None
        info["original_cost"] = None
        info["effective_cost"] = None
        info["mana_paid"] = 0
        info["summons_enabled_by_reduction"] = False
        info["charged_card"] = None
        info["charged_card_civilizations"] = None
        info["charged_card_enters_tapped"] = False
        info["g_strike_activated"] = False
        info["g_strike_card_name"] = None
        info["g_strike_target_index"] = None
        info["g_strike_target_name"] = None
        info["g_strike_prevented_attack"] = False
        info["g_strike_source_zone"] = None
        info["revolution_change"] = False
        info["revolution_change_card_name"] = None
        info["revolution_change_returned_card_name"] = None
        info["revolution_change_from_hand_index"] = None
        info["revolution_change_attacker_index"] = None
        info["invasion"] = False
        info["invasion_card_name"] = None
        info["invasion_source_card_name"] = None
        info["invasion_from_hand_index"] = None
        info["invasion_attacker_index"] = None
        self._set_after_attack_defaults(info)

        if action.type == ActionType.CHARGE_MANA:
            self._raise_if_pending(action)
            assert action.card_index is not None
            player = state.players[acting_player]
            card = player.hand.pop(action.card_index)
            tapped = enters_mana_tapped(card)
            player.mana.append(ManaCard(card=card, tapped=tapped))
            player.charged_mana_this_turn = True
            info["charged_card"] = card.name
            info["charged_card_civilizations"] = list(card.civilizations or ())
            info["charged_card_enters_tapped"] = tapped

        elif action.type == ActionType.SUMMON:
            self._raise_if_pending(action)
            assert action.card_index is not None
            player = state.players[acting_player]
            card = player.hand[action.card_index]
            summon_card = card.side_as_card(action.side) if action.side == "top" else card
            original_payment_plan = mana_payment_plan(player, summon_card)
            summon_effective_cost = effective_summon_cost(player, summon_card)
            reduction_effects = active_creature_cost_reductions(player)
            paid_indices = tap_mana_for_summon(player, summon_card)
            original = player.hand.pop(action.card_index)
            player.battle_zone.append(
                Creature(card=summon_card, summoned_turn=state.turn_number, original_card=original if original.is_twinpact else None)
            )
            info["side_used"] = action.side
            info["summoned_card"] = summon_card.name
            info["summon_card_name"] = summon_card.name
            info["original_cost"] = summon_card.cost
            info["effective_cost"] = summon_effective_cost
            info["mana_paid"] = len(paid_indices)
            if reduction_effects:
                info["cost_reduction_used"] = True
                info["cost_reduction_source"] = ", ".join(effect.source_card_name for effect in reduction_effects)
                info["cost_reduction_amount"] = sum(effect.amount for effect in reduction_effects)
                info["cost_reduction_applies_to"] = "CREATURE"
                info["cost_reduced_by"] = summon_card.cost - summon_effective_cost
                info["summons_enabled_by_reduction"] = original_payment_plan is None
                self._consume_cost_reductions(player, reduction_effects)

        elif action.type == ActionType.CAST_SPELL:
            self._raise_if_pending(action)
            info.update(self._cast_spell(action.hand_index if action.hand_index is not None else action.card_index, action.target_index, action.side))

        elif action.type == ActionType.REVOLUTION_CHANGE:
            self._raise_if_pending(action)
            info.update(self._resolve_revolution_change(action.hand_index if action.hand_index is not None else action.card_index, action.attacker_index))

        elif action.type == ActionType.INVASION:
            self._raise_if_pending(action)
            info.update(self._resolve_invasion(action.hand_index if action.hand_index is not None else action.card_index, action.attacker_index))

        elif action.type == ActionType.END_MAIN:
            self._raise_if_pending(action)
            state.phase = Phase.ATTACK

        elif action.type == ActionType.ATTACK_SHIELD:
            self._raise_if_pending(action)
            assert action.attacker_index is not None
            info.update(self._declare_attack(action.attacker_index, "SHIELD"))

        elif action.type == ActionType.ATTACK_PLAYER:
            self._raise_if_pending(action)
            assert action.attacker_index is not None
            info.update(self._declare_attack(action.attacker_index, "PLAYER"))

        elif action.type == ActionType.ATTACK_CREATURE:
            self._raise_if_pending(action)
            assert action.attacker_index is not None
            assert action.target_index is not None
            info.update(self._attack_creature(action.attacker_index, action.target_index))

        elif action.type == ActionType.BLOCK:
            assert action.blocker_index is not None
            info.update(self._resolve_block(action.blocker_index))

        elif action.type == ActionType.DECLINE_BLOCK:
            info.update(self._resolve_decline_block())

        elif action.type == ActionType.END_ATTACK:
            self._raise_if_pending(action)
            self._advance_turn(info)

        done = state.done
        if done:
            if state.winner is not None:
                reward = 1.0 if state.winner == acting_player else -1.0
            info["winner"] = state.winner
        elif self.config.intermediate_rewards:
            reward = self._intermediate_reward(action)

        info.setdefault("winner", state.winner)
        info["draw"] = done and state.winner is None
        info["turn_number"] = state.turn_number
        return self.get_observation(), reward, done, info

    def legal_actions(self) -> list[Action]:
        return compute_legal_actions(self._require_state())

    def legal_action_ids(self) -> list[int]:
        action_ids: list[int] = []
        for action in self.legal_actions():
            try:
                action_ids.append(encode_action(action))
            except ValueError:
                continue
        return action_ids

    def step_action_id(self, action_id: int) -> tuple[dict[str, Any], float, bool, dict[str, Any]]:
        if action_id not in self.legal_action_ids():
            raise ValueError(f"Illegal action_id: {action_id}")
        decoded = decode_action(action_id)
        action = next((candidate for candidate in self.legal_actions() if encode_action(candidate) == action_id), decoded)
        return self.step(action)

    def get_observation(
        self,
        player_id: int | None = None,
        include_action_mask: bool | None = None,
    ) -> dict[str, Any]:
        state = self._require_state()
        viewer = state.current_player if player_id is None else player_id
        opponent = 1 - viewer
        observation = {
            "current_player": state.current_player,
            "viewer": viewer,
            "phase": state.phase.value,
            "turn_number": state.turn_number,
            "winner": state.winner,
            "done": state.done,
            "pending_attack": self._pending_attack_observation(),
            "last_trigger": {
                "activated": state.last_trigger_activated,
                "effect": state.last_trigger_effect,
                "player": state.last_trigger_player,
            },
            "last_spell": {
                "cast": state.last_spell_cast,
                "effect": state.last_spell_effect,
                "player": state.last_spell_player,
            },
            "self": self._player_observation(state.players[viewer], reveal_hand=True),
            "opponent": self._player_observation(state.players[opponent], reveal_hand=False),
            "legal_actions": self.legal_actions() if viewer == state.current_player else [],
        }
        should_include_mask = self.config.include_action_mask if include_action_mask is None else include_action_mask
        if should_include_mask:
            observation["action_mask"] = (
                legal_action_mask(self) if viewer == state.current_player else []
            )
        return observation

    def validate_invariants(self) -> list[str]:
        state = self._require_state()
        errors: list[str] = []

        for player_id, player in enumerate(state.players):
            zones = [
                player.deck,
                player.hand,
                [mana.card for mana in player.mana],
                [card for creature in player.battle_zone for card in _creature_zone_cards(creature)],
                player.graveyard,
                player.shields,
            ]
            zone_cards = [card for zone in zones for card in zone]
            card_ids = [card.id for card in zone_cards]

            if len(zone_cards) != 40:
                errors.append(f"player {player_id} card count is {len(zone_cards)}, expected 40")
            if len(card_ids) != len(set(card_ids)):
                errors.append(f"player {player_id} has duplicated card ids across zones")
            if len(player.shields) < 0:
                errors.append(f"player {player_id} has negative shield count")
            if len(player.hand) < 0:
                errors.append(f"player {player_id} has negative hand count")

        if state.winner is not None and not state.done:
            errors.append("winner is set but done is false")
        if state.done and state.phase != Phase.GAME_OVER:
            errors.append("done is true but phase is not GAME_OVER")
        return errors

    def assert_invariants(self) -> None:
        errors = self.validate_invariants()
        if errors:
            raise AssertionError("; ".join(errors))

    def _start_turn(self, draw_card: bool = True) -> None:
        state = self._require_state()
        player = state.players[state.current_player]
        state.phase = Phase.MAIN
        state.pending_attack = None
        state.revolution_changed_this_turn = False
        state.invaded_this_turn = False
        player.charged_mana_this_turn = False
        for mana_card in player.mana:
            mana_card.tapped = False
        for creature in player.battle_zone:
            creature.tapped = False
        for each_player in state.players:
            for creature in each_player.battle_zone:
                creature.cannot_attack_this_turn = False

        if draw_card and not self._draw_card(player):
            state.winner = state.opponent
            state.done = True
            state.phase = Phase.GAME_OVER

    def _advance_turn(self, info: dict[str, Any] | None = None) -> None:
        state = self._require_state()
        expired = self._expire_cost_reductions(state.players[state.current_player])
        if info is not None and expired:
            info["cost_reduction_expired"] = True
            info["cost_reduction_source"] = ", ".join(effect.source_card_name for effect in expired)
            info["cost_reduction_amount"] = sum(effect.amount for effect in expired)
            info["cost_reduction_applies_to"] = "CREATURE"
        if state.current_player == 1:
            state.turn_number += 1
            if state.turn_number > self.config.max_turns:
                state.done = True
                state.winner = None
                state.phase = Phase.GAME_OVER
                return
        state.current_player = state.opponent
        state.first_turn = False
        self._start_turn(draw_card=True)

    def _cast_spell(self, hand_index: int | None, target_index: int | None, side: str | None = None) -> dict[str, Any]:
        state = self._require_state()
        if hand_index is None:
            raise ValueError("CAST_SPELL requires hand_index.")
        player = state.players[state.current_player]
        opponent = state.players[state.opponent]
        if hand_index < 0 or hand_index >= len(player.hand):
            raise ValueError(f"Invalid spell hand index: {hand_index}")
        card = player.hand[hand_index]
        spell_card = card.side_as_card(side) if side == "bottom" else card
        if spell_card.card_type != "SPELL":
            raise ValueError(f"Card is not a spell: {card.name}")
        effect = spell_card.spell_effect or spell_card.trigger_effect
        if effect is None and "NEXT_CREATURE_COST_REDUCTION" in spell_card.ability_tags:
            effect = "NEXT_CREATURE_COST_REDUCTION"
        if effect is None:
            raise ValueError(f"Spell has no effect: {card.name}")
        if effect == "DESTROY_TARGET" and target_index is None:
            raise ValueError("DESTROY_TARGET requires target_index.")
        if effect != "DESTROY_TARGET" and target_index is not None:
            raise ValueError(f"{effect} does not use target_index.")
        if effect == "DESTROY_TARGET" and (target_index < 0 or target_index >= len(opponent.battle_zone)):
            raise ValueError(f"Invalid spell target index: {target_index}")

        tap_mana_for_card(player, spell_card)
        original_card = player.hand.pop(hand_index)
        info: dict[str, Any] = {
            "spell_cast": True,
            "spell_name": spell_card.name,
            "spell_effect": effect,
            "spell_target_index": target_index,
            "side_used": side,
            "cost_reduction_created": False,
            "cost_reduction_source": None,
            "cost_reduction_amount": 0,
            "cost_reduction_applies_to": None,
        }
        self._set_last_spell(effect, state.current_player)

        if effect == "NEXT_CREATURE_COST_REDUCTION" or "NEXT_CREATURE_COST_REDUCTION" in spell_card.ability_tags:
            player.graveyard.append(original_card)
            effect_amount = 3
            player.pending_cost_reductions.append(
                CostReductionEffect(
                    source_card_name=spell_card.name,
                    applies_to="CREATURE",
                    amount=effect_amount,
                    expires="NEXT_CREATURE_SUMMON",
                )
            )
            info["cost_reduction_created"] = True
            info["cost_reduction_source"] = spell_card.name
            info["cost_reduction_amount"] = effect_amount
            info["cost_reduction_applies_to"] = "CREATURE"
            return info

        if effect == "DRAW_1":
            player.graveyard.append(original_card)
            self._draw_card(player)
            return info
        if effect == "DESTROY_TARGET":
            assert target_index is not None
            destroyed = opponent.battle_zone.pop(target_index)
            opponent.graveyard.extend(_creature_zone_cards(destroyed))
            player.graveyard.append(original_card)
            return info
        if effect == "GAIN_SHIELD":
            player.graveyard.append(original_card)
            if player.deck:
                player.shields.append(player.deck.pop())
            return info
        if effect == "MANA_BOOST":
            player.graveyard.append(original_card)
            if player.deck:
                player.mana.append(ManaCard(card=player.deck.pop(), tapped=False))
            return info

        player.graveyard.append(original_card)
        return info

    def _set_last_spell(self, effect: str, player_id: int) -> None:
        state = self._require_state()
        state.last_spell_cast = True
        state.last_spell_effect = effect
        state.last_spell_player = player_id

    def _resolve_revolution_change(self, hand_index: int | None, attacker_index: int | None) -> dict[str, Any]:
        state = self._require_state()
        if state.phase != Phase.ATTACK:
            raise ValueError("REVOLUTION_CHANGE is only legal during attack phase.")
        if hand_index is None or attacker_index is None:
            raise ValueError("REVOLUTION_CHANGE requires hand_index and attacker_index.")
        player = state.players[state.current_player]
        if hand_index < 0 or hand_index >= len(player.hand):
            raise ValueError(f"Invalid revolution change hand index: {hand_index}")
        if attacker_index < 0 or attacker_index >= len(player.battle_zone):
            raise ValueError(f"Invalid revolution change attacker index: {attacker_index}")
        change_card = player.hand[hand_index]
        if change_card.card_type != "CREATURE" or "REVOLUTION_CHANGE" not in change_card.ability_tags:
            raise ValueError(f"Card cannot revolution change: {change_card.name}")
        if not compute_legal_actions(state) or Action(ActionType.REVOLUTION_CHANGE, hand_index=hand_index, attacker_index=attacker_index) not in compute_legal_actions(state):
            raise ValueError("REVOLUTION_CHANGE target is not legal.")

        returned = player.battle_zone.pop(attacker_index)
        returned_cards = _creature_zone_cards(returned)
        player.hand.extend(returned_cards)
        change_card = player.hand.pop(hand_index)
        player.battle_zone.append(Creature(card=change_card, tapped=False, summoned_turn=state.turn_number))
        state.revolution_changed_this_turn = True
        return {
            "revolution_change": True,
            "revolution_change_card_name": change_card.name,
            "revolution_change_returned_card_name": returned_cards[0].name,
            "revolution_change_from_hand_index": hand_index,
            "revolution_change_attacker_index": attacker_index,
        }

    def _resolve_invasion(self, hand_index: int | None, attacker_index: int | None) -> dict[str, Any]:
        state = self._require_state()
        if state.phase != Phase.ATTACK:
            raise ValueError("INVASION is only legal during attack phase.")
        if hand_index is None or attacker_index is None:
            raise ValueError("INVASION requires hand_index and attacker_index.")
        player = state.players[state.current_player]
        if hand_index < 0 or hand_index >= len(player.hand):
            raise ValueError(f"Invalid invasion hand index: {hand_index}")
        if attacker_index < 0 or attacker_index >= len(player.battle_zone):
            raise ValueError(f"Invalid invasion attacker index: {attacker_index}")
        invasion_card = player.hand[hand_index]
        if invasion_card.card_type != "CREATURE" or "INVASION" not in invasion_card.ability_tags:
            raise ValueError(f"Card cannot invade: {invasion_card.name}")
        if Action(ActionType.INVASION, hand_index=hand_index, attacker_index=attacker_index) not in compute_legal_actions(state):
            raise ValueError("INVASION target is not legal.")

        source = player.battle_zone.pop(attacker_index)
        source_cards = _creature_zone_cards(source)
        invasion_card = player.hand.pop(hand_index)
        player.battle_zone.append(
            Creature(
                card=invasion_card,
                tapped=False,
                summoned_turn=state.turn_number,
                evolution_sources=source_cards,
            )
        )
        state.invaded_this_turn = True
        return {
            "invasion": True,
            "invasion_card_name": invasion_card.name,
            "invasion_source_card_name": source_cards[0].name,
            "invasion_from_hand_index": hand_index,
            "invasion_attacker_index": attacker_index,
        }

    def _battle_creatures(self, attacker_index: int, target_index: int) -> None:
        state = self._require_state()
        player = state.players[state.current_player]
        opponent = state.players[state.opponent]
        attacker = player.battle_zone[attacker_index]
        self._resolve_battle(player, attacker_index, opponent, target_index)
        if not state.done:
            self._resolve_after_attack_triggers(state.current_player, state.opponent, attacker, {})

    def _attack_creature(self, attacker_index: int, target_index: int) -> dict[str, Any]:
        state = self._require_state()
        attacker_player = state.current_player
        defender_player = state.opponent
        info: dict[str, Any] = {}
        attacker = state.players[attacker_player].battle_zone[attacker_index]
        self._resolve_battle(state.players[attacker_player], attacker_index, state.players[defender_player], target_index)
        if not state.done:
            self._resolve_after_attack_triggers(attacker_player, defender_player, attacker, info)
        return info

    def _declare_attack(self, attacker_index: int, target_type: str) -> dict[str, Any]:
        state = self._require_state()
        player = state.players[state.current_player]
        opponent = state.players[state.opponent]
        attacker = player.battle_zone[attacker_index]
        attacker.tapped = True
        info: dict[str, Any] = {"pending_attack_created": False}
        if self._blocker_indices(opponent):
            state.pending_attack = PendingAttack(
                attacker_player=state.current_player,
                defender_player=state.opponent,
                attacker_index=attacker_index,
                target_type=target_type,
                target_index=None,
                original_phase=state.phase,
                context_id=state.next_attack_context_id,
            )
            state.next_attack_context_id += 1
            state.current_player = state.opponent
            state.phase = Phase.ATTACK
            info["pending_attack_created"] = True
            return info

        info.update(self._resolve_unblocked_attack(state.current_player, state.opponent, target_type, attacker_index))
        return info

    def _resolve_block(self, blocker_index: int) -> dict[str, Any]:
        state = self._require_state()
        pending = state.pending_attack
        if pending is None:
            raise ValueError("BLOCK requires a pending attack.")
        if state.current_player != pending.defender_player:
            raise ValueError("Only the defender can block.")
        defender = state.players[pending.defender_player]
        if blocker_index >= len(defender.battle_zone):
            raise ValueError(f"Invalid blocker index: {blocker_index}")
        blocker = defender.battle_zone[blocker_index]
        if not blocker.card.blocker or blocker.tapped:
            raise ValueError(f"Creature cannot block: {blocker_index}")

        blocker_name = blocker.card.name
        blocker_power = blocker.card.power
        attacker = state.players[pending.attacker_player].battle_zone[pending.attacker_index]
        attacker_power = attacker.card.power
        self._clear_last_trigger()
        self._resolve_battle(
            state.players[pending.attacker_player],
            pending.attacker_index,
            defender,
            blocker_index,
        )
        info: dict[str, Any] = {
            "blocked": True,
            "blocker_index": blocker_index,
            "blocker_name": blocker_name,
            "blocker_power": blocker_power,
            "attacker_power": attacker_power,
        }
        if not state.done:
            self._resolve_after_attack_triggers(pending.attacker_player, pending.defender_player, attacker, info)
        self._clear_pending_attack()
        return info

    def _resolve_decline_block(self) -> dict[str, Any]:
        state = self._require_state()
        pending = state.pending_attack
        if pending is None:
            raise ValueError("DECLINE_BLOCK requires a pending attack.")
        info = self._resolve_unblocked_attack(
            pending.attacker_player,
            pending.defender_player,
            pending.target_type,
            pending.attacker_index,
        )
        self._clear_pending_attack()
        info["declined_block"] = True
        return info

    def _resolve_unblocked_attack(
        self,
        attacker_player: int,
        defender_player: int,
        target_type: str,
        attacker_index: int | None,
    ) -> dict[str, Any]:
        state = self._require_state()
        self._clear_last_trigger()
        self._clear_last_spell()
        info: dict[str, Any] = {
            "shield_broken": False,
            "broken_shield_card": None,
            "trigger_activated": False,
            "trigger_effect": None,
            "attacker_destroyed_by_trigger": False,
            "breaker_count": 1,
            "shields_to_break": 0,
            "shields_broken_count": 0,
            "multi_break": False,
            "shield_break_results": [],
        }
        if target_type == "SHIELD":
            attacker = self._creature_by_index(attacker_player, attacker_index)
            breaker_count = self._attacker_breaker_count(attacker)
            defender = state.players[defender_player]
            shields_to_break = min(breaker_count, len(defender.shields))
            results = break_shields(self, attacker_player, defender_player, shields_to_break, attacker, info)
            info["breaker_count"] = breaker_count
            info["shields_to_break"] = shields_to_break
            info["shields_broken_count"] = len(results)
            info["multi_break"] = len(results) > 1
            if not state.done:
                self._resolve_after_attack_triggers(attacker_player, defender_player, attacker, info)
            return info
        if target_type == "PLAYER":
            state.winner = attacker_player
            state.done = True
            state.phase = Phase.GAME_OVER
            return info
        raise ValueError(f"Unsupported pending attack target type: {target_type}")

    def _set_after_attack_defaults(self, info: dict[str, Any]) -> None:
        info["after_attack_trigger_activated"] = False
        info["gachinko_judge"] = False
        info["gachinko_attacker_card"] = None
        info["gachinko_defender_card"] = None
        info["gachinko_attacker_cost"] = None
        info["gachinko_defender_cost"] = None
        info["gachinko_won"] = False
        info["same_name_summoned"] = False
        info["same_name_summoned_card"] = None
        info["gachinko_revealed_twinpact"] = False
        info["gachinko_revealed_card_name"] = None
        info["gachinko_judge_cost_source"] = None
        info["gachinko_prin_ruling_applicable"] = False

    def _resolve_after_attack_triggers(
        self,
        attacker_player: int,
        defender_player: int,
        attacker_instance: int | Creature | None,
        info: dict[str, Any],
    ) -> None:
        self._set_after_attack_defaults(info)
        state = self._require_state()
        if state.done:
            return
        attacker_index = self._creature_index(attacker_player, attacker_instance)
        if attacker_index is None:
            return
        attacking_zone = state.players[attacker_player].battle_zone
        if attacker_index < 0 or attacker_index >= len(attacking_zone):
            return
        attacker = attacking_zone[attacker_index]
        if not _has_hachiko_after_attack_trigger(attacker.card):
            return

        attacker_state = state.players[attacker_player]
        defender_state = state.players[defender_player]
        info["after_attack_trigger_activated"] = True
        if not self._resolve_gachinko_judge(attacker_player, defender_player, info):
            return

        summoned = self._resolve_hachiko_same_name_search(attacker_state, attacker.card.name, state.turn_number)
        if summoned is not None:
            info["same_name_summoned"] = True
            info["same_name_summoned_card"] = summoned.name

    def _resolve_gachinko_judge(self, attacker_player: int, defender_player: int, info: dict[str, Any]) -> bool:
        state = self._require_state()
        attacker_state = state.players[attacker_player]
        defender_state = state.players[defender_player]
        info["gachinko_judge"] = True
        if not attacker_state.deck or not defender_state.deck:
            return False

        attacker_revealed = attacker_state.deck.pop()
        defender_revealed = defender_state.deck.pop()
        attacker_cost, attacker_source = self._get_gachinko_judge_cost(attacker_revealed)
        defender_cost, defender_source = self._get_gachinko_judge_cost(defender_revealed)
        info["gachinko_attacker_card"] = attacker_revealed.name
        info["gachinko_defender_card"] = defender_revealed.name
        info["gachinko_attacker_cost"] = attacker_cost
        info["gachinko_defender_cost"] = defender_cost
        self._record_gachinko_revealed_card(attacker_revealed, attacker_source, info)
        self._record_gachinko_revealed_card(defender_revealed, defender_source, info)
        attacker_state.deck.insert(0, attacker_revealed)
        defender_state.deck.insert(0, defender_revealed)

        if attacker_cost is None or defender_cost is None:
            return False
        won = attacker_cost >= defender_cost
        info["gachinko_won"] = won
        return won

    def _get_gachinko_judge_cost(self, card: Card) -> tuple[int | None, str]:
        if self._is_prin_twinpact(card) and card.bottom_side is not None:
            return card.bottom_side.cost, "bottom_spell_cost"
        if card.is_twinpact:
            costs = [
                (side.cost, "top_creature_cost" if name == "top" else "bottom_spell_cost")
                for name, side in (("top", card.top_side), ("bottom", card.bottom_side))
                if side is not None and side.cost is not None
            ]
            if costs:
                return max(costs, key=lambda item: item[0] or 0)
            return None, "unknown_twinpact_cost"
        return card.cost if card.cost > 0 else None, "card_cost"

    def _record_gachinko_revealed_card(self, card: Card, source: str, info: dict[str, Any]) -> None:
        if not card.is_twinpact:
            return
        info["gachinko_revealed_twinpact"] = True
        info["gachinko_revealed_card_name"] = card.name
        info["gachinko_judge_cost_source"] = source
        if self._is_prin_twinpact(card):
            info["gachinko_prin_ruling_applicable"] = True

    def _is_prin_twinpact(self, card: Card) -> bool:
        return card.name == "綺羅王女プリン / ハンター☆エイリアン仲良しビーム"

    def _resolve_hachiko_same_name_search(self, player: PlayerState, name: str, turn_number: int) -> Card | None:
        for index in range(len(player.deck) - 1, -1, -1):
            card = player.deck[index]
            if card.name != name or card.card_type != "CREATURE":
                continue
            summoned = player.deck.pop(index)
            player.battle_zone.append(Creature(card=summoned, tapped=False, summoned_turn=turn_number))
            self.random.shuffle(player.deck)
            return summoned
        self.random.shuffle(player.deck)
        return None

    def _resolve_g_strike(self, card: Card, defender_player: int, attacker_player: int) -> dict[str, Any]:
        info: dict[str, Any] = {
            "g_strike_activated": True,
            "g_strike_card_name": card.name,
            "g_strike_target_index": None,
            "g_strike_target_name": None,
            "g_strike_prevented_attack": False,
            "g_strike_source_zone": "shield",
        }
        handler = self.ability_registry.get_handler("G_STRIKE")
        if handler is not None and hasattr(handler, "apply_g_strike"):
            return handler.apply_g_strike(self, card, defender_player, attacker_player, info)
        return info

    def _select_g_strike_target(self, attacker_player: int) -> int | None:
        handler = self.ability_registry.get_handler("G_STRIKE")
        if handler is not None and hasattr(handler, "choose_target"):
            return handler.choose_target(self, self._require_state().opponent, attacker_player)
        return None

    def _clear_last_trigger(self) -> None:
        state = self._require_state()
        state.last_trigger_activated = False
        state.last_trigger_effect = None
        state.last_trigger_player = None

    def _clear_last_spell(self) -> None:
        state = self._require_state()
        state.last_spell_cast = False
        state.last_spell_effect = None
        state.last_spell_player = None

    def _clear_pending_attack(self) -> None:
        state = self._require_state()
        pending = state.pending_attack
        if pending is None:
            return
        state.current_player = pending.attacker_player
        if not state.done:
            state.phase = pending.original_phase
        state.pending_attack = None

    def _blocker_indices(self, player: PlayerState) -> list[int]:
        return [
            index
            for index, creature in enumerate(player.battle_zone)
            if creature.card.blocker and not creature.tapped
        ]

    def _creature_by_index(self, player_id: int, creature_index: int | None) -> Creature | None:
        if creature_index is None:
            return None
        battle_zone = self._require_state().players[player_id].battle_zone
        if creature_index < 0 or creature_index >= len(battle_zone):
            return None
        return battle_zone[creature_index]

    def _creature_index(self, player_id: int, creature_instance: int | Creature | None) -> int | None:
        if creature_instance is None:
            return None
        if isinstance(creature_instance, int):
            return creature_instance
        for index, creature in enumerate(self._require_state().players[player_id].battle_zone):
            if creature is creature_instance:
                return index
        return None

    def _attacker_breaker_count(self, attacker: Creature | None) -> int:
        if attacker is None:
            return 1
        return max(1, int(attacker.card.breaker_count))

    def _consume_cost_reductions(self, player: PlayerState, effects: list[CostReductionEffect]) -> None:
        effect_ids = {id(effect) for effect in effects}
        for effect in effects:
            effect.used = True
        player.pending_cost_reductions = [
            effect for effect in player.pending_cost_reductions if id(effect) not in effect_ids
        ]

    def _expire_cost_reductions(self, player: PlayerState) -> list[CostReductionEffect]:
        expired = [effect for effect in player.pending_cost_reductions if not effect.used]
        if expired:
            player.pending_cost_reductions = [
                effect for effect in player.pending_cost_reductions if effect.used
            ]
        return expired

    def _raise_if_pending(self, action: Action) -> None:
        if self._require_state().pending_attack is not None:
            raise ValueError(f"Only BLOCK or DECLINE_BLOCK are legal during pending attack: {action}")

    def _resolve_battle(
        self,
        attacking_player: PlayerState,
        attacker_index: int,
        defending_player: PlayerState,
        defender_index: int,
    ) -> None:
        attacker = attacking_player.battle_zone[attacker_index]
        defender = defending_player.battle_zone[defender_index]

        attacker.tapped = True
        attacker_destroyed = defender.card.power >= attacker.card.power
        defender_destroyed = attacker.card.power >= defender.card.power

        if defender_destroyed:
            destroyed_defender = defending_player.battle_zone.pop(defender_index)
            defending_player.graveyard.extend(_creature_zone_cards(destroyed_defender))
        if attacker_destroyed:
            destroyed_attacker = attacking_player.battle_zone.pop(attacker_index)
            attacking_player.graveyard.extend(_creature_zone_cards(destroyed_attacker))

    def _pending_attack_observation(self) -> dict[str, Any] | None:
        state = self._require_state()
        pending = state.pending_attack
        if pending is None:
            return None
        attacker = state.players[pending.attacker_player].battle_zone[pending.attacker_index]
        defender = state.players[pending.defender_player]
        blockers = [defender.battle_zone[index] for index in self._blocker_indices(defender)]
        return {
            "attacker_player": pending.attacker_player,
            "defender_player": pending.defender_player,
            "attacker_index": pending.attacker_index,
            "attacker_power": attacker.card.power,
            "target_type": pending.target_type,
            "target_index": pending.target_index,
            "context_id": pending.context_id,
            "blocker_count": len(blockers),
            "blocker_max_power": max((creature.card.power for creature in blockers), default=0),
        }

    def _draw_card(self, player: PlayerState) -> bool:
        if not player.deck:
            return False
        player.hand.append(player.deck.pop())
        return True

    def _move_cards(self, source: list[Card], target: list[Card], count: int) -> None:
        for _ in range(count):
            target.append(source.pop())

    def _player_observation(self, player: PlayerState, reveal_hand: bool) -> dict[str, Any]:
        hand = [self._card_observation(card) for card in player.hand] if reveal_hand else None
        return {
            "deck_count": len(player.deck),
            "hand": hand,
            "hand_count": len(player.hand),
            "shield_count": len(player.shields),
            "mana": [
                {
                    "card": self._card_observation(mana_card.card),
                    "tapped": mana_card.tapped,
                    "civilizations": list(mana_civilizations(mana_card)),
                }
                for mana_card in player.mana
            ],
            "battle_zone": [
                {
                    "card": self._card_observation(creature.card),
                    "tapped": creature.tapped,
                    "summoned_turn": creature.summoned_turn,
                    "cannot_attack_this_turn": creature.cannot_attack_this_turn,
                    "evolution_source_count": len(creature.evolution_sources),
                    "evolution_sources": [self._card_observation(card) for card in creature.evolution_sources],
                }
                for creature in player.battle_zone
            ],
            "graveyard": [self._card_observation(card) for card in player.graveyard],
            "charged_mana_this_turn": player.charged_mana_this_turn,
            "visible_trigger_count": self._visible_trigger_count(player),
            "spell_count": sum(1 for card in player.hand if card.card_type == "SPELL") if reveal_hand else None,
            "graveyard_spell_count": sum(1 for card in player.graveyard if card.card_type == "SPELL"),
            "civilization_counts": civilization_counts(player.mana),
            "untapped_civilization_counts": civilization_counts(player.mana, untapped_only=True),
            "multicolor_mana_count": multicolor_mana_count(player.mana),
            "pending_cost_reductions": [
                {
                    "source_card_name": effect.source_card_name,
                    "applies_to": effect.applies_to,
                    "amount": effect.amount,
                    "expires": effect.expires,
                    "used": effect.used,
                }
                for effect in player.pending_cost_reductions
            ],
            "next_creature_cost_reduction": sum(
                effect.amount
                for effect in player.pending_cost_reductions
                if not effect.used and effect.applies_to == "CREATURE"
            ),
            "playable_hand_count": playable_hand_counts(player)["playable"] if reveal_hand else None,
            "unplayable_due_to_civilization_count": (
                playable_hand_counts(player)["civilization_shortfall"] if reveal_hand else None
            ),
            "unplayable_due_to_cost_count": playable_hand_counts(player)["cost_shortfall"] if reveal_hand else None,
        }

    def _card_observation(self, card: Card) -> dict[str, Any]:
        return {
            "id": card.id,
            "name": card.name,
            "cost": card.cost,
            "power": card.power,
            "civilization": card.civilization,
            "civilizations": list(card.civilizations or (card.civilization,)),
            "blocker": card.blocker,
            "shield_trigger": card.shield_trigger,
            "card_type": card.card_type,
            "trigger_effect": card.trigger_effect,
            "spell_effect": card.spell_effect,
            "ability_tags": list(card.ability_tags),
            "breaker_count": card.breaker_count,
            "is_twinpact": card.is_twinpact,
            "top_side": self._side_observation(card.top_side),
            "bottom_side": self._side_observation(card.bottom_side),
        }

    def _side_observation(self, side) -> dict[str, Any] | None:
        if side is None:
            return None
        return {
            "name": side.name,
            "cost": side.cost,
            "civilizations": list(side.civilizations),
            "card_type": side.card_type,
            "power": side.power,
            "spell_effect": side.spell_effect,
            "trigger_effect": side.trigger_effect,
            "shield_trigger": side.shield_trigger,
            "ability_tags": list(side.ability_tags),
        }

    def _visible_trigger_count(self, player: PlayerState) -> int:
        return sum(1 for card in player.graveyard if card.shield_trigger) + sum(
            1 for creature in player.battle_zone if creature.card.shield_trigger
        )

    def _intermediate_reward(self, action: Action) -> float:
        if action.type == ActionType.ATTACK_SHIELD:
            return 0.01
        if action.type == ActionType.SUMMON:
            return 0.001
        return 0.0

    def _require_state(self) -> GameState:
        if self.state is None:
            raise RuntimeError("Call reset() before using the environment.")
        return self.state


def _has_hachiko_after_attack_trigger(card: Card) -> bool:
    tags = set(card.ability_tags)
    return (
        card.name == "特攻の忠剣ハチ公"
        or {"GACHINKO_JUDGE", "SEARCH_SAME_NAME", "PUT_FROM_DECK_TO_BATTLE_ZONE"}.issubset(tags)
    )


def _creature_zone_card(creature: Creature) -> Card:
    return _creature_zone_cards(creature)[0]


def _creature_zone_cards(creature: Creature) -> list[Card]:
    return [creature.original_card or creature.card] + list(creature.evolution_sources)
