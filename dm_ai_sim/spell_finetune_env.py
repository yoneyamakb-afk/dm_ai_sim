from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dm_ai_sim.actions import ActionType
from dm_ai_sim.selfplay_env import DuelMastersSelfPlayEnv, SelfPlayConfig


@dataclass(slots=True)
class SpellRewardConfig:
    enabled: bool = True
    blocker_removed_attack_passed: float = 0.06
    high_power_destroyed: float = 0.04
    mana_boost_to_high_cost_summon: float = 0.04
    draw_low_hand_recovered: float = 0.03
    gain_shield_survived_turn: float = 0.05
    won_after_spell: float = 0.03
    missed_lethal_without_spell: float = -0.05
    blocker_left_attack_stopped: float = -0.04
    low_value_destroy: float = -0.01
    spell_over_development: float = -0.01


@dataclass(slots=True)
class SpellOpponentWeights:
    heuristic: float = 0.40
    ppo_spell: float = 0.20
    selfplay_spell: float = 0.20
    trigger_best: float = 0.10
    random: float = 0.10
    snapshot: float = 0.10


class DuelMastersSpellFineTuneEnv(DuelMastersSelfPlayEnv):
    def __init__(
        self,
        config: SelfPlayConfig | None = None,
        reward_config: SpellRewardConfig | None = None,
        opponent_weights: SpellOpponentWeights | None = None,
        ppo_spell_path: Path | None = None,
        selfplay_spell_path: Path | None = None,
        trigger_best_path: Path | None = None,
        render_mode: str | None = None,
    ) -> None:
        super().__init__(config=config, render_mode=render_mode)
        self.reward_config = reward_config or SpellRewardConfig()
        self.opponent_weights = opponent_weights or SpellOpponentWeights()
        model_dir = Path("saved_models")
        self.ppo_spell_path = ppo_spell_path or model_dir / "ppo_spell.zip"
        self.selfplay_spell_path = selfplay_spell_path or model_dir / "selfplay_spell.zip"
        self.trigger_best_path = trigger_best_path or model_dir / "selfplay_trigger_finetuned.zip"
        self._spell_cast_this_game = False
        self._removed_blocker_waiting_for_attack = False
        self._mana_boost_waiting_for_summon = False
        self._gain_shield_turn: int | None = None

    def reset(self, *args, **kwargs):
        self._spell_cast_this_game = False
        self._removed_blocker_waiting_for_attack = False
        self._mana_boost_waiting_for_summon = False
        self._gain_shield_turn = None
        return super().reset(*args, **kwargs)

    def available_opponents(self) -> list[str | Path]:
        if self.config.fixed_opponent is not None:
            return [self.config.fixed_opponent]

        weighted: list[str | Path] = []
        self._extend_weighted(weighted, "heuristic", self.opponent_weights.heuristic)
        if self.ppo_spell_path.exists():
            self._extend_weighted(weighted, self.ppo_spell_path, self.opponent_weights.ppo_spell)
        if self.selfplay_spell_path.exists():
            self._extend_weighted(weighted, self.selfplay_spell_path, self.opponent_weights.selfplay_spell)
        if self.trigger_best_path.exists():
            self._extend_weighted(weighted, self.trigger_best_path, self.opponent_weights.trigger_best)
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
        target_power = 0
        target_blocker = False
        if action is not None and action.target_index is not None and 0 <= action.target_index < len(opponent.battle_zone):
            target = opponent.battle_zone[action.target_index].card
            target_power = target.power
            target_blocker = bool(target.blocker)
        destroy_spell_available = any(
            candidate.type == ActionType.CAST_SPELL
            and candidate.target_index is not None
            and candidate.target_index < len(opponent.battle_zone)
            and opponent.battle_zone[candidate.target_index].card.blocker
            for candidate in legal_actions
        )
        playable_summon_available = any(candidate.type == ActionType.SUMMON for candidate in legal_actions)
        own_can_attack_count = sum(1 for creature in player.battle_zone if not creature.tapped)
        return {
            "action_type": action.type.value if action is not None else "",
            "spell_effect": "",
            "target_power": target_power,
            "target_blocker": target_blocker,
            "own_hand_count": len(player.hand),
            "own_shields": len(player.shields),
            "own_mana": len(player.mana),
            "opponent_shields": len(opponent.shields),
            "opponent_blockers": sum(1 for creature in opponent.battle_zone if creature.card.blocker),
            "own_can_attack_count": own_can_attack_count,
            "destroy_spell_available": destroy_spell_available,
            "playable_summon_available": playable_summon_available,
            "turn": state.turn_number,
        }

    def _shaped_reward(self, before: dict[str, int | bool | str], info: dict) -> float:
        state = self.base_env.state
        if state is None or not before:
            return 0.0
        player = state.players[0]
        reward = 0.0
        action_type = str(before["action_type"])
        spell_effect = str(info.get("spell_effect") or "")
        won = state.done and state.winner == 0

        if info.get("spell_cast"):
            self._spell_cast_this_game = True
            if spell_effect == "DESTROY_TARGET":
                if bool(before["target_blocker"]):
                    self._removed_blocker_waiting_for_attack = True
                if int(before["target_power"]) >= 5000:
                    reward += self.reward_config.high_power_destroyed
                if int(before["target_power"]) < 3000 and not bool(before["target_blocker"]):
                    reward += self.reward_config.low_value_destroy
            if spell_effect == "MANA_BOOST":
                self._mana_boost_waiting_for_summon = True
            if spell_effect == "DRAW_1" and int(before["own_hand_count"]) <= 1 and len(player.hand) > int(before["own_hand_count"]):
                reward += self.reward_config.draw_low_hand_recovered
            if spell_effect == "GAIN_SHIELD" and int(before["own_shields"]) == 0 and len(player.shields) > 0:
                reward += self.reward_config.gain_shield_survived_turn
                self._gain_shield_turn = int(before["turn"])
            if bool(before["playable_summon_available"]) and spell_effect in {"DRAW_1", "GAIN_SHIELD"}:
                reward += self.reward_config.spell_over_development

        if (
            self._removed_blocker_waiting_for_attack
            and action_type in {ActionType.ATTACK_SHIELD.value, ActionType.ATTACK_PLAYER.value}
            and (info.get("shield_broken") or won)
        ):
            reward += self.reward_config.blocker_removed_attack_passed
            self._removed_blocker_waiting_for_attack = False

        if self._mana_boost_waiting_for_summon and action_type == ActionType.SUMMON.value and len(player.mana) >= 5:
            reward += self.reward_config.mana_boost_to_high_cost_summon
            self._mana_boost_waiting_for_summon = False

        if self._spell_cast_this_game and won:
            reward += self.reward_config.won_after_spell

        if (
            action_type == ActionType.END_ATTACK.value
            and int(before["opponent_shields"]) == 0
            and int(before["own_can_attack_count"]) > 0
        ):
            reward += self.reward_config.missed_lethal_without_spell

        if info.get("blocked") and bool(before["destroy_spell_available"]):
            reward += self.reward_config.blocker_left_attack_stopped

        return reward

