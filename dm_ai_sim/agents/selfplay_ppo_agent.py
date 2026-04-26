from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from sb3_contrib import MaskablePPO

if TYPE_CHECKING:
    from dm_ai_sim.selfplay_env import DuelMastersSelfPlayEnv


class SelfPlayPPOAgent:
    def __init__(self, model_path: str | Path) -> None:
        self.model_path = Path(model_path)
        self.model = MaskablePPO.load(str(self.model_path))

    def act(
        self,
        env: "DuelMastersSelfPlayEnv",
        player_id: int = 0,
        deterministic: bool = True,
    ) -> int:
        observation = env.observation_vector(player_id=player_id)
        action, _state = self.model.predict(
            observation,
            deterministic=deterministic,
            action_masks=env.action_masks(),
        )
        return int(np.asarray(action).item())

    @classmethod
    def from_default_path(cls) -> "SelfPlayPPOAgent":
        return cls(Path("saved_models") / "selfplay_ppo.zip")
