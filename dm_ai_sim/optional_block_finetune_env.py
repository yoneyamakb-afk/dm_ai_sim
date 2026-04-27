from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dm_ai_sim.actions import ActionType
from dm_ai_sim.selfplay_env import DuelMastersSelfPlayEnv, SelfPlayConfig


@dataclass(slots=True)
class OptionalBlockRewardConfig:
    enabled: bool = True
    lethal_success: float = 0.10
    missed_lethal: float = -0.05
    block_prevented_loss: float = 0.08
    blocker_favorable_trade: float = 0.04
    blocker_trade_prevented_lethal: float = 0.04
    declined_loss: float = -0.08
    attack_order_opened_followup: float = 0.03
    attack_order_missed_lethal: float = -0.05


@dataclass(slots=True)
class OptionalBlockOpponentWeights:
    heuristic: float = 0.50
    ppo_optional_block: float = 0.20
    selfplay_optional_block: float = 0.20
    random: float = 0.10
    snapshot: float = 0.10


class DuelMastersOptionalBlockFineTuneEnv(DuelMastersSelfPlayEnv):
    def __init__(
        self,
        config: SelfPlayConfig | None = None,
        reward_config: OptionalBlockRewardConfig | None = None,
        opponent_weights: OptionalBlockOpponentWeights | None = None,
        ppo_optional_block_path: Path | None = None,
        selfplay_optional_block_path: Path | None = None,
        render_mode: str | None = None,
    ) -> None:
        super().__init__(config=config, render_mode=render_mode)
        self.reward_config = reward_config or OptionalBlockRewardConfig()
        self.opponent_weights = opponent_weights or OptionalBlockOpponentWeights()
        self.ppo_optional_block_path = ppo_optional_block_path or Path("saved_models") / "ppo_optional_block.zip"
        self.selfplay_optional_block_path = (
            selfplay_optional_block_path or Path("saved_models") / "selfplay_optional_block.zip"
        )

    def available_opponents(self) -> list[str | Path]:
        if self.config.fixed_opponent is not None:
            return [self.config.fixed_opponent]

        weighted: list[str | Path] = []
        self._extend_weighted(weighted, "heuristic", self.opponent_weights.heuristic)
        if self.ppo_optional_block_path.exists():
            self._extend_weighted(weighted, self.ppo_optional_block_path, self.opponent_weights.ppo_optional_block)
        if self.selfplay_optional_block_path.exists():
            self._extend_weighted(
                weighted,
                self.selfplay_optional_block_path,
                self.opponent_weights.selfplay_optional_block,
            )
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
            (candidate for candidate, candidate_id in zip(legal_actions, self.base_env.legal_action_ids()) if candidate_id == action_id),
            None,
        )
        pending = state.pending_attack
        return {
            "own_creature_count": len(player.battle_zone),
            "opponent_creature_count": len(opponent.battle_zone),
            "own_shields": len(player.shields),
            "opponent_shields": len(opponent.shields),
            "own_can_attack_count": sum(1 for creature in player.battle_zone if not creature.tapped),
            "opponent_can_attack_count": sum(1 for creature in opponent.battle_zone if not creature.tapped),
            "action_type": action.type.value if action is not None else "",
            "pending_target_player": pending is not None and pending.target_type == "PLAYER",
            "pending_defender_player": pending.defender_player if pending is not None else -1,
            "blocker_count": sum(1 for creature in player.battle_zone if creature.card.blocker and not creature.tapped),
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
        lost = state.done and state.winner == 1

        if won and action_type == ActionType.ATTACK_PLAYER.value:
            reward += self.reward_config.lethal_success
        if (
            action_type == ActionType.END_ATTACK.value
            and int(before["opponent_shields"]) == 0
            and int(before["own_can_attack_count"]) > 0
        ):
            reward += self.reward_config.missed_lethal
        if info.get("blocked") and int(before["pending_defender_player"]) == 0:
            own_after = len(player.battle_zone)
            opponent_after = len(opponent.battle_zone)
            if int(before["pending_target_player"]):
                reward += self.reward_config.block_prevented_loss
            if opponent_after < int(before["opponent_creature_count"]) and own_after >= int(before["own_creature_count"]):
                reward += self.reward_config.blocker_favorable_trade
            if opponent_after < int(before["opponent_creature_count"]) and own_after < int(before["own_creature_count"]):
                reward += self.reward_config.blocker_trade_prevented_lethal
        if (
            lost
            and info.get("declined_block")
            and int(before["pending_defender_player"]) == 0
            and int(before["blocker_count"]) > 0
        ):
            reward += self.reward_config.declined_loss
        if (
            action_type == ActionType.ATTACK_CREATURE.value
            and len(opponent.battle_zone) < int(before["opponent_creature_count"])
            and int(before["own_can_attack_count"]) > 1
        ):
            reward += self.reward_config.attack_order_opened_followup
        if (
            action_type == ActionType.ATTACK_SHIELD.value
            and int(before["opponent_shields"]) == 0
            and int(before["own_can_attack_count"]) > 1
            and not won
        ):
            reward += self.reward_config.attack_order_missed_lethal
        return reward
