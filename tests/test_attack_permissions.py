from __future__ import annotations

from dm_ai_sim.ability_handlers.base import AbilityHandler
from dm_ai_sim.ability_handlers.registry import AbilityRegistry
from dm_ai_sim.ability_handlers.speed_attacker import SpeedAttackerHandler
from dm_ai_sim.actions import Action, ActionType
from dm_ai_sim.agents.heuristic_agent import HeuristicAgent
from dm_ai_sim.attack_permissions import (
    can_creature_attack,
    can_creature_attack_in_state,
    get_attackable_creatures,
    get_gstrike_targets,
)
from dm_ai_sim.card import Card
from dm_ai_sim.env import Env, EnvConfig
from dm_ai_sim.rules import legal_actions
from dm_ai_sim.state import Creature, GameState, Phase, PlayerState


def test_common_attack_permission_allows_speed_attacker_on_summon_turn() -> None:
    env = _permission_env([
        Creature(card=_card("Speed", tags=("SPEED_ATTACKER",)), summoned_turn=1),
    ])

    assert can_creature_attack(env, 0, 0)


def test_common_attack_permission_false_conditions_win() -> None:
    env = _permission_env([
        Creature(card=_card("Speed", tags=("SPEED_ATTACKER",)), summoned_turn=1, cannot_attack_this_turn=True),
        Creature(card=_card("Tapped Speed", tags=("SPEED_ATTACKER",)), summoned_turn=1, tapped=True),
    ])

    assert not can_creature_attack(env, 0, 0)
    assert not can_creature_attack(env, 0, 1)


def test_common_attack_permission_blocks_summoning_sickness_for_normal_creature() -> None:
    env = _permission_env([
        Creature(card=_card("Normal"), summoned_turn=1),
    ])

    assert not can_creature_attack(env, 0, 0)


def test_attack_permission_handler_false_overrides_allowing_handler() -> None:
    registry = AbilityRegistry()
    registry.register(SpeedAttackerHandler())
    registry.register(_NoAttackHandler())
    state = _permission_state([
        Creature(card=_card("Locked Speed", tags=("SPEED_ATTACKER", "NO_ATTACK_TEST")), summoned_turn=1),
    ])

    assert not can_creature_attack_in_state(state, 0, 0, registry=registry)


def test_gstrike_targets_use_common_attack_permission() -> None:
    env = _permission_env([
        Creature(card=_card("Tapped Speed", tags=("SPEED_ATTACKER",)), summoned_turn=1, tapped=True),
        Creature(card=_card("Sick Normal"), summoned_turn=1),
        Creature(card=_card("Ready Speed", tags=("SPEED_ATTACKER",)), summoned_turn=1),
    ])

    assert get_gstrike_targets(env, 0) == [2]


def test_legal_actions_match_common_attackable_indices() -> None:
    env = _permission_env([
        Creature(card=_card("Speed", tags=("SPEED_ATTACKER",)), summoned_turn=1),
        Creature(card=_card("Sick Normal"), summoned_turn=1),
        Creature(card=_card("Old Normal"), summoned_turn=0),
    ])
    assert env.state is not None
    attackable = set(get_attackable_creatures(env, 0))
    legal_attackers = {
        action.attacker_index
        for action in legal_actions(env.state)
        if action.type in {ActionType.ATTACK_CREATURE, ActionType.ATTACK_SHIELD, ActionType.ATTACK_PLAYER}
    }

    assert legal_attackers == attackable


def test_heuristic_agent_does_not_choose_unattackable_creature() -> None:
    env = _permission_env([
        Creature(card=_card("Stopped Speed", tags=("SPEED_ATTACKER",)), summoned_turn=1, cannot_attack_this_turn=True),
        Creature(card=_card("Ready Speed", tags=("SPEED_ATTACKER",)), summoned_turn=1),
    ])
    observation = env.get_observation()
    malformed_actions = [
        Action(ActionType.ATTACK_SHIELD, attacker_index=0),
        Action(ActionType.ATTACK_SHIELD, attacker_index=1),
    ]

    action = HeuristicAgent().act(malformed_actions, observation)

    assert action.attacker_index == 1


class _NoAttackHandler(AbilityHandler):
    tag = "NO_ATTACK_TEST"

    def modifies_attack_permission(self, creature, game_state, player_id) -> bool | None:
        return False if self.can_handle(creature) else None


def _permission_env(creatures: list[Creature]) -> Env:
    deck = [_card(f"D{i}", card_id=1000 + i) for i in range(40)]
    env = Env(deck0=list(deck), deck1=list(deck), config=EnvConfig(seed=1))
    env.reset()
    state = env.state
    assert state is not None
    state.current_player = 0
    state.phase = Phase.ATTACK
    state.players[0].battle_zone = creatures
    state.players[1].shields = [_card("Shield", card_id=9000)]
    return env


def _permission_state(creatures: list[Creature]) -> GameState:
    return GameState(
        players=[
            PlayerState(deck=[], battle_zone=creatures),
            PlayerState(deck=[], shields=[_card("Shield", card_id=9000)]),
        ],
        current_player=0,
        phase=Phase.ATTACK,
        turn_number=1,
    )


def _card(name: str, card_id: int = 1, tags: tuple[str, ...] = ()) -> Card:
    return Card(id=card_id, name=name, cost=1, power=1000, civilizations=("FIRE",), ability_tags=tags)
