from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from sb3_contrib import MaskablePPO

if TYPE_CHECKING:
    from dm_ai_sim.selfplay_env import DuelMastersSelfPlayEnv


class SelfPlayTriggerFineTunedAgent:
    _reported_prediction_failures: set[Path] = set()

    def __init__(self, model_path: str | Path = Path("saved_models") / "selfplay_trigger_finetuned.zip") -> None:
        self.model_path = Path(model_path)
        self.model: MaskablePPO | None = None
        if self.model_path.exists():
            try:
                self.model = MaskablePPO.load(str(self.model_path))
            except Exception as exc:
                print(f"Skipping SelfPlayTriggerFineTunedAgent model {self.model_path}: {exc}")

    @property
    def is_available(self) -> bool:
        return self.model is not None

    def act(self, env: "DuelMastersSelfPlayEnv", player_id: int = 0, deterministic: bool = True) -> int:
        legal_action_ids = env.base_env.legal_action_ids()
        if not legal_action_ids:
            raise ValueError("No legal action ids available.")
        if self.model is None:
            return legal_action_ids[0]
        try:
            action, _state = self.model.predict(
                env.observation_vector(player_id=player_id),
                deterministic=deterministic,
                action_masks=env.action_masks(),
            )
        except Exception as exc:
            if self.model_path not in self._reported_prediction_failures:
                print(f"SelfPlayTriggerFineTunedAgent prediction failed, falling back: {exc}")
                self._reported_prediction_failures.add(self.model_path)
            return legal_action_ids[0]
        action_id = int(np.asarray(action).item())
        return action_id if action_id in legal_action_ids else legal_action_ids[0]
