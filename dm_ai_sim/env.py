from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from dm_ai_sim.action_encoder import decode_action, encode_action, legal_action_mask
from dm_ai_sim.actions import Action, ActionType
from dm_ai_sim.card import Card, make_vanilla_deck
from dm_ai_sim.mana import (
    civilization_counts,
    enters_mana_tapped,
    mana_civilizations,
    multicolor_mana_count,
    playable_hand_counts,
    tap_mana_for_card,
)
from dm_ai_sim.rules import legal_actions as compute_legal_actions
from dm_ai_sim.state import Creature, GameState, ManaCard, PendingAttack, Phase, PlayerState


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
        info["spell_cast"] = False
        info["spell_name"] = None
        info["spell_effect"] = None
        info["spell_target_index"] = None
        info["charged_card"] = None
        info["charged_card_civilizations"] = None
        info["charged_card_enters_tapped"] = False
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
            tap_mana_for_card(player, card)
            player.hand.pop(action.card_index)
            player.battle_zone.append(Creature(card=card, summoned_turn=state.turn_number))

        elif action.type == ActionType.CAST_SPELL:
            self._raise_if_pending(action)
            info.update(self._cast_spell(action.hand_index if action.hand_index is not None else action.card_index, action.target_index))

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
            self._advance_turn()

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
        action = decode_action(action_id)
        if action_id not in self.legal_action_ids():
            raise ValueError(f"Illegal action_id: {action_id}")
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
                [creature.card for creature in player.battle_zone],
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
        player.charged_mana_this_turn = False
        for mana_card in player.mana:
            mana_card.tapped = False
        for creature in player.battle_zone:
            creature.tapped = False

        if draw_card and not self._draw_card(player):
            state.winner = state.opponent
            state.done = True
            state.phase = Phase.GAME_OVER

    def _advance_turn(self) -> None:
        state = self._require_state()
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

    def _cast_spell(self, hand_index: int | None, target_index: int | None) -> dict[str, Any]:
        state = self._require_state()
        if hand_index is None:
            raise ValueError("CAST_SPELL requires hand_index.")
        player = state.players[state.current_player]
        opponent = state.players[state.opponent]
        if hand_index < 0 or hand_index >= len(player.hand):
            raise ValueError(f"Invalid spell hand index: {hand_index}")
        card = player.hand[hand_index]
        if card.card_type != "SPELL":
            raise ValueError(f"Card is not a spell: {card.name}")
        effect = card.spell_effect or card.trigger_effect
        if effect is None:
            raise ValueError(f"Spell has no effect: {card.name}")
        if effect == "DESTROY_TARGET" and target_index is None:
            raise ValueError("DESTROY_TARGET requires target_index.")
        if effect != "DESTROY_TARGET" and target_index is not None:
            raise ValueError(f"{effect} does not use target_index.")
        if effect == "DESTROY_TARGET" and (target_index < 0 or target_index >= len(opponent.battle_zone)):
            raise ValueError(f"Invalid spell target index: {target_index}")

        spell_card = player.hand[hand_index]
        tap_mana_for_card(player, spell_card)
        player.hand.pop(hand_index)
        info: dict[str, Any] = {
            "spell_cast": True,
            "spell_name": spell_card.name,
            "spell_effect": effect,
            "spell_target_index": target_index,
        }
        self._set_last_spell(effect, state.current_player)

        if effect == "DRAW_1":
            player.graveyard.append(spell_card)
            self._draw_card(player)
            return info
        if effect == "DESTROY_TARGET":
            assert target_index is not None
            destroyed = opponent.battle_zone.pop(target_index)
            opponent.graveyard.append(destroyed.card)
            player.graveyard.append(spell_card)
            return info
        if effect == "GAIN_SHIELD":
            player.graveyard.append(spell_card)
            if player.deck:
                player.shields.append(player.deck.pop())
            return info
        if effect == "MANA_BOOST":
            player.graveyard.append(spell_card)
            if player.deck:
                player.mana.append(ManaCard(card=player.deck.pop(), tapped=False))
            return info

        player.graveyard.append(spell_card)
        return info

    def _set_last_spell(self, effect: str, player_id: int) -> None:
        state = self._require_state()
        state.last_spell_cast = True
        state.last_spell_effect = effect
        state.last_spell_player = player_id

    def _battle_creatures(self, attacker_index: int, target_index: int) -> None:
        state = self._require_state()
        player = state.players[state.current_player]
        opponent = state.players[state.opponent]
        self._resolve_battle(player, attacker_index, opponent, target_index)
        if not state.done:
            self._resolve_after_attack_triggers(state.current_player, state.opponent, attacker_index, {})

    def _attack_creature(self, attacker_index: int, target_index: int) -> dict[str, Any]:
        state = self._require_state()
        attacker_player = state.current_player
        defender_player = state.opponent
        info: dict[str, Any] = {}
        self._resolve_battle(state.players[attacker_player], attacker_index, state.players[defender_player], target_index)
        if not state.done:
            self._resolve_after_attack_triggers(attacker_player, defender_player, attacker_index, info)
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
            self._resolve_after_attack_triggers(pending.attacker_player, pending.defender_player, pending.attacker_index, info)
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
        defender = state.players[defender_player]
        self._clear_last_trigger()
        self._clear_last_spell()
        info: dict[str, Any] = {
            "shield_broken": False,
            "broken_shield_card": None,
            "trigger_activated": False,
            "trigger_effect": None,
            "attacker_destroyed_by_trigger": False,
        }
        if target_type == "SHIELD":
            if defender.shields:
                broken_card = defender.shields.pop()
                info["shield_broken"] = True
                info["broken_shield_card"] = broken_card.name
                info.update(self._resolve_shield_trigger(broken_card, defender_player, attacker_player, attacker_index))
            if not state.done:
                self._resolve_after_attack_triggers(attacker_player, defender_player, attacker_index, info)
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

    def _resolve_after_attack_triggers(
        self,
        attacker_player: int,
        defender_player: int,
        attacker_index: int | None,
        info: dict[str, Any],
    ) -> None:
        self._set_after_attack_defaults(info)
        state = self._require_state()
        if state.done or attacker_index is None:
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
        info["gachinko_judge"] = True
        if not attacker_state.deck or not defender_state.deck:
            return

        attacker_revealed = attacker_state.deck.pop()
        defender_revealed = defender_state.deck.pop()
        info["gachinko_attacker_card"] = attacker_revealed.name
        info["gachinko_defender_card"] = defender_revealed.name
        info["gachinko_attacker_cost"] = attacker_revealed.cost
        info["gachinko_defender_cost"] = defender_revealed.cost
        attacker_state.deck.insert(0, attacker_revealed)
        defender_state.deck.insert(0, defender_revealed)

        if attacker_revealed.cost <= 0 or defender_revealed.cost <= 0:
            return

        won = attacker_revealed.cost >= defender_revealed.cost
        info["gachinko_won"] = won
        if not won:
            return

        summoned = self._summon_same_name_from_deck(attacker_state, attacker.card.name, state.turn_number)
        if summoned is not None:
            info["same_name_summoned"] = True
            info["same_name_summoned_card"] = summoned.name

    def _summon_same_name_from_deck(self, player: PlayerState, name: str, turn_number: int) -> Card | None:
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

    def _resolve_shield_trigger(
        self,
        card: Card,
        defender_player: int,
        attacker_player: int,
        attacker_index: int | None,
    ) -> dict[str, Any]:
        state = self._require_state()
        defender = state.players[defender_player]
        info: dict[str, Any] = {
            "trigger_activated": False,
            "trigger_effect": None,
            "attacker_destroyed_by_trigger": False,
        }
        if not card.shield_trigger or card.trigger_effect is None:
            defender.hand.append(card)
            return info

        effect = card.trigger_effect
        info["trigger_activated"] = True
        info["trigger_effect"] = effect
        state.last_trigger_activated = True
        state.last_trigger_effect = effect
        state.last_trigger_player = defender_player

        if effect == "DRAW_1":
            defender.graveyard.append(card)
            self._draw_card(defender)
            return info

        if effect == "DESTROY_ATTACKER":
            defender.graveyard.append(card)
            attacker_zone = state.players[attacker_player].battle_zone
            if attacker_index is not None and attacker_index < len(attacker_zone):
                destroyed = attacker_zone.pop(attacker_index)
                state.players[attacker_player].graveyard.append(destroyed.card)
                info["attacker_destroyed_by_trigger"] = True
            return info

        if effect == "SUMMON_SELF" and card.card_type == "CREATURE":
            defender.battle_zone.append(Creature(card=card, summoned_turn=state.turn_number))
            return info

        if effect == "GAIN_SHIELD":
            defender.graveyard.append(card)
            if defender.deck:
                defender.shields.append(defender.deck.pop())
            return info

        defender.hand.append(card)
        info["trigger_activated"] = False
        info["trigger_effect"] = None
        self._clear_last_trigger()
        return info

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
            defending_player.graveyard.append(destroyed_defender.card)
        if attacker_destroyed:
            destroyed_attacker = attacking_player.battle_zone.pop(attacker_index)
            attacking_player.graveyard.append(destroyed_attacker.card)

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
