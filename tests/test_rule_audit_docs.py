from pathlib import Path

from dm_ai_sim.diagnose_standard_deck import main as diagnose_standard_deck_main


def test_rule_audit_documents_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    for name in [
        "RULE_COMPATIBILITY.md",
        "STANDARD_DECK_DIAGNOSTICS.md",
        "TEST_COVERAGE.md",
        "REAL_CARD_DATA_PLAN.md",
    ]:
        path = root / name
        assert path.exists()
        assert path.read_text(encoding="utf-8").strip()


def test_diagnose_standard_deck_runs(capsys) -> None:
    diagnose_standard_deck_main()
    output = capsys.readouterr().out
    assert "deck_size: 40" in output
    assert "multicolor_cards:" in output
    assert "turn2_candidates:" in output

