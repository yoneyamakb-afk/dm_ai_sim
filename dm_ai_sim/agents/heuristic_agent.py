from __future__ import annotations

from dm_ai_sim.actions import Action, ActionType


class HeuristicAgent:
    def act(self, legal_actions: list[Action], observation: dict | None = None) -> Action:
        if not legal_actions:
            raise ValueError("No legal actions available.")

        for action_type in (
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
            if action_type == ActionType.SUMMON and observation is not None:
                return self._highest_cost_summon(candidates, observation)
            if action_type == ActionType.CHARGE_MANA and observation is not None:
                return self._highest_cost_charge(candidates, observation)
            return candidates[0]

        return legal_actions[0]

    def _highest_cost_summon(self, actions: list[Action], observation: dict) -> Action:
        hand = observation["self"]["hand"]
        return max(actions, key=lambda action: hand[action.card_index]["cost"])

    def _highest_cost_charge(self, actions: list[Action], observation: dict) -> Action:
        hand = observation["self"]["hand"]
        return max(actions, key=lambda action: hand[action.card_index]["cost"])
