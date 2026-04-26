from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from dm_ai_sim.action_encoder import ACTION_SPACE_SIZE, legal_action_mask
from dm_ai_sim.agents.heuristic_agent import HeuristicAgent
from dm_ai_sim.agents.random_agent import RandomAgent
from dm_ai_sim.agents.selfplay_ppo_agent import SelfPlayPPOAgent
from dm_ai_sim.env import Env, EnvConfig
from dm_ai_sim.state import Phase


@dataclass(slots=True)
class SelfPlayConfig:
    seed: int | None = None
    max_turns: int = 200
    opponent_pool_dir: Path = Path("saved_models") / "opponents"
    fixed_opponent: str | Path | None = None
    include_heuristic_opponent: bool = True
    include_random_opponent: bool = True
    intermediate_rewards: bool = True
    shield_break_reward: float = 0.05
    invalid_action_penalty: float = -0.01
    max_invalid_actions: int = 50
    max_pool_size: int = 10


class DuelMastersSelfPlayEnv(gym.Env):
    metadata = {"render_modes": ["human", "ansi"], "render_fps": 4}

    def __init__(self, config: SelfPlayConfig | None = None, render_mode: str | None = None) -> None:
        super().__init__()
        self.config = config or SelfPlayConfig()
        self.render_mode = render_mode
        self.rng = random.Random(self.config.seed)
        self.action_space = spaces.Discrete(ACTION_SPACE_SIZE)
        self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(24,), dtype=np.float32)
        self.base_env = self._make_base_env()
        self.opponent: RandomAgent | HeuristicAgent | SelfPlayPPOAgent = RandomAgent(seed=self.config.seed)
        self.opponent_name = "random"
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
            self.rng.seed(seed)
        self.base_env = self._make_base_env()
        self.opponent, self.opponent_name = self._select_opponent()
        self.invalid_actions = 0
        self.base_env.reset()
        return self.observation_vector(player_id=0), self._info()

    def step(self, action: int) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        action_id = int(action)
        if action_id not in self.base_env.legal_action_ids():
            self.invalid_actions += 1
            truncated = self.invalid_actions >= self.config.max_invalid_actions
            return (
                self.observation_vector(player_id=0),
                self.config.invalid_action_penalty,
                False,
                truncated,
                self._info(invalid_action=True),
            )

        self.invalid_actions = 0
        before_opponent_shields = self.base_env.get_observation(player_id=0)["opponent"]["shield_count"]
        _observation, _reward, done, info = self.base_env.step_action_id(action_id)
        reward = 0.0

        if self.config.intermediate_rewards:
            after_opponent_shields = self.base_env.get_observation(player_id=0)["opponent"]["shield_count"]
            if after_opponent_shields < before_opponent_shields:
                reward += self.config.shield_break_reward

        while not done and self.base_env.state is not None and self.base_env.state.current_player == 1:
            if isinstance(self.opponent, SelfPlayPPOAgent):
                opponent_action_id = self.opponent.act(self, player_id=1)
                _observation, _opponent_reward, done, info = self.base_env.step_action_id(opponent_action_id)
            else:
                opponent_observation = self.base_env.get_observation()
                opponent_action = self.opponent.act(self.base_env.legal_actions(), opponent_observation)
                _observation, _opponent_reward, done, info = self.base_env.step(opponent_action)

        if done:
            reward = self._terminal_reward()

        return self.observation_vector(player_id=0), float(reward), bool(done), False, self._info(base_info=info)

    def render(self) -> str | None:
        state = self.base_env.state
        if state is None:
            text = "DuelMastersSelfPlayEnv(not reset)"
        else:
            text = (
                f"turn={state.turn_number} phase={state.phase.value} "
                f"current_player={state.current_player} opponent={self.opponent_name} "
                f"winner={state.winner} done={state.done}"
            )
        if self.render_mode == "human":
            print(text)
            return None
        return text

    def action_masks(self) -> np.ndarray:
        return np.asarray(legal_action_mask(self.base_env), dtype=bool)

    def observation_vector(self, player_id: int = 0) -> np.ndarray:
        state = self.base_env.state
        if state is None:
            return np.zeros(self.observation_space.shape, dtype=np.float32)

        obs = self.base_env.get_observation(player_id=player_id)
        self_obs = obs["self"]
        opponent_obs = obs["opponent"]
        player = state.players[player_id]
        opponent = state.players[1 - player_id]
        legal_ids = self.base_env.legal_action_ids() if state.current_player == player_id and not state.done else []
        own_powers = [creature.card.power for creature in player.battle_zone]
        opponent_powers = [creature.card.power for creature in opponent.battle_zone]
        own_total_power = sum(own_powers)
        opponent_total_power = sum(opponent_powers)
        own_blockers = [creature for creature in player.battle_zone if creature.card.blocker]
        opponent_blockers = [creature for creature in opponent.battle_zone if creature.card.blocker]
        own_untapped_blockers = [creature for creature in own_blockers if not creature.tapped]
        opponent_untapped_blockers = [creature for creature in opponent_blockers if not creature.tapped]
        own_blocker_max_power = max((creature.card.power for creature in own_blockers), default=0)
        opponent_blocker_max_power = max((creature.card.power for creature in opponent_blockers), default=0)

        values = [
            1.0 if state.current_player == player_id else 0.0,
            1.0 if state.phase == Phase.MAIN else 0.0,
            1.0 if state.phase == Phase.ATTACK else 0.0,
            min(state.turn_number / self.config.max_turns, 1.0),
            self_obs["hand_count"] / 40.0,
            self_obs["deck_count"] / 40.0,
            self_obs["shield_count"] / 5.0,
            len(player.mana) / 40.0,
            len(own_blockers) / 40.0,
            len(player.battle_zone) / 40.0,
            len(own_untapped_blockers) / 40.0,
            min((max(own_powers) if own_powers else 0) / 10000.0, 1.0),
            opponent_obs["hand_count"] / 40.0,
            opponent_obs["deck_count"] / 40.0,
            opponent_obs["shield_count"] / 5.0,
            len(opponent.mana) / 40.0,
            len(opponent_blockers) / 40.0,
            min((max(opponent_powers) if opponent_powers else 0) / 10000.0, 1.0),
            min(own_total_power / 100000.0, 1.0),
            min(opponent_total_power / 100000.0, 1.0),
            len(opponent_untapped_blockers) / 40.0,
            len(legal_ids) / ACTION_SPACE_SIZE,
            min(own_blocker_max_power / 10000.0, 1.0),
            min(opponent_blocker_max_power / 10000.0, 1.0),
        ]
        return np.asarray(values, dtype=np.float32)

    def _observation_vector(self) -> np.ndarray:
        return self.observation_vector(player_id=0)

    def available_opponents(self) -> list[str | Path]:
        if self.config.fixed_opponent is not None:
            return [self.config.fixed_opponent]

        opponents: list[str | Path] = []
        if self.config.include_heuristic_opponent:
            opponents.append("heuristic")
        if self.config.include_random_opponent:
            opponents.append("random")
        opponents.extend(self._snapshot_paths()[-self.config.max_pool_size :])
        return opponents or ["random"]

    def _make_base_env(self) -> Env:
        return Env(
            config=EnvConfig(
                seed=self.config.seed,
                max_turns=self.config.max_turns,
                include_action_mask=True,
            )
        )

    def _select_opponent(self) -> tuple[RandomAgent | HeuristicAgent | SelfPlayPPOAgent, str]:
        selected = self.rng.choice(self.available_opponents())
        if str(selected) == "heuristic":
            return HeuristicAgent(), "heuristic"
        if str(selected) == "random":
            return RandomAgent(seed=self.config.seed), "random"
        path = Path(selected)
        return SelfPlayPPOAgent(path), path.name

    def _snapshot_paths(self) -> list[Path]:
        pool_dir = Path(self.config.opponent_pool_dir)
        if not pool_dir.exists():
            return []
        return sorted(pool_dir.glob("ppo_snapshot_*.zip"))

    def _info(self, base_info: dict[str, Any] | None = None, invalid_action: bool = False) -> dict[str, Any]:
        info = dict(base_info or {})
        info["action_mask"] = legal_action_mask(self.base_env)
        info["legal_action_ids"] = self.base_env.legal_action_ids()
        info["invalid_action"] = invalid_action
        info["opponent"] = self.opponent_name
        return info

    def _terminal_reward(self) -> float:
        state = self.base_env.state
        if state is None or state.winner is None:
            return 0.0
        return 1.0 if state.winner == 0 else -1.0
