from dm_ai_sim.evaluate_spell import available_agents, main as evaluate_spell_main


def test_evaluate_spell_handles_missing_models(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DM_EVALUATE_SPELL_GAMES", "2")

    agents = available_agents()
    evaluate_spell_main()

    assert [agent.name for agent in agents] == ["RandomAgent", "HeuristicAgent"]
