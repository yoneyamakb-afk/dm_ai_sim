from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import torch
from sb3_contrib import MaskablePPO
from stable_baselines3 import PPO

if TYPE_CHECKING:
    from dm_ai_sim.gym_env import DuelMastersGymEnv


class PPOAgent:
    def __init__(self, model_path: str | Path) -> None:
        try:
            self.model = MaskablePPO.load(str(model_path))
        except Exception:
            self.model = PPO.load(str(model_path))

    def act(self, gym_env: "DuelMastersGymEnv", deterministic: bool = True) -> int:
        observation = gym_env._observation_vector()
        legal_action_ids = gym_env.base_env.legal_action_ids()
        if not legal_action_ids:
            raise ValueError("No legal action ids available.")

        if deterministic:
            if isinstance(self.model, MaskablePPO):
                try:
                    action, _state = self.model.predict(
                        observation,
                        deterministic=True,
                        action_masks=gym_env.action_masks(),
                    )
                except Exception as exc:
                    print(f"PPOAgent prediction failed, falling back: {exc}")
                    return legal_action_ids[0]
                action_id = int(np.asarray(action).item())
                return action_id if action_id in legal_action_ids else legal_action_ids[0]
            try:
                probabilities = self._action_probabilities(observation)
                return max(legal_action_ids, key=lambda action_id: probabilities[action_id])
            except Exception as exc:
                print(f"PPOAgent probability lookup failed, falling back: {exc}")
                return legal_action_ids[0]

        if isinstance(self.model, MaskablePPO):
            try:
                action, _state = self.model.predict(
                    observation,
                    deterministic=False,
                    action_masks=gym_env.action_masks(),
                )
            except Exception as exc:
                print(f"PPOAgent prediction failed, falling back: {exc}")
                return legal_action_ids[0]
            action_id = int(np.asarray(action).item())
            return action_id if action_id in legal_action_ids else legal_action_ids[0]

        try:
            action, _state = self.model.predict(observation, deterministic=False)
        except Exception as exc:
            print(f"PPOAgent prediction failed, falling back: {exc}")
            return legal_action_ids[0]
        action_id = int(np.asarray(action).item())
        if action_id in legal_action_ids:
            return action_id
        try:
            probabilities = self._action_probabilities(observation)
        except Exception as exc:
            print(f"PPOAgent probability lookup failed, falling back: {exc}")
            return legal_action_ids[0]
        legal_probs = np.asarray([probabilities[action_id] for action_id in legal_action_ids], dtype=np.float64)
        if legal_probs.sum() <= 0:
            return legal_action_ids[0]
        legal_probs = legal_probs / legal_probs.sum()
        return int(np.random.choice(legal_action_ids, p=legal_probs))

    def _action_probabilities(self, observation: np.ndarray) -> np.ndarray:
        obs_tensor, _vectorized = self.model.policy.obs_to_tensor(observation)
        with torch.no_grad():
            distribution = self.model.policy.get_distribution(obs_tensor)
        return distribution.distribution.probs.detach().cpu().numpy().reshape(-1)

    @classmethod
    def from_default_path(cls) -> "PPOAgent":
        return cls(Path("saved_models") / "ppo_basic.zip")
