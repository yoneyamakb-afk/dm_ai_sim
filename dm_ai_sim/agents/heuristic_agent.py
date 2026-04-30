from __future__ import annotations

from collections import Counter

from dm_ai_sim.actions import Action, ActionType


NON_COLORLESS = ("LIGHT", "WATER", "DARKNESS", "FIRE", "NATURE")


class HeuristicAgent:
    def act(self, legal_actions: list[Action], observation: dict | None = None) -> Action:
        if not legal_actions:
            raise ValueError("No legal actions available.")

        if any(action.type in {ActionType.BLOCK, ActionType.DECLINE_BLOCK} for action in legal_actions):
            return self._block_or_decline(legal_actions, observation)

        for action_type in (
            ActionType.INVASION,
            ActionType.REVOLUTION_CHANGE,
            ActionType.ATTACK_CREATURE,
            ActionType.ATTACK_PLAYER,
            ActionType.ATTACK_SHIELD,
            ActionType.CAST_SPELL,
            ActionType.SUMMON,
            ActionType.CHARGE_MANA,
            ActionType.END_MAIN,
            ActionType.END_ATTACK,
        ):
            candidates = [action for action in legal_actions if action.type == action_type]
            if not candidates:
                continue
            if action_type == ActionType.ATTACK_CREATURE and observation is not None:
                favorable = self._favorable_creature_attacks(candidates, observation)
                if favorable:
                    return favorable[0]
                blocker_removal = self._blocker_removal_attacks(candidates, observation)
                if blocker_removal:
                    return blocker_removal[0]
                continue
            if action_type == ActionType.REVOLUTION_CHANGE and observation is not None:
                return self._best_revolution_change(candidates, observation)
            if action_type == ActionType.INVASION and observation is not None:
                return self._best_invasion(candidates, observation)
            if action_type in {ActionType.ATTACK_PLAYER, ActionType.ATTACK_SHIELD} and observation is not None:
                if self._has_untapped_opponent_blocker(observation):
                    continue
            if action_type == ActionType.CAST_SPELL and observation is not None:
                spell = self._best_spell(candidates, observation)
                if spell is not None:
                    return spell
                continue
            if action_type == ActionType.SUMMON and observation is not None:
                return self._highest_cost_summon(candidates, observation)
            if action_type == ActionType.CHARGE_MANA and observation is not None:
                return self._best_mana_charge(candidates, observation)
            return candidates[0]

        return legal_actions[0]

    def _favorable_creature_attacks(self, actions: list[Action], observation: dict) -> list[Action]:
        own_creatures = observation["self"]["battle_zone"]
        opposing_creatures = observation["opponent"]["battle_zone"]
        favorable: list[Action] = []

        for action in actions:
            attacker_power = own_creatures[action.attacker_index]["card"]["power"]
            defender_power = opposing_creatures[action.target_index]["card"]["power"]
            if attacker_power > defender_power:
                favorable.append(action)

        return sorted(
            favorable,
            key=lambda action: (
                opposing_creatures[action.target_index]["card"]["power"],
                -own_creatures[action.attacker_index]["card"]["power"],
            ),
            reverse=True,
        )

    def _blocker_removal_attacks(self, actions: list[Action], observation: dict) -> list[Action]:
        own_creatures = observation["self"]["battle_zone"]
        opposing_creatures = observation["opponent"]["battle_zone"]
        removal: list[Action] = []

        for action in actions:
            defender = opposing_creatures[action.target_index]
            if not defender["card"]["blocker"]:
                continue
            attacker_power = own_creatures[action.attacker_index]["card"]["power"]
            defender_power = defender["card"]["power"]
            if attacker_power >= defender_power:
                removal.append(action)

        return sorted(
            removal,
            key=lambda action: opposing_creatures[action.target_index]["card"]["power"],
            reverse=True,
        )

    def _has_untapped_opponent_blocker(self, observation: dict) -> bool:
        return any(
            creature["card"]["blocker"] and not creature["tapped"]
            for creature in observation["opponent"]["battle_zone"]
        )

    def _highest_cost_summon(self, actions: list[Action], observation: dict) -> Action:
        hand = observation["self"]["hand"]
        return max(actions, key=lambda action: _action_card_cost(hand[action.card_index], action))

    def _best_revolution_change(self, actions: list[Action], observation: dict) -> Action:
        hand = observation["self"]["hand"]
        battle_zone = observation["self"]["battle_zone"]

        def score(action: Action) -> tuple[int, int, int]:
            change_card = hand[action.hand_index]
            returned = battle_zone[action.attacker_index]
            hachiko_bonus = 5 if returned["card"]["name"] == "特攻の忠剣ハチ公" else 0
            return change_card["power"] - returned["card"]["power"], hachiko_bonus, change_card["power"]

        return max(actions, key=score)

    def _best_invasion(self, actions: list[Action], observation: dict) -> Action:
        hand = observation["self"]["hand"]
        battle_zone = observation["self"]["battle_zone"]

        def score(action: Action) -> tuple[int, int, int]:
            invasion_card = hand[action.hand_index]
            source = battle_zone[action.attacker_index]
            hachiko_bonus = 5 if source["card"]["name"] == "特攻の忠剣ハチ公" else 0
            red_zone_bonus = 5 if invasion_card["name"] == "熱き侵略 レッドゾーンZ" else 0
            return invasion_card["power"] - source["card"]["power"], hachiko_bonus + red_zone_bonus, invasion_card["power"]

        return max(actions, key=score)

    def _best_spell(self, actions: list[Action], observation: dict) -> Action | None:
        hand = observation["self"]["hand"]
        opponent_creatures = observation["opponent"]["battle_zone"]
        shield_count = observation["self"]["shield_count"]
        hand_count = observation["self"]["hand_count"]

        destroy_actions = [
            action for action in actions
            if _action_spell_effect(hand[action.hand_index], action) == "DESTROY_TARGET"
        ]
        if destroy_actions:
            blocker_targets = [
                action for action in destroy_actions
                if opponent_creatures[action.target_index]["card"]["blocker"]
            ]
            if blocker_targets:
                return max(
                    blocker_targets,
                    key=lambda action: opponent_creatures[action.target_index]["card"]["power"],
                )
            return max(
                destroy_actions,
                key=lambda action: opponent_creatures[action.target_index]["card"]["power"],
            )

        for desired in ("MANA_BOOST", "GAIN_SHIELD", "DRAW_1"):
            if desired == "GAIN_SHIELD" and shield_count > 2:
                continue
            if desired == "DRAW_1" and hand_count > 2:
                continue
            for action in actions:
                effect = _action_spell_effect(hand[action.hand_index], action)
                if effect == desired:
                    return action
        return None

    def _block_or_decline(self, legal_actions: list[Action], observation: dict | None) -> Action:
        decline = next(
            (action for action in legal_actions if action.type == ActionType.DECLINE_BLOCK),
            legal_actions[-1],
        )
        block_actions = [action for action in legal_actions if action.type == ActionType.BLOCK]
        if observation is None or not block_actions:
            return decline

        pending = observation.get("pending_attack")
        if pending is None:
            return decline

        attacker_power = pending["attacker_power"]
        own_blockers = observation["self"]["battle_zone"]
        shield_count = observation["self"]["shield_count"]
        target_player = pending["target_type"] == "PLAYER"

        surviving_blocks = [
            action for action in block_actions
            if own_blockers[action.blocker_index]["card"]["power"] > attacker_power
        ]
        if surviving_blocks:
            return min(
                surviving_blocks,
                key=lambda action: own_blockers[action.blocker_index]["card"]["power"],
            )

        trading_blocks = [
            action for action in block_actions
            if own_blockers[action.blocker_index]["card"]["power"] == attacker_power
        ]
        if trading_blocks and (target_player or shield_count <= 2 or attacker_power >= 4000):
            return trading_blocks[0]

        if target_player and block_actions:
            return max(
                block_actions,
                key=lambda action: own_blockers[action.blocker_index]["card"]["power"],
            )

        if shield_count <= 1 and block_actions:
            return max(
                block_actions,
                key=lambda action: own_blockers[action.blocker_index]["card"]["power"],
            )

        return decline

    def _highest_cost_charge(self, actions: list[Action], observation: dict) -> Action:
        hand = observation["self"]["hand"]
        return max(actions, key=lambda action: hand[action.card_index]["cost"])

    def _best_mana_charge(self, actions: list[Action], observation: dict) -> Action:
        hand = observation["self"]["hand"]
        mana_counts = observation["self"].get("civilization_counts", {})
        playable_indices = {action.card_index for action in observation.get("legal_actions", []) if action.type != ActionType.CHARGE_MANA}
        hand_civilizations = Counter(
            civilization
            for card in hand
            for civilization in card.get("civilizations", [card.get("civilization", "COLORLESS")])
            if civilization != "COLORLESS"
        )

        def score(action: Action) -> tuple[float, int]:
            card = hand[action.card_index]
            civilizations = tuple(card.get("civilizations", [card.get("civilization", "COLORLESS")]))
            non_colorless = [civilization for civilization in civilizations if civilization != "COLORLESS"]
            value = 0.0
            for civilization in non_colorless:
                if mana_counts.get(civilization, 0) == 0:
                    value += 5.0
                value += hand_civilizations[civilization] * 0.6
            if len(non_colorless) > 1 and observation["turn_number"] <= 3:
                value += 2.0
            if card["cost"] <= 3 and non_colorless and mana_counts.get(non_colorless[0], 0) == 0:
                value += 1.5
            if action.card_index in playable_indices:
                value -= 4.0
            value += card["cost"] * 0.1
            return value, card["cost"]

        return max(actions, key=score)


def _action_card_cost(card: dict, action: Action) -> int:
    if action.side == "top" and card.get("top_side"):
        return int(card["top_side"].get("cost") or card["cost"])
    if action.side == "bottom" and card.get("bottom_side"):
        return int(card["bottom_side"].get("cost") or card["cost"])
    return int(card["cost"])


def _action_spell_effect(card: dict, action: Action) -> str | None:
    if action.side == "bottom" and card.get("bottom_side"):
        side = card["bottom_side"]
        return side.get("spell_effect") or side.get("trigger_effect")
    return card.get("spell_effect") or card.get("trigger_effect")
