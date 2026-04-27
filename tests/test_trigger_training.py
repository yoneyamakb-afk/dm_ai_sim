from pathlib import Path

from dm_ai_sim.actions import Action, ActionType
from dm_ai_sim.agents.ppo_trigger_agent import PPOTriggerAgent
from dm_ai_sim.agents.selfplay_trigger_agent import SelfPlayTriggerAgent
from dm_ai_sim.agents.selfplay_trigger_finetuned_agent import SelfPlayTriggerFineTunedAgent
from dm_ai_sim.card import Card
from dm_ai_sim.evaluate_trigger import available_agents, main as evaluate_trigger_main
from dm_ai_sim.selfplay_env import DuelMastersSelfPlayEnv, SelfPlayConfig
from dm_ai_sim.state import Creature, Phase
from dm_ai_sim.train_ppo_trigger import train as train_ppo_trigger
from dm_ai_sim.train_selfplay_trigger import train as train_selfplay_trigger
from dm_ai_sim.train_selfplay_trigger_finetune import train as train_trigger_finetune
from dm_ai_sim.trigger_finetune_env import DuelMastersTriggerFineTuneEnv, TriggerRewardConfig


def test_trigger_agents_handle_missing_models() -> None:
    env = DuelMastersSelfPlayEnv(SelfPlayConfig(seed=1, fixed_opponent="random"))
    env.reset()
    agents = [
        PPOTriggerAgent(Path("missing_ppo_trigger.zip")),
        SelfPlayTriggerAgent(Path("missing_selfplay_trigger.zip")),
        SelfPlayTriggerFineTunedAgent(Path("missing_selfplay_trigger_finetuned.zip")),
    ]

    for agent in agents:
        assert not agent.is_available
        assert agent.act(env) in env.base_env.legal_action_ids()


def test_evaluate_trigger_handles_missing_models(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)

    agents = available_agents()
    evaluate_trigger_main()

    assert [agent.name for agent in agents] == ["RandomAgent", "HeuristicAgent"]


def test_train_ppo_trigger_short_run(tmp_path: Path) -> None:
    saved_path = train_ppo_trigger(
        total_timesteps=16,
        model_path=tmp_path / "ppo_trigger_test",
        verbose=0,
        n_steps=8,
        batch_size=8,
    )

    assert saved_path.exists()


def test_train_selfplay_trigger_short_run(tmp_path: Path) -> None:
    pool_dir = tmp_path / "opponents_trigger"
    saved_path = train_selfplay_trigger(
        total_timesteps=16,
        model_path=tmp_path / "selfplay_trigger_test",
        opponent_pool_dir=pool_dir,
        verbose=0,
        n_steps=8,
        batch_size=8,
    )

    assert saved_path.exists()
    assert (pool_dir / "ppo_snapshot_16.zip").exists()


def test_train_selfplay_trigger_finetune_short_run(tmp_path: Path) -> None:
    pool_dir = tmp_path / "opponents_trigger_finetuned"
    saved_path = train_trigger_finetune(
        total_timesteps=16,
        model_path=tmp_path / "selfplay_trigger_finetuned_test",
        opponent_pool_dir=pool_dir,
        verbose=0,
        n_steps=8,
        batch_size=8,
        reward_shaping=True,
    )

    assert saved_path.exists()
    assert (pool_dir / "ppo_snapshot_16.zip").exists()


def test_trigger_reward_shaping_on_off_does_not_break_env() -> None:
    for enabled in (True, False):
        env = DuelMastersTriggerFineTuneEnv(
            SelfPlayConfig(seed=2, fixed_opponent="heuristic"),
            reward_config=TriggerRewardConfig(enabled=enabled),
        )
        _observation, info = env.reset()
        _next_observation, reward, terminated, truncated, next_info = env.step(info["legal_action_ids"][0])

        assert isinstance(reward, float)
        assert isinstance(terminated, bool)
        assert isinstance(truncated, bool)
        assert "legal_action_ids" in next_info


def test_trigger_after_decline_clears_pending_and_moves_attacker_to_graveyard() -> None:
    env = DuelMastersSelfPlayEnv(SelfPlayConfig(seed=3, fixed_opponent="random"))
    env.reset()
    state = env.base_env.state
    assert state is not None
    state.phase = Phase.ATTACK
    state.turn_number = 2
    state.players[0].battle_zone.clear()
    state.players[1].battle_zone.clear()
    attacker = Card(id=9001, name="Attacker", cost=1, power=3000)
    trigger = Card(
        id=9002,
        name="Destroy Trigger",
        cost=1,
        power=0,
        shield_trigger=True,
        card_type="SPELL",
        trigger_effect="DESTROY_ATTACKER",
    )
    state.players[0].battle_zone.append(Creature(attacker, summoned_turn=1))
    state.players[1].battle_zone.append(
        Creature(Card(id=9003, name="Blocker", cost=1, power=1000, blocker=True), summoned_turn=1)
    )
    state.players[1].shields = [trigger]

    env.base_env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))
    _obs, _reward, _done, info = env.base_env.step(Action(ActionType.DECLINE_BLOCK))

    assert state.pending_attack is None
    assert info["trigger_activated"]
    assert info["attacker_destroyed_by_trigger"]
    assert attacker in state.players[0].graveyard


def test_summon_self_trigger_creature_can_act_on_later_turn() -> None:
    env = DuelMastersSelfPlayEnv(SelfPlayConfig(seed=4, fixed_opponent="random"))
    env.reset()
    state = env.base_env.state
    assert state is not None
    state.phase = Phase.ATTACK
    state.turn_number = 2
    trigger_creature = Card(
        id=9010,
        name="Trigger Creature",
        cost=1,
        power=2000,
        shield_trigger=True,
        card_type="CREATURE",
        trigger_effect="SUMMON_SELF",
    )
    state.players[0].battle_zone = [Creature(Card(id=9011, name="Attacker", cost=1, power=3000), summoned_turn=1)]
    state.players[1].battle_zone.clear()
    state.players[1].shields = [trigger_creature]

    env.base_env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))
    summoned = state.players[1].battle_zone[-1]
    assert summoned.card == trigger_creature
    assert summoned.summoned_turn == state.turn_number
    state.current_player = 1
    state.turn_number += 1
    state.phase = Phase.ATTACK
    assert any(action.type == ActionType.ATTACK_SHIELD for action in env.base_env.legal_actions())


def test_gain_shield_trigger_keeps_shield_count() -> None:
    env = DuelMastersSelfPlayEnv(SelfPlayConfig(seed=5, fixed_opponent="random"))
    env.reset()
    state = env.base_env.state
    assert state is not None
    state.phase = Phase.ATTACK
    state.turn_number = 2
    state.players[0].battle_zone = [Creature(Card(id=9020, name="Attacker", cost=1, power=3000), summoned_turn=1)]
    state.players[1].battle_zone.clear()
    state.players[1].shields = [
        Card(id=9021, name="Gain Shield", cost=1, power=0, shield_trigger=True, card_type="SPELL", trigger_effect="GAIN_SHIELD")
    ]

    _obs, _reward, _done, info = env.base_env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))

    assert info["trigger_effect"] == "GAIN_SHIELD"
    assert len(state.players[1].shields) == 1
