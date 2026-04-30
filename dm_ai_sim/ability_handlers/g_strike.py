from __future__ import annotations

from typing import Any

from dm_ai_sim.ability_handlers.base import AbilityHandler


class GStrikeHandler(AbilityHandler):
    tag = "G_STRIKE"

    def can_handle(self, card_or_creature: Any) -> bool:
        card = getattr(card_or_creature, "card", card_or_creature)
        if self.tag in tuple(getattr(card, "ability_tags", ()) or ()):
            return True
        top_side = getattr(card, "top_side", None)
        bottom_side = getattr(card, "bottom_side", None)
        return (
            top_side is not None
            and self.tag in tuple(getattr(top_side, "ability_tags", ()) or ())
        ) or (
            bottom_side is not None
            and self.tag in tuple(getattr(bottom_side, "ability_tags", ()) or ())
        )

    def choose_target(self, env: Any, defender_player: int, attacker_player: int) -> int | None:
        state = env.state
        if state is None:
            return None
        candidates: list[tuple[tuple[int, int, int, int], int]] = []
        for index, creature in enumerate(state.players[attacker_player].battle_zone):
            attack_capable = int(_creature_can_attack_now(creature, state.turn_number))
            likely_chain = int("SPEED_ATTACKER" in creature.card.ability_tags or creature.card.name == "特攻の忠剣ハチ公")
            candidates.append(((attack_capable, likely_chain, creature.card.power, -index), index))
        if not candidates:
            return None
        return max(candidates, key=lambda item: item[0])[1]

    def apply_g_strike(self, env: Any, card: Any, defender_player: int, attacker_player: int, info: dict[str, Any]) -> dict[str, Any]:
        state = env.state
        target_index = self.choose_target(env, defender_player, attacker_player)
        info.update(
            {
                "g_strike_activated": True,
                "g_strike_card_name": card.name,
                "g_strike_target_index": target_index,
                "g_strike_target_name": None,
                "g_strike_prevented_attack": False,
                "g_strike_source_zone": "shield",
            }
        )
        if state is None or target_index is None:
            return info
        target = state.players[attacker_player].battle_zone[target_index]
        target.cannot_attack_this_turn = True
        info["g_strike_target_name"] = target.card.name
        info["g_strike_prevented_attack"] = True
        return info


def _creature_can_attack_now(creature: Any, turn_number: int) -> bool:
    tags = set(creature.card.ability_tags)
    has_speed_attacker = "SPEED_ATTACKER" in tags
    has_attack_ready_evolution = bool({"INVASION", "ATTACKING_CREATURE_EVOLUTION"} & tags)
    return (
        not creature.tapped
        and not creature.cannot_attack_this_turn
        and (has_speed_attacker or has_attack_ready_evolution or creature.summoned_turn < turn_number)
    )
