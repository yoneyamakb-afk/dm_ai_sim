from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from dm_ai_sim.action_encoder import decode_action, encode_action, legal_action_mask
from dm_ai_sim.actions import Action, ActionType
from dm_ai_sim.card import Card, make_vanilla_deck
from dm_ai_sim.rules import legal_actions as compute_legal_actions
from dm_ai_sim.state import Creature, GameState, ManaCard, Phase, PlayerState


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

        if action.type == ActionType.CHARGE_MANA:
            assert action.card_index is not None
            player = state.players[acting_player]
            card = player.hand.pop(action.card_index)
            player.mana.append(ManaCard(card=card))
            player.charged_mana_this_turn = True

        elif action.type == ActionType.SUMMON:
            assert action.card_index is not None
            player = state.players[acting_player]
            card = player.hand.pop(action.card_index)
            self._tap_mana_for_cost(player, card.cost)
            player.battle_zone.append(Creature(card=card, summoned_turn=state.turn_number))

        elif action.type == ActionType.END_MAIN:
            state.phase = Phase.ATTACK

        elif action.type == ActionType.ATTACK_SHIELD:
            assert action.attacker_index is not None
            block_info = self._try_block_attack(action.attacker_index)
            if block_info is not None:
                info.update(block_info)
            else:
                attacker = state.players[acting_player].battle_zone[action.attacker_index]
                attacker.tapped = True
                opponent = state.players[state.opponent]
                if opponent.shields:
                    opponent.hand.append(opponent.shields.pop())

        elif action.type == ActionType.ATTACK_PLAYER:
            assert action.attacker_index is not None
            block_info = self._try_block_attack(action.attacker_index)
            if block_info is not None:
                info.update(block_info)
            else:
                attacker = state.players[acting_player].battle_zone[action.attacker_index]
                attacker.tapped = True
                state.winner = acting_player
                state.done = True
                state.phase = Phase.GAME_OVER

        elif action.type == ActionType.ATTACK_CREATURE:
            assert action.attacker_index is not None
            assert action.target_index is not None
            self._battle_creatures(action.attacker_index, action.target_index)

        elif action.type == ActionType.END_ATTACK:
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

    def _tap_mana_for_cost(self, player: PlayerState, cost: int) -> None:
        tapped = 0
        for mana_card in player.mana:
            if not mana_card.tapped:
                mana_card.tapped = True
                tapped += 1
                if tapped == cost:
                    return
        raise RuntimeError("Not enough untapped mana to pay cost.")

    def _battle_creatures(self, attacker_index: int, target_index: int) -> None:
        state = self._require_state()
        player = state.players[state.current_player]
        opponent = state.players[state.opponent]
        self._resolve_battle(player, attacker_index, opponent, target_index)

    def _try_block_attack(self, attacker_index: int) -> dict[str, Any] | None:
        state = self._require_state()
        player = state.players[state.current_player]
        opponent = state.players[state.opponent]
        blocker_index = self._choose_blocker_index(attacker_index)
        if blocker_index is None:
            return None

        blocker = opponent.battle_zone[blocker_index]
        blocker_name = blocker.card.name
        self._resolve_battle(player, attacker_index, opponent, blocker_index)
        return {
            "blocked": True,
            "blocker_index": blocker_index,
            "blocker_name": blocker_name,
        }

    def _choose_blocker_index(self, attacker_index: int) -> int | None:
        state = self._require_state()
        attacker = state.players[state.current_player].battle_zone[attacker_index]
        blockers = [
            (index, creature)
            for index, creature in enumerate(state.players[state.opponent].battle_zone)
            if creature.card.blocker and not creature.tapped
        ]
        if not blockers:
            return None

        destroy_without_dying = [
            (index, creature)
            for index, creature in blockers
            if creature.card.power > attacker.card.power
        ]
        if destroy_without_dying:
            return min(destroy_without_dying, key=lambda item: item[1].card.power)[0]

        trade = [
            (index, creature)
            for index, creature in blockers
            if creature.card.power == attacker.card.power
        ]
        if trade:
            return trade[0][0]

        return min(blockers, key=lambda item: item[1].card.power)[0]

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
                {"card": self._card_observation(mana_card.card), "tapped": mana_card.tapped}
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
        }

    def _card_observation(self, card: Card) -> dict[str, Any]:
        return {
            "id": card.id,
            "name": card.name,
            "cost": card.cost,
            "power": card.power,
            "civilization": card.civilization,
            "blocker": card.blocker,
        }

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
