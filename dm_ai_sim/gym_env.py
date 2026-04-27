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
from dm_ai_sim.observation import OBSERVATION_SIZE, mana_observation_features
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
        self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(OBSERVATION_SIZE,), dtype=np.float32)
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
        pending = state.pending_attack
        pending_for_player = pending if pending is not None else None
        pending_blockers = own_untapped_blockers if pending_for_player and pending_for_player.defender_player == 0 else []
        last_trigger = obs.get("last_trigger", {})
        last_spell = obs.get("last_spell", {})
        own_visible_triggers = self_obs["visible_trigger_count"]
        opponent_visible_triggers = opponent_obs["visible_trigger_count"]
        own_spell_count = self_obs["spell_count"] or 0
        playable_spell_count = sum(1 for action_id in legal_ids if 256 <= action_id < 376)
        own_graveyard_spells = self_obs["graveyard_spell_count"]
        opponent_graveyard_spells = opponent_obs["graveyard_spell_count"]

        values = [
            1.0 if state.current_player == 0 else 0.0,
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
            min(own_spell_count / 40.0, 1.0),
            min((max(opponent_powers) if opponent_powers else 0) / 10000.0, 1.0),
            1.0 if pending_for_player is not None else min(playable_spell_count / 40.0, 1.0),
            1.0 if pending_for_player and pending_for_player.defender_player == 0 else min(len(opponent.battle_zone) / 40.0, 1.0),
            min(
                (
                    state.players[pending_for_player.attacker_player].battle_zone[pending_for_player.attacker_index].card.power
                    if pending_for_player
                    else own_graveyard_spells
                )
                / (10000.0 if pending_for_player else 40.0),
                1.0,
            ),
            (len(pending_blockers) / 40.0) if pending_for_player else len(legal_ids) / ACTION_SPACE_SIZE,
            min(
                (
                    max((creature.card.power for creature in pending_blockers), default=0)
                    if pending_for_player
                    else opponent_graveyard_spells
                )
                / (10000.0 if pending_for_player else 40.0),
                1.0,
            ),
            (1.0 if pending_for_player and pending_for_player.target_type == "PLAYER" else 0.0)
            if pending_for_player
            else max(
                self._trigger_effect_value(last_trigger.get("effect")),
                self._spell_effect_value(last_spell.get("effect")) if last_spell.get("cast") else 0.0,
            ),
        ]
        values.extend(mana_observation_features(self_obs, opponent_obs))
        return np.asarray(values, dtype=np.float32)

    def _trigger_effect_value(self, effect: str | None) -> float:
        values = {
            "DRAW_1": 0.25,
            "DESTROY_ATTACKER": 0.50,
            "SUMMON_SELF": 0.75,
            "GAIN_SHIELD": 1.0,
        }
        return values.get(effect, 0.0)

    def _spell_effect_value(self, effect: str | None) -> float:
        values = {
            "DRAW_1": 0.20,
            "DESTROY_TARGET": 0.45,
            "GAIN_SHIELD": 0.70,
            "MANA_BOOST": 0.95,
        }
        return values.get(effect, 0.0)

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
