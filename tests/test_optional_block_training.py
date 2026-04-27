from pathlib import Path

from dm_ai_sim.actions import Action, ActionType
from dm_ai_sim.agents.ppo_optional_block_agent import PPOOptionalBlockAgent
from dm_ai_sim.agents.selfplay_optional_block_agent import SelfPlayOptionalBlockAgent
from dm_ai_sim.agents.selfplay_optional_block_finetuned_agent import SelfPlayOptionalBlockFineTunedAgent
from dm_ai_sim.card import Card
from dm_ai_sim.evaluate_optional_block import available_agents, main as evaluate_optional_block_main
from dm_ai_sim.optional_block_finetune_env import DuelMastersOptionalBlockFineTuneEnv, OptionalBlockRewardConfig
from dm_ai_sim.selfplay_env import DuelMastersSelfPlayEnv, SelfPlayConfig
from dm_ai_sim.state import Creature, Phase
from dm_ai_sim.train_ppo_optional_block import train as train_ppo_optional_block
from dm_ai_sim.train_selfplay_optional_block import train as train_selfplay_optional_block
from dm_ai_sim.train_selfplay_optional_block_finetune import train as train_optional_block_finetune


def test_optional_block_agents_handle_missing_models() -> None:
    env = DuelMastersSelfPlayEnv(SelfPlayConfig(seed=1, fixed_opponent="random"))
    env.reset()
    agents = [
        PPOOptionalBlockAgent(Path("missing_ppo_optional_block.zip")),
        SelfPlayOptionalBlockAgent(Path("missing_selfplay_optional_block.zip")),
        SelfPlayOptionalBlockFineTunedAgent(Path("missing_selfplay_optional_block_finetuned.zip")),
    ]

    for agent in agents:
        assert not agent.is_available
        assert agent.act(env) in env.base_env.legal_action_ids()


def test_evaluate_optional_block_handles_missing_models(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)

    agents = available_agents()
    evaluate_optional_block_main()

    assert [agent.name for agent in agents] == ["RandomAgent", "HeuristicAgent"]


def test_train_ppo_optional_block_short_run(tmp_path: Path) -> None:
    saved_path = train_ppo_optional_block(
        total_timesteps=16,
        model_path=tmp_path / "ppo_optional_block_test",
        verbose=0,
        n_steps=8,
        batch_size=8,
    )

    assert saved_path.exists()


def test_train_selfplay_optional_block_short_run(tmp_path: Path) -> None:
    pool_dir = tmp_path / "opponents_optional_block"
    saved_path = train_selfplay_optional_block(
        total_timesteps=16,
        model_path=tmp_path / "selfplay_optional_block_test",
        opponent_pool_dir=pool_dir,
        verbose=0,
        n_steps=8,
        batch_size=8,
    )

    assert saved_path.exists()
    assert (pool_dir / "ppo_snapshot_16.zip").exists()


def test_train_selfplay_optional_block_finetune_short_run(tmp_path: Path) -> None:
    pool_dir = tmp_path / "opponents_optional_block_finetuned"
    saved_path = train_optional_block_finetune(
        total_timesteps=16,
        model_path=tmp_path / "selfplay_optional_block_finetuned_test",
        opponent_pool_dir=pool_dir,
        verbose=0,
        n_steps=8,
        batch_size=8,
        reward_shaping=True,
    )

    assert saved_path.exists()
    assert (pool_dir / "ppo_snapshot_16.zip").exists()


def test_optional_block_reward_shaping_on_off_does_not_break_env() -> None:
    for enabled in (True, False):
        env = DuelMastersOptionalBlockFineTuneEnv(
            SelfPlayConfig(seed=2, fixed_opponent="heuristic"),
            reward_config=OptionalBlockRewardConfig(enabled=enabled),
        )
        _observation, info = env.reset()
        _next_observation, reward, terminated, truncated, next_info = env.step(info["legal_action_ids"][0])

        assert isinstance(reward, float)
        assert isinstance(terminated, bool)
        assert isinstance(truncated, bool)
        assert "legal_action_ids" in next_info


def test_pending_attack_mask_exposes_block_and_decline_to_optional_block_agent() -> None:
    env = DuelMastersSelfPlayEnv(SelfPlayConfig(seed=3, fixed_opponent="random"))
    env.reset()
    state = env.base_env.state
    assert state is not None
    state.phase = Phase.ATTACK
    state.turn_number = 2
    state.players[0].battle_zone.append(
        Creature(Card(id=9001, name="Attacker", cost=1, power=3000), summoned_turn=1)
    )
    state.players[1].battle_zone.append(
        Creature(Card(id=9002, name="Blocker", cost=1, power=4000, blocker=True), summoned_turn=1)
    )

    env.base_env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))

    assert env.base_env.legal_action_ids() == [242, 250]
    action_id = SelfPlayOptionalBlockAgent(Path("missing.zip")).act(env, player_id=1)
    assert action_id in {242, 250}
