from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

import numpy as np
from sb3_contrib import MaskablePPO

if TYPE_CHECKING:
    from dm_ai_sim.selfplay_env import DuelMastersSelfPlayEnv


class SelfPlayOptionalBlockFineTunedAgent:
    _reported_prediction_errors: ClassVar[set[str]] = set()

    def __init__(
        self,
        model_path: str | Path = Path("saved_models") / "selfplay_optional_block_finetuned.zip",
    ) -> None:
        self.model_path = Path(model_path)
        self.model: MaskablePPO | None = None
        if self.model_path.exists():
            try:
                self.model = MaskablePPO.load(str(self.model_path))
            except Exception as exc:
                print(f"Skipping SelfPlayOptionalBlockFineTunedAgent model {self.model_path}: {exc}")

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
            error_key = str(exc)
            if error_key not in self._reported_prediction_errors:
                self._reported_prediction_errors.add(error_key)
                print(f"SelfPlayOptionalBlockFineTunedAgent prediction failed, falling back: {exc}")
            return legal_action_ids[0]
        action_id = int(np.asarray(action).item())
        return action_id if action_id in legal_action_ids else legal_action_ids[0]
