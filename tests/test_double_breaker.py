from __future__ import annotations

from pathlib import Path

from dm_ai_sim.action_encoder import encode_action
from dm_ai_sim.actions import Action, ActionType
from dm_ai_sim.agents.heuristic_agent import HeuristicAgent
from dm_ai_sim.analyze_double_breaker_logs import main as analyze_double_breaker_logs_main
from dm_ai_sim.card import Card, CardSide
from dm_ai_sim.card_database import load_card_database
from dm_ai_sim.diagnose_reference_deck_02 import main as diagnose_reference_deck_02_main
from dm_ai_sim.env import Env, EnvConfig
from dm_ai_sim.evaluate_double_breaker import main as evaluate_double_breaker_main
from dm_ai_sim.state import Creature, Phase


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_CARDS = ROOT / "data/cards/reference_cards.json"


def test_double_breaker_tag_sets_breaker_count() -> None:
    card = _card(1, "Double", tags=("DOUBLE_BREAKER",))
    normal = _card(2, "Normal")

    assert card.breaker_count == 2
    assert normal.breaker_count == 1


def test_runtime_red_girazon_and_red_zone_are_double_breakers() -> None:
    database = load_card_database(REFERENCE_CARDS)

    assert database.to_runtime_card("DM_REF_015", strict=False).breaker_count == 2
    assert database.to_runtime_card("DM_REF_016", strict=False).breaker_count == 2


def test_double_breaker_attack_breaks_two_shields() -> None:
    attacker = _card(10, "Double Attacker", tags=("DOUBLE_BREAKER",))
    shields = [_card(20, "Bottom Shield"), _card(21, "Top Shield"), _card(22, "Third Shield")]
    env = _attack_env(attacker, shields)

    _obs, _reward, _done, info = env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))

    assert info["breaker_count"] == 2
    assert info["shields_to_break"] == 2
    assert info["shields_broken_count"] == 2
    assert info["multi_break"] is True
    assert [result["broken_card_name"] for result in info["shield_break_results"]] == ["Third Shield", "Top Shield"]
    assert len(env.state.players[1].shields) == 1


def test_double_breaker_with_one_shield_breaks_only_one() -> None:
    attacker = _card(30, "Double Attacker", tags=("DOUBLE_BREAKER",))
    env = _attack_env(attacker, [_card(31, "Only Shield")])

    _obs, _reward, _done, info = env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))

    assert info["breaker_count"] == 2
    assert info["shields_to_break"] == 1
    assert info["shields_broken_count"] == 1
    assert info["multi_break"] is False


def test_blocked_double_breaker_does_not_break_shields() -> None:
    attacker = _card(40, "Double Attacker", tags=("DOUBLE_BREAKER",))
    shields = [_card(41, "Shield A"), _card(42, "Shield B")]
    env = _attack_env(attacker, shields, with_blocker=True)

    env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))
    _obs, _reward, _done, info = env.step(Action(ActionType.BLOCK, blocker_index=0))

    assert info["blocked"] is True
    assert info.get("shields_broken_count", 0) == 0
    assert len(env.state.players[1].shields) == 2


def test_double_breaker_destroy_trigger_does_not_stop_second_broken_shield() -> None:
    attacker = _card(50, "Double Attacker", tags=("DOUBLE_BREAKER",))
    normal = _card(51, "Normal After Destroy")
    destroy = Card(id=52, name="Destroy Trigger", cost=1, power=0, shield_trigger=True, card_type="SPELL", trigger_effect="DESTROY_ATTACKER")
    extra = _card(53, "Other Creature", tags=("SPEED_ATTACKER",))
    env = _attack_env(attacker, [normal, destroy], extra_attackers=[extra])

    _obs, _reward, _done, info = env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))

    assert [result["broken_card_name"] for result in info["shield_break_results"]] == ["Destroy Trigger", "Normal After Destroy"]
    assert info["attacker_destroyed_by_trigger"] is True
    assert normal in env.state.players[1].hand
    assert [creature.card.name for creature in env.state.players[0].battle_zone] == ["Other Creature"]


def test_double_breaker_processes_gstrike_and_normal_shield() -> None:
    database = load_card_database(REFERENCE_CARDS)
    prin = database.to_runtime_card("DM_REF_020", strict=True)
    attacker = _card(60, "Double Attacker", tags=("DOUBLE_BREAKER",))
    speed = _card(61, "Ready Speed", tags=("SPEED_ATTACKER",))
    env = _attack_env(attacker, [_card(62, "Normal Shield"), prin], extra_attackers=[speed])

    _obs, _reward, _done, info = env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))

    assert info["g_strike_activated"] is True
    assert info["g_strike_target_name"] == "Ready Speed"
    assert info["shield_break_results"][0]["g_strike_activated"] is True
    assert info["shield_break_results"][1]["card_added_to_hand"] is True


def test_twinpact_top_side_can_be_double_breaker() -> None:
    twin = Card(
        id=70,
        name="Twin",
        cost=5,
        power=5000,
        civilizations=("FIRE",),
        is_twinpact=True,
        top_side=CardSide(
            name="Twin Top",
            cost=5,
            civilizations=("FIRE",),
            card_type="CREATURE",
            power=5000,
            ability_tags=("DOUBLE_BREAKER",),
        ),
        bottom_side=CardSide(
            name="Twin Bottom",
            cost=2,
            civilizations=("FIRE",),
            card_type="SPELL",
            power=None,
        ),
    )

    assert twin.side_as_card("top").breaker_count == 2


def test_revolution_change_red_girazon_breaks_two_shields() -> None:
    env = _revolution_env()

    env.step(Action(ActionType.REVOLUTION_CHANGE, hand_index=0, attacker_index=0))
    _obs, _reward, _done, info = env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))

    assert info["breaker_count"] == 2
    assert info["shields_broken_count"] == 2
    assert info["multi_break"] is True


def test_invasion_red_zone_z_breaks_two_shields() -> None:
    env = _invasion_env()

    env.step(Action(ActionType.INVASION, hand_index=0, attacker_index=0))
    _obs, _reward, _done, info = env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))

    assert info["breaker_count"] == 2
    assert info["shields_broken_count"] == 2
    assert info["multi_break"] is True


def test_double_breaker_attack_mask_still_encodes_normally() -> None:
    attacker = _card(80, "Double Attacker", tags=("DOUBLE_BREAKER",))
    env = _attack_env(attacker, [_card(81, "Shield A"), _card(82, "Shield B")], include_action_mask=True)
    action = Action(ActionType.ATTACK_SHIELD, attacker_index=0)
    observation = env.get_observation(include_action_mask=True)

    assert action in env.legal_actions()
    assert observation["action_mask"][encode_action(action)] == 1


def test_heuristic_agent_prefers_higher_breaker_count_for_shield_attack() -> None:
    env = _attack_env(
        _card(90, "Normal Attacker"),
        [_card(91, "Shield A"), _card(92, "Shield B")],
        extra_attackers=[_card(93, "Double Attacker", tags=("DOUBLE_BREAKER",))],
    )

    action = HeuristicAgent().act(env.legal_actions(), env.get_observation())

    assert action.type == ActionType.ATTACK_SHIELD
    assert action.attacker_index == 1


def test_double_breaker_clis_run(tmp_path: Path, capsys) -> None:
    evaluate_double_breaker_main(games=1)
    assert "double_breaker_attacks:" in capsys.readouterr().out

    analyze_double_breaker_logs_main(games=1, output_path=tmp_path / "double_breaker.jsonl")
    output = capsys.readouterr().out
    assert "multi_break_batches:" in output
    assert (tmp_path / "double_breaker.jsonl").exists()


def test_diagnose_double_breaker_is_implemented(capsys) -> None:
    diagnose_reference_deck_02_main()
    output = capsys.readouterr().out
    unsupported_section = output.split("unsupported_tag_summary:", 1)[1].split("unsupported_counts_by_tag:", 1)[0]

    assert "DOUBLE_BREAKER" not in unsupported_section


def _attack_env(
    attacker: Card,
    shields: list[Card],
    extra_attackers: list[Card] | None = None,
    with_blocker: bool = False,
    include_action_mask: bool = False,
) -> Env:
    deck = [_card(1000 + index, f"D{index}") for index in range(40)]
    env = Env(deck0=list(deck), deck1=list(deck), config=EnvConfig(seed=1, include_action_mask=include_action_mask))
    env.reset()
    state = env.state
    assert state is not None
    state.current_player = 0
    state.phase = Phase.ATTACK
    state.turn_number = 2
    attack_cards = [attacker] + list(extra_attackers or [])
    state.players[0].battle_zone = [
        Creature(card=card, tapped=False, summoned_turn=1 if "SPEED_ATTACKER" not in card.ability_tags else state.turn_number)
        for card in attack_cards
    ]
    state.players[1].battle_zone = []
    state.players[1].shields = list(shields)
    if with_blocker:
        state.players[1].battle_zone = [Creature(card=_card(900, "Blocker", blocker=True), tapped=False, summoned_turn=1)]
    return env


def _revolution_env() -> Env:
    database = load_card_database(REFERENCE_CARDS)
    red = database.to_runtime_card("DM_REF_015", strict=False)
    hachiko = database.to_runtime_card("DM_REF_014", strict=True)
    env = _attack_env(hachiko, [_card(2000, "Shield A"), _card(2001, "Shield B"), _card(2002, "Shield C")])
    state = env.state
    assert state is not None
    state.players[0].hand = [red]
    state.players[0].mana = []
    return env


def _invasion_env() -> Env:
    database = load_card_database(REFERENCE_CARDS)
    red_zone = database.to_runtime_card("DM_REF_016", strict=False)
    hachiko = database.to_runtime_card("DM_REF_014", strict=True)
    env = _attack_env(hachiko, [_card(3000, "Shield A"), _card(3001, "Shield B"), _card(3002, "Shield C")])
    state = env.state
    assert state is not None
    state.players[0].hand = [red_zone]
    state.players[0].mana = []
    return env


def _card(card_id: int, name: str, tags: tuple[str, ...] = (), blocker: bool = False) -> Card:
    return Card(id=card_id, name=name, cost=1, power=1000, civilizations=("FIRE",), ability_tags=tags, blocker=blocker)
