from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dm_ai_sim.actions import ActionType
from dm_ai_sim.selfplay_env import DuelMastersSelfPlayEnv, SelfPlayConfig


@dataclass(slots=True)
class TriggerRewardConfig:
    enabled: bool = True
    lethal_success: float = 0.10
    missed_lethal: float = -0.05
    won_after_trigger: float = 0.05
    important_attacker_destroyed: float = -0.04
    rebuilt_lethal_after_gain_shield: float = 0.05
    answered_summon_self: float = 0.03
    shield_break: float = 0.02
    clean_shield_break: float = 0.02


@dataclass(slots=True)
class TriggerOpponentWeights:
    heuristic: float = 0.40
    ppo_trigger: float = 0.20
    selfplay_trigger: float = 0.20
    optional_block: float = 0.10
    random: float = 0.10
    snapshot: float = 0.10


class DuelMastersTriggerFineTuneEnv(DuelMastersSelfPlayEnv):
    def __init__(
        self,
        config: SelfPlayConfig | None = None,
        reward_config: TriggerRewardConfig | None = None,
        opponent_weights: TriggerOpponentWeights | None = None,
        ppo_trigger_path: Path | None = None,
        selfplay_trigger_path: Path | None = None,
        optional_block_path: Path | None = None,
        render_mode: str | None = None,
    ) -> None:
        super().__init__(config=config, render_mode=render_mode)
        self.reward_config = reward_config or TriggerRewardConfig()
        self.opponent_weights = opponent_weights or TriggerOpponentWeights()
        model_dir = Path("saved_models")
        self.ppo_trigger_path = ppo_trigger_path or model_dir / "ppo_trigger.zip"
        self.selfplay_trigger_path = selfplay_trigger_path or model_dir / "selfplay_trigger.zip"
        self.optional_block_path = optional_block_path or model_dir / "selfplay_optional_block_finetuned.zip"

    def available_opponents(self) -> list[str | Path]:
        if self.config.fixed_opponent is not None:
            return [self.config.fixed_opponent]

        weighted: list[str | Path] = []
        self._extend_weighted(weighted, "heuristic", self.opponent_weights.heuristic)
        if self.ppo_trigger_path.exists():
            self._extend_weighted(weighted, self.ppo_trigger_path, self.opponent_weights.ppo_trigger)
        if self.selfplay_trigger_path.exists():
            self._extend_weighted(weighted, self.selfplay_trigger_path, self.opponent_weights.selfplay_trigger)
        if self.optional_block_path.exists():
            self._extend_weighted(weighted, self.optional_block_path, self.opponent_weights.optional_block)
        self._extend_weighted(weighted, "random", self.opponent_weights.random)
        snapshots = self._snapshot_paths()[-self.config.max_pool_size :]
        if snapshots:
            repeats = max(1, int(self.opponent_weights.snapshot * 100))
            for snapshot in snapshots:
                weighted.extend([snapshot] * repeats)
        return weighted or ["heuristic"]

    def step(self, action: int):
        before = self._snapshot_player_zero_state(action)
        observation, reward, terminated, truncated, info = super().step(action)
        if self.reward_config.enabled:
            reward += self._shaped_reward(before, info)
        return observation, float(reward), terminated, truncated, info

    def _extend_weighted(self, values: list[str | Path], opponent: str | Path, weight: float) -> None:
        repeats = max(0, int(weight * 100))
        values.extend([opponent] * repeats)

    def _snapshot_player_zero_state(self, action_id: int) -> dict[str, int | bool | str]:
        state = self.base_env.state
        if state is None:
            return {}
        player = state.players[0]
        opponent = state.players[1]
        legal_actions = self.base_env.legal_actions()
        action = next(
            (
                candidate
                for candidate, candidate_id in zip(legal_actions, self.base_env.legal_action_ids())
                if candidate_id == action_id
            ),
            None,
        )
        own_attackers = [creature for creature in player.battle_zone if not creature.tapped]
        return {
            "action_type": action.type.value if action is not None else "",
            "own_can_attack_count": len(own_attackers),
            "own_max_power": max((creature.card.power for creature in own_attackers), default=0),
            "opponent_shields": len(opponent.shields),
            "opponent_creature_count": len(opponent.battle_zone),
            "opponent_hand_count": len(opponent.hand),
            "last_trigger_effect": state.last_trigger_effect or "",
        }

    def _shaped_reward(self, before: dict[str, int | bool | str], info: dict) -> float:
        state = self.base_env.state
        if state is None or not before:
            return 0.0
        player = state.players[0]
        opponent = state.players[1]
        reward = 0.0
        action_type = str(before["action_type"])
        won = state.done and state.winner == 0

        if won and action_type == ActionType.ATTACK_PLAYER.value:
            reward += self.reward_config.lethal_success
        if (
            action_type == ActionType.END_ATTACK.value
            and int(before["opponent_shields"]) == 0
            and int(before["own_can_attack_count"]) > 0
        ):
            reward += self.reward_config.missed_lethal
        if won and info.get("trigger_activated"):
            reward += self.reward_config.won_after_trigger
        if info.get("shield_broken"):
            reward += self.reward_config.shield_break
            if not info.get("trigger_activated"):
                reward += self.reward_config.clean_shield_break
        if (
            info.get("attacker_destroyed_by_trigger")
            and int(before["own_max_power"]) >= 4000
        ):
            reward += self.reward_config.important_attacker_destroyed
        if (
            str(before["last_trigger_effect"]) == "GAIN_SHIELD"
            and won
            and action_type == ActionType.ATTACK_PLAYER.value
        ):
            reward += self.reward_config.rebuilt_lethal_after_gain_shield
        if (
            str(before["last_trigger_effect"]) == "SUMMON_SELF"
            and len(opponent.battle_zone) < int(before["opponent_creature_count"])
        ):
            reward += self.reward_config.answered_summon_self
        return reward
