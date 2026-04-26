from __future__ import annotations

import random

from dm_ai_sim.actions import Action


class RandomAgent:
    def __init__(self, seed: int | None = None) -> None:
        self.random = random.Random(seed)

    def act(self, legal_actions: list[Action], observation: dict | None = None) -> Action:
        if not legal_actions:
            raise ValueError("No legal actions available.")
        return self.random.choice(legal_actions)
