from pathlib import Path

from dm_ai_sim.actions import Action, ActionType
from dm_ai_sim.analyze_mana_logs import main as analyze_mana_main
from dm_ai_sim.card import Card
from dm_ai_sim.env import Env, EnvConfig
from dm_ai_sim.evaluate_mana import main as evaluate_mana_main
from dm_ai_sim.gym_env import DuelMastersGymEnv
from dm_ai_sim.selfplay_env import DuelMastersSelfPlayEnv, SelfPlayConfig
from dm_ai_sim.state import Creature, ManaCard, Phase


def _env_with_hand(card: Card) -> Env:
    env = Env(config=EnvConfig(seed=1, include_action_mask=True))
    env.reset()
    state = env.state
    assert state is not None
    state.players[0].hand = [card]
    state.players[0].mana.clear()
    state.phase = Phase.MAIN
    state.current_player = 0
    return env


def test_single_color_enters_mana_untapped() -> None:
    card = Card(id=1, name="Fire", cost=1, power=1000, civilizations=("FIRE",))
    env = _env_with_hand(card)
    env.step(Action(ActionType.CHARGE_MANA, card_index=0))
    assert not env.state.players[0].mana[0].tapped


def test_multicolor_enters_mana_tapped() -> None:
    card = Card(id=2, name="Fire Nature", cost=1, power=1000, civilizations=("FIRE", "NATURE"))
    env = _env_with_hand(card)
    env.step(Action(ActionType.CHARGE_MANA, card_index=0))
    assert env.state.players[0].mana[0].tapped


def test_colorless_enters_mana_untapped() -> None:
    card = Card(id=3, name="Colorless", cost=1, power=1000, civilizations=("COLORLESS",))
    env = _env_with_hand(card)
    env.step(Action(ActionType.CHARGE_MANA, card_index=0))
    assert not env.state.players[0].mana[0].tapped


def test_single_color_requires_matching_civilization() -> None:
    card = Card(id=4, name="Fire Creature", cost=1, power=1000, civilizations=("FIRE",))
    env = _env_with_hand(card)
    env.state.players[0].mana = [ManaCard(Card(id=5, name="Nature Mana", cost=1, power=1000, civilizations=("NATURE",)))]
    assert all(action.type != ActionType.SUMMON for action in env.legal_actions())


def test_multicolor_requires_all_civilizations() -> None:
    card = Card(id=6, name="Fire Nature Creature", cost=2, power=1000, civilizations=("FIRE", "NATURE"))
    env = _env_with_hand(card)
    env.state.players[0].mana = [
        ManaCard(Card(id=7, name="Fire Mana", cost=1, power=1000, civilizations=("FIRE",))),
        ManaCard(Card(id=8, name="Water Mana", cost=1, power=1000, civilizations=("WATER",))),
    ]
    assert all(action.type != ActionType.SUMMON for action in env.legal_actions())


def test_one_multicolor_mana_cannot_satisfy_two_required_civilizations() -> None:
    card = Card(id=9, name="Fire Nature Creature", cost=2, power=1000, civilizations=("FIRE", "NATURE"))
    env = _env_with_hand(card)
    env.state.players[0].mana = [
        ManaCard(Card(id=10, name="Dual Mana", cost=1, power=1000, civilizations=("FIRE", "NATURE"))),
        ManaCard(Card(id=11, name="Colorless Mana", cost=1, power=1000, civilizations=("COLORLESS",))),
    ]
    assert all(action.type != ActionType.SUMMON for action in env.legal_actions())


def test_cost_enough_but_civilization_missing_blocks_spell() -> None:
    spell = Card(id=12, name="Fire Spell", cost=1, power=0, card_type="SPELL", spell_effect="DRAW_1", civilizations=("FIRE",))
    env = _env_with_hand(spell)
    env.state.players[0].mana = [ManaCard(Card(id=13, name="Nature Mana", cost=1, power=1000, civilizations=("NATURE",)))]
    assert all(action.type != ActionType.CAST_SPELL for action in env.legal_actions())


def test_payment_taps_correct_number_and_legal_step_agree() -> None:
    card = Card(id=14, name="Fire Nature Creature", cost=2, power=1000, civilizations=("FIRE", "NATURE"))
    env = _env_with_hand(card)
    env.state.players[0].mana = [
        ManaCard(Card(id=15, name="Fire Mana", cost=1, power=1000, civilizations=("FIRE",))),
        ManaCard(Card(id=16, name="Nature Mana", cost=1, power=1000, civilizations=("NATURE",))),
        ManaCard(Card(id=17, name="Dual Mana", cost=1, power=1000, civilizations=("FIRE", "NATURE"))),
    ]
    summon = next(action for action in env.legal_actions() if action.type == ActionType.SUMMON)
    env.step(summon)
    assert sum(1 for mana in env.state.players[0].mana if mana.tapped) == 2
    assert not env.state.players[0].mana[2].tapped


def test_shield_trigger_ignores_civilization_payment() -> None:
    env = Env(config=EnvConfig(seed=2))
    env.reset()
    state = env.state
    assert state is not None
    state.phase = Phase.ATTACK
    state.turn_number = 2
    state.players[0].battle_zone.clear()
    state.players[1].battle_zone.clear()
    state.players[0].battle_zone.append(
        Creature(
            Card(id=18, name="Attacker", cost=1, power=3000, civilizations=("FIRE",)),
            summoned_turn=1,
        )
    )
    state.players[1].mana.clear()
    state.players[1].shields = [
        Card(
            id=19,
            name="Unpayable Trigger",
            cost=5,
            power=0,
            card_type="SPELL",
            shield_trigger=True,
            trigger_effect="GAIN_SHIELD",
            civilizations=("DARKNESS",),
        )
    ]
    _obs, _reward, _done, info = env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))
    assert info["trigger_activated"]


def test_action_mask_reflects_civilization_payment() -> None:
    card = Card(id=20, name="Fire Creature", cost=1, power=1000, civilizations=("FIRE",))
    env = _env_with_hand(card)
    env.state.players[0].mana = [ManaCard(Card(id=21, name="Nature Mana", cost=1, power=1000, civilizations=("NATURE",)))]
    obs = env.get_observation()
    assert sum(obs["action_mask"][40:80]) == 0


def test_gym_and_selfplay_survive_civilization_payment() -> None:
    gym = DuelMastersGymEnv()
    _obs, info = gym.reset()
    _obs, reward, terminated, truncated, _info = gym.step(info["legal_action_ids"][0])
    assert isinstance(reward, float)
    assert isinstance(terminated, bool)
    assert isinstance(truncated, bool)

    selfplay = DuelMastersSelfPlayEnv(SelfPlayConfig(seed=3, fixed_opponent="random"))
    _obs, info = selfplay.reset()
    _obs, reward, terminated, truncated, _info = selfplay.step(info["legal_action_ids"][0])
    assert isinstance(reward, float)
    assert isinstance(terminated, bool)
    assert isinstance(truncated, bool)


def test_analyze_and_evaluate_mana_run(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DM_EVALUATE_MANA_GAMES", "2")
    analyze_mana_main(games=1, output_path=tmp_path / "mana.jsonl")
    evaluate_mana_main()
    assert (tmp_path / "mana.jsonl").exists()
