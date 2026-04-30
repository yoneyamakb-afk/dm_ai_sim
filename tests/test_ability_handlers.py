from __future__ import annotations

from pathlib import Path

from dm_ai_sim.ability_handlers.g_strike import GStrikeHandler
from dm_ai_sim.ability_handlers.registry import AbilityRegistry, get_default_ability_registry
from dm_ai_sim.ability_handlers.speed_attacker import SpeedAttackerHandler
from dm_ai_sim.card import Card
from dm_ai_sim.events import Event, EventType
from dm_ai_sim.env import Env, EnvConfig
from dm_ai_sim.rules import can_attack
from dm_ai_sim.state import Creature, GameState, Phase, PlayerState


ROOT = Path(__file__).resolve().parents[1]


def test_event_type_and_event_dataclass_can_be_created() -> None:
    event = Event(EventType.ATTACK_DECLARED, player=0, opponent=1, payload={"attacker_index": 0})

    assert event.type == EventType.ATTACK_DECLARED
    assert event.payload["attacker_index"] == 0


def test_registry_registers_and_finds_handlers_by_tag() -> None:
    registry = AbilityRegistry()
    handler = SpeedAttackerHandler()

    registry.register(handler)

    assert registry.get_handler("SPEED_ATTACKER") is handler
    assert registry.get_handlers_for_tags(("SPEED_ATTACKER",)) == [handler]


def test_default_registry_finds_handlers_for_card_tags() -> None:
    card = Card(id=1, name="Speed", cost=2, power=1000, civilizations=("FIRE",), ability_tags=("SPEED_ATTACKER",))
    handlers = get_default_ability_registry().get_handlers_for_card(card)

    assert any(isinstance(handler, SpeedAttackerHandler) for handler in handlers)


def test_speed_attacker_handler_can_handle_card_and_creature() -> None:
    card = Card(id=1, name="Speed", cost=2, power=1000, civilizations=("FIRE",), ability_tags=("SPEED_ATTACKER",))
    creature = Creature(card=card, summoned_turn=1)
    handler = SpeedAttackerHandler()

    assert handler.can_handle(card)
    assert handler.can_handle(creature)


def test_speed_attacker_can_attack_with_summoning_sickness() -> None:
    state = _attack_state(
        Creature(
            card=Card(id=1, name="Speed", cost=2, power=1000, civilizations=("FIRE",), ability_tags=("SPEED_ATTACKER",)),
            summoned_turn=1,
        )
    )

    assert can_attack(0, state)


def test_speed_attacker_cannot_attack_when_prevented_this_turn() -> None:
    state = _attack_state(
        Creature(
            card=Card(id=1, name="Speed", cost=2, power=1000, civilizations=("FIRE",), ability_tags=("SPEED_ATTACKER",)),
            summoned_turn=1,
            cannot_attack_this_turn=True,
        )
    )

    assert not can_attack(0, state)


def test_gstrike_handler_prefers_attack_capable_creature() -> None:
    env = _handler_env()
    state = env.state
    assert state is not None
    state.players[0].battle_zone = [
        Creature(card=Card(id=11, name="Old Big", cost=5, power=9000, civilizations=("FIRE",)), summoned_turn=state.turn_number),
        Creature(
            card=Card(id=12, name="Speed Small", cost=2, power=1000, civilizations=("FIRE",), ability_tags=("SPEED_ATTACKER",)),
            summoned_turn=state.turn_number,
        ),
    ]

    assert GStrikeHandler().choose_target(env, defender_player=1, attacker_player=0) == 1


def test_architecture_docs_exist() -> None:
    assert (ROOT / "ARCHITECTURE_RULE_ENGINE.md").exists()
    assert (ROOT / "ABILITY_HANDLER_MIGRATION.md").exists()


def _attack_state(creature: Creature) -> GameState:
    return GameState(
        players=[
            PlayerState(deck=[], battle_zone=[creature]),
            PlayerState(deck=[]),
        ],
        current_player=0,
        phase=Phase.ATTACK,
        turn_number=1,
    )


def _handler_env() -> Env:
    deck = [Card(id=1000 + i, name=f"C{i}", cost=1, power=1000, civilizations=("FIRE",)) for i in range(40)]
    env = Env(deck0=list(deck), deck1=list(deck), config=EnvConfig(seed=1))
    env.reset()
    state = env.state
    assert state is not None
    state.current_player = 0
    state.phase = Phase.ATTACK
    return env
