from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from dm_ai_sim.action_encoder import ACTION_SPACE_SIZE, legal_action_mask
from dm_ai_sim.agents.heuristic_agent import HeuristicAgent
from dm_ai_sim.agents.random_agent import RandomAgent
from dm_ai_sim.env import Env, EnvConfig
from dm_ai_sim.state import Phase

OpponentType = Literal["random", "heuristic"]


@dataclass(slots=True)
class DuelMastersGymConfig:
    opponent: OpponentType = "random"
    seed: int | None = None
    max_turns: int = 200
    intermediate_rewards: bool = False
    invalid_action_penalty: float = -0.01
    shield_break_reward: float = 0.05
    max_invalid_actions: int = 50


class DuelMastersGymEnv(gym.Env):
    metadata = {"render_modes": ["human", "ansi"], "render_fps": 4}

    def __init__(self, config: DuelMastersGymConfig | None = None, render_mode: str | None = None) -> None:
        super().__init__()
        self.config = config or DuelMastersGymConfig()
        self.render_mode = render_mode
        self.action_space = spaces.Discrete(ACTION_SPACE_SIZE)
        self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(24,), dtype=np.float32)
        self.base_env = self._make_base_env()
        self.opponent_agent = self._make_opponent_agent()
        self.invalid_actions = 0

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        super().reset(seed=seed)
        if seed is not None:
            self.config.seed = seed
        self.base_env = self._make_base_env()
        self.opponent_agent = self._make_opponent_agent()
        self.invalid_actions = 0
        self.base_env.reset()
        return self._observation_vector(), self._info()

    def step(self, action: int) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        action_id = int(action)
        if action_id not in self.base_env.legal_action_ids():
            self.invalid_actions += 1
            truncated = self.invalid_actions >= self.config.max_invalid_actions
            return (
                self._observation_vector(),
                self.config.invalid_action_penalty,
                False,
                truncated,
                self._info(invalid_action=True),
            )

        self.invalid_actions = 0
        before_opponent_shields = self.base_env.get_observation(player_id=0)["opponent"]["shield_count"]
        _observation, reward, done, info = self.base_env.step_action_id(action_id)
        reward = self._player_zero_reward(reward, done)

        if self.config.intermediate_rewards:
            after_opponent_shields = self.base_env.get_observation(player_id=0)["opponent"]["shield_count"]
            if after_opponent_shields < before_opponent_shields:
                reward += self.config.shield_break_reward

        while not done and self.base_env.state is not None and self.base_env.state.current_player == 1:
            opponent_observation = self.base_env.get_observation()
            opponent_action = self.opponent_agent.act(self.base_env.legal_actions(), opponent_observation)
            _observation, _opponent_reward, done, info = self.base_env.step(opponent_action)

        if done:
            reward = self._terminal_reward()

        return self._observation_vector(), float(reward), bool(done), False, self._info(base_info=info)

    def render(self) -> str | None:
        state = self.base_env.state
        if state is None:
            text = "DuelMastersGymEnv(not reset)"
        else:
            text = (
                f"turn={state.turn_number} phase={state.phase.value} "
                f"current_player={state.current_player} winner={state.winner} done={state.done}"
            )
        if self.render_mode == "human":
            print(text)
            return None
        return text

    def action_masks(self) -> np.ndarray:
        return np.asarray(legal_action_mask(self.base_env), dtype=bool)

    def _make_base_env(self) -> Env:
        return Env(
            config=EnvConfig(
                seed=self.config.seed,
                max_turns=self.config.max_turns,
                intermediate_rewards=False,
                include_action_mask=True,
            )
        )

    def _make_opponent_agent(self) -> RandomAgent | HeuristicAgent:
        if self.config.opponent == "heuristic":
            return HeuristicAgent()
        return RandomAgent(seed=self.config.seed)

    def _observation_vector(self) -> np.ndarray:
        state = self.base_env.state
        if state is None:
            return np.zeros(self.observation_space.shape, dtype=np.float32)

        obs = self.base_env.get_observation(player_id=0)
        self_obs = obs["self"]
        opponent_obs = obs["opponent"]
        legal_ids = self.base_env.legal_action_ids() if not state.done else []
        player = state.players[0]
        opponent = state.players[1]

        values = [
            1.0 if state.current_player == 0 else 0.0,
            1.0 if state.phase == Phase.MAIN else 0.0,
            1.0 if state.phase == Phase.ATTACK else 0.0,
            min(state.turn_number / self.config.max_turns, 1.0),
            self_obs["hand_count"] / 40.0,
            self_obs["deck_count"] / 40.0,
            self_obs["shield_count"] / 5.0,
            len(player.mana) / 40.0,
            sum(1 for mana in player.mana if not mana.tapped) / 40.0,
            len(player.battle_zone) / 40.0,
            sum(1 for creature in player.battle_zone if not creature.tapped) / 40.0,
            len(player.graveyard) / 40.0,
            opponent_obs["hand_count"] / 40.0,
            opponent_obs["deck_count"] / 40.0,
            opponent_obs["shield_count"] / 5.0,
            len(opponent.mana) / 40.0,
            len(opponent.battle_zone) / 40.0,
            len(opponent.graveyard) / 40.0,
            (self_obs["shield_count"] - opponent_obs["shield_count"] + 5) / 10.0,
            (len(player.battle_zone) - len(opponent.battle_zone) + 40) / 80.0,
            len(legal_ids) / ACTION_SPACE_SIZE,
            1.0 if 160 in legal_ids else 0.0,
            1.0 if 161 in legal_ids else 0.0,
            min(self.invalid_actions / self.config.max_invalid_actions, 1.0),
        ]
        return np.asarray(values, dtype=np.float32)

    def _info(self, base_info: dict[str, Any] | None = None, invalid_action: bool = False) -> dict[str, Any]:
        info = dict(base_info or {})
        info["action_mask"] = legal_action_mask(self.base_env)
        info["legal_action_ids"] = self.base_env.legal_action_ids()
        info["invalid_action"] = invalid_action
        return info

    def _player_zero_reward(self, base_reward: float, done: bool) -> float:
        if done:
            return self._terminal_reward()
        return base_reward

    def _terminal_reward(self) -> float:
        state = self.base_env.state
        if state is None or state.winner is None:
            return 0.0
        return 1.0 if state.winner == 0 else -1.0
