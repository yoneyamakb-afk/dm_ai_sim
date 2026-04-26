from __future__ import annotations

from dm_ai_sim.actions import Action, ActionType


class HeuristicAgent:
    def act(self, legal_actions: list[Action], observation: dict | None = None) -> Action:
        if not legal_actions:
            raise ValueError("No legal actions available.")

        for action_type in (
            ActionType.ATTACK_CREATURE,
            ActionType.ATTACK_PLAYER,
            ActionType.ATTACK_SHIELD,
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
            if action_type in {ActionType.ATTACK_PLAYER, ActionType.ATTACK_SHIELD} and observation is not None:
                if self._has_untapped_opponent_blocker(observation):
                    continue
            if action_type == ActionType.SUMMON and observation is not None:
                return self._highest_cost_summon(candidates, observation)
            if action_type == ActionType.CHARGE_MANA and observation is not None:
                return self._highest_cost_charge(candidates, observation)
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
        return max(actions, key=lambda action: hand[action.card_index]["cost"])

    def _highest_cost_charge(self, actions: list[Action], observation: dict) -> Action:
        hand = observation["self"]["hand"]
        return max(actions, key=lambda action: hand[action.card_index]["cost"])
