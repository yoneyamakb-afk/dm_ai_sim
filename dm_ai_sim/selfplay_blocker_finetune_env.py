from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dm_ai_sim.actions import ActionType
from dm_ai_sim.agents.heuristic_agent import HeuristicAgent
from dm_ai_sim.agents.random_agent import RandomAgent
from dm_ai_sim.agents.selfplay_ppo_agent import SelfPlayPPOAgent
from dm_ai_sim.selfplay_env import DuelMastersSelfPlayEnv, SelfPlayConfig


@dataclass(slots=True)
class FineTuneRewardConfig:
    enabled: bool = True
    destroy_opponent_blocker: float = 0.05
    own_attack_blocked: float = 0.0
    unblocked_shield_break: float = 0.03
    favorable_trade: float = 0.04
    trade: float = 0.01
    unfavorable_trade: float = -0.04


@dataclass(slots=True)
class FineTuneOpponentWeights:
    heuristic: float = 0.60
    ppo_blocker: float = 0.20
    random: float = 0.10
    snapshot: float = 0.10


class DuelMastersBlockerFineTuneEnv(DuelMastersSelfPlayEnv):
    def __init__(
        self,
        config: SelfPlayConfig | None = None,
        reward_config: FineTuneRewardConfig | None = None,
        opponent_weights: FineTuneOpponentWeights | None = None,
        ppo_blocker_path: Path | None = None,
        render_mode: str | None = None,
    ) -> None:
        super().__init__(config=config, render_mode=render_mode)
        self.reward_config = reward_config or FineTuneRewardConfig()
        self.opponent_weights = opponent_weights or FineTuneOpponentWeights()
        self.ppo_blocker_path = ppo_blocker_path or Path("saved_models") / "ppo_blocker.zip"

    def available_opponents(self) -> list[str | Path]:
        if self.config.fixed_opponent is not None:
            return [self.config.fixed_opponent]

        weighted: list[str | Path] = []
        self._extend_weighted(weighted, "heuristic", self.opponent_weights.heuristic)
        if self.ppo_blocker_path.exists():
            self._extend_weighted(weighted, self.ppo_blocker_path, self.opponent_weights.ppo_blocker)
        self._extend_weighted(weighted, "random", self.opponent_weights.random)
        snapshots = self._snapshot_paths()[-self.config.max_pool_size :]
        if snapshots:
            repeats = max(1, int(self.opponent_weights.snapshot * 100))
            for snapshot in snapshots:
                weighted.extend([snapshot] * repeats)
        return weighted or ["heuristic"]

    def step(self, action: int):
        before = self._snapshot_player_zero_state()
        observation, reward, terminated, truncated, info = super().step(action)
        if self.reward_config.enabled:
            reward += self._shaped_reward(before, info)
        return observation, float(reward), terminated, truncated, info

    def _extend_weighted(self, values: list[str | Path], opponent: str | Path, weight: float) -> None:
        repeats = max(0, int(weight * 100))
        values.extend([opponent] * repeats)

    def _snapshot_player_zero_state(self) -> dict[str, int | bool]:
        state = self.base_env.state
        if state is None:
            return {}
        player = state.players[0]
        opponent = state.players[1]
        attacker_power = 0
        action_type = None
        if state.current_player == 0:
            legal_actions = self.base_env.legal_actions()
            action_ids = self.base_env.legal_action_ids()
            if legal_actions and action_ids:
                action = legal_actions[0]
                action_type = action.type
        return {
            "opponent_blocker_count": sum(1 for creature in opponent.battle_zone if creature.card.blocker),
            "opponent_creature_count": len(opponent.battle_zone),
            "own_creature_count": len(player.battle_zone),
            "opponent_shields": len(opponent.shields),
            "action_type": action_type,
            "attacker_power": attacker_power,
        }

    def _shaped_reward(self, before: dict[str, int | bool], info: dict) -> float:
        state = self.base_env.state
        if state is None or not before:
            return 0.0

        player = state.players[0]
        opponent = state.players[1]
        reward = 0.0
        opponent_blockers_after = sum(1 for creature in opponent.battle_zone if creature.card.blocker)
        opponent_creatures_after = len(opponent.battle_zone)
        own_creatures_after = len(player.battle_zone)
        opponent_shields_after = len(opponent.shields)

        if opponent_blockers_after < int(before["opponent_blocker_count"]):
            reward += self.reward_config.destroy_opponent_blocker
        if (
            not info.get("blocked")
            and opponent_shields_after < int(before["opponent_shields"])
        ):
            reward += self.reward_config.unblocked_shield_break
        if (
            opponent_creatures_after < int(before["opponent_creature_count"])
            and own_creatures_after >= int(before["own_creature_count"])
        ):
            reward += self.reward_config.favorable_trade
        if (
            own_creatures_after < int(before["own_creature_count"])
            and opponent_creatures_after < int(before["opponent_creature_count"])
        ):
            reward += self.reward_config.trade
        if (
            own_creatures_after < int(before["own_creature_count"])
            and opponent_creatures_after >= int(before["opponent_creature_count"])
        ):
            reward += self.reward_config.unfavorable_trade
        return reward
