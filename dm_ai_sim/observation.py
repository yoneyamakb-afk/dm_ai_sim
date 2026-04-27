from __future__ import annotations

from dm_ai_sim.card import VALID_CIVILIZATIONS


OBSERVATION_SIZE = 47


def mana_observation_features(self_obs: dict, opponent_obs: dict) -> list[float]:
    own_counts = self_obs.get("civilization_counts", {})
    own_untapped = self_obs.get("untapped_civilization_counts", {})
    opponent_counts = opponent_obs.get("civilization_counts", {})
    playable = self_obs.get("playable_hand_count") or 0
    civilization_shortfall = self_obs.get("unplayable_due_to_civilization_count") or 0
    cost_shortfall = self_obs.get("unplayable_due_to_cost_count") or 0
    multicolor = self_obs.get("multicolor_mana_count") or 0
    stalled_by_civilization = 1.0 if playable == 0 and civilization_shortfall > 0 else 0.0

    values: list[float] = []
    values.extend(min(float(own_counts.get(civ, 0)) / 40.0, 1.0) for civ in VALID_CIVILIZATIONS)
    values.extend(min(float(own_untapped.get(civ, 0)) / 40.0, 1.0) for civ in VALID_CIVILIZATIONS)
    values.extend(min(float(opponent_counts.get(civ, 0)) / 40.0, 1.0) for civ in VALID_CIVILIZATIONS)
    values.extend(
        [
            min(float(playable) / 40.0, 1.0),
            min(float(civilization_shortfall) / 40.0, 1.0),
            min(float(cost_shortfall) / 40.0, 1.0),
            min(float(multicolor) / 40.0, 1.0),
            stalled_by_civilization,
        ]
    )
    return values

