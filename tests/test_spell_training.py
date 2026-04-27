from pathlib import Path

from dm_ai_sim.agents.ppo_spell_agent import PPOSpellAgent
from dm_ai_sim.agents.selfplay_spell_agent import SelfPlaySpellAgent
from dm_ai_sim.agents.selfplay_spell_finetuned_agent import SelfPlaySpellFineTunedAgent
from dm_ai_sim.analyze_spell_logs import analyze_game
from dm_ai_sim.evaluate_spell import main as evaluate_spell_main
from dm_ai_sim.selfplay_env import DuelMastersSelfPlayEnv, SelfPlayConfig
from dm_ai_sim.spell_finetune_env import DuelMastersSpellFineTuneEnv, SpellRewardConfig
from dm_ai_sim.train_ppo_spell import train as train_ppo_spell
from dm_ai_sim.train_selfplay_spell import train as train_selfplay_spell
from dm_ai_sim.train_selfplay_spell_finetune import train as train_spell_finetune


def test_spell_agents_handle_missing_models() -> None:
    env = DuelMastersSelfPlayEnv(SelfPlayConfig(seed=1, fixed_opponent="random"))
    env.reset()
    agents = [
        PPOSpellAgent(Path("missing_ppo_spell.zip")),
        SelfPlaySpellAgent(Path("missing_selfplay_spell.zip")),
        SelfPlaySpellFineTunedAgent(Path("missing_selfplay_spell_finetuned.zip")),
    ]

    for agent in agents:
        assert not agent.is_available
        assert agent.act(env) in env.base_env.legal_action_ids()


def test_train_ppo_spell_short_run(tmp_path: Path) -> None:
    saved_path = train_ppo_spell(
        total_timesteps=16,
        model_path=tmp_path / "ppo_spell_test",
        verbose=0,
        n_steps=8,
        batch_size=8,
    )

    assert saved_path.exists()


def test_train_selfplay_spell_short_run(tmp_path: Path) -> None:
    pool_dir = tmp_path / "opponents_spell"
    saved_path = train_selfplay_spell(
        total_timesteps=16,
        model_path=tmp_path / "selfplay_spell_test",
        opponent_pool_dir=pool_dir,
        verbose=0,
        n_steps=8,
        batch_size=8,
    )

    assert saved_path.exists()
    assert (pool_dir / "ppo_snapshot_16.zip").exists()


def test_train_selfplay_spell_finetune_short_run(tmp_path: Path) -> None:
    pool_dir = tmp_path / "opponents_spell_finetuned"
    saved_path = train_spell_finetune(
        total_timesteps=16,
        model_path=tmp_path / "selfplay_spell_finetuned_test",
        opponent_pool_dir=pool_dir,
        verbose=0,
        n_steps=8,
        batch_size=8,
        reward_shaping=True,
    )

    assert saved_path.exists()
    assert (pool_dir / "ppo_snapshot_16.zip").exists()


def test_spell_reward_shaping_on_off_does_not_break_env() -> None:
    for enabled in (True, False):
        env = DuelMastersSpellFineTuneEnv(
            SelfPlayConfig(seed=2, fixed_opponent="heuristic"),
            reward_config=SpellRewardConfig(enabled=enabled),
        )
        _observation, info = env.reset()
        _next_observation, reward, terminated, truncated, next_info = env.step(info["legal_action_ids"][0])

        assert isinstance(reward, float)
        assert isinstance(terminated, bool)
        assert isinstance(truncated, bool)
        assert "legal_action_ids" in next_info


def test_cast_spell_action_mask_supports_maskable_ppo(tmp_path: Path) -> None:
    saved_path = train_ppo_spell(
        total_timesteps=8,
        model_path=tmp_path / "ppo_spell_mask_test",
        verbose=0,
        n_steps=8,
        batch_size=8,
    )

    assert saved_path.exists()


def test_evaluate_spell_handles_missing_models(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DM_EVALUATE_SPELL_GAMES", "2")

    evaluate_spell_main()


def test_analyze_spell_logs_extended_tags_are_known() -> None:
    record = analyze_game(0)
    known_tags = {
        "DESTROY_TARGETでblockerを処理したか",
        "DESTROY_TARGETでリーサルが通ったか",
        "DESTROY_TARGETで低価値対象を取った可能性",
        "MANA_BOOSTで高コスト召喚に繋がった",
        "DRAW_1で手札切れを回避した",
        "GAIN_SHIELDでそのターンの敗北を防いだか",
        "呪文を使わずに負けた可能性",
        "呪文を使いすぎて盤面展開が遅れた可能性",
        "CAST_SPELLより召喚を優先すべきだった可能性",
        "CAST_SPELLより攻撃を優先すべきだった可能性",
    }

    assert set(record["tags"]).issubset(known_tags)


def test_incompatible_model_path_in_pool_does_not_break_env(tmp_path: Path) -> None:
    bad_model = tmp_path / "ppo_snapshot_old_256.zip"
    bad_model.write_text("not a compatible model", encoding="utf-8")
    env = DuelMastersSelfPlayEnv(SelfPlayConfig(seed=3, fixed_opponent=bad_model))
    _observation, info = env.reset()
    _next_observation, reward, terminated, truncated, next_info = env.step(info["legal_action_ids"][0])

    assert isinstance(reward, float)
    assert isinstance(terminated, bool)
    assert isinstance(truncated, bool)
    assert "legal_action_ids" in next_info
