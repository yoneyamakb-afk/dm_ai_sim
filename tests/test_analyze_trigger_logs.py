import json

from dm_ai_sim import analyze_trigger_logs


def test_analyze_trigger_logs_writes_jsonl(tmp_path) -> None:
    output_path = tmp_path / "trigger_analysis.jsonl"

    analyze_trigger_logs.main(games=1, output_path=output_path)

    lines = output_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert "winner" in record
    assert "tags" in record
    assert "events" in record


def test_analyze_trigger_logs_expanded_tags_are_available() -> None:
    tags = analyze_trigger_logs._classify_trigger_tags(
        [
            {
                "attacker_player": 0,
                "action": {"type": "ATTACK_SHIELD"},
                "shield_broken": True,
                "trigger_activated": True,
                "trigger_effect": "DESTROY_ATTACKER",
                "attacker_destroyed_by_trigger": True,
                "shield_count_before": 1,
                "shield_count_after": 0,
            },
            {
                "attacker_player": 0,
                "action": {"type": "END_ATTACK"},
                "shield_broken": False,
                "trigger_activated": False,
                "trigger_effect": None,
                "attacker_destroyed_by_trigger": False,
                "shield_count_before": 0,
                "shield_count_after": 0,
            },
            {
                "attacker_player": 1,
                "action": {"type": "ATTACK_SHIELD"},
                "shield_broken": True,
                "trigger_activated": True,
                "trigger_effect": "GAIN_SHIELD",
                "attacker_destroyed_by_trigger": False,
                "shield_count_before": 1,
                "shield_count_after": 1,
            },
        ],
        winner=1,
    )

    assert "リーサル可能だったか" in tags
    assert "DESTROY_ATTACKERで主要アタッカーを失ったか" in tags
    assert "GAIN_SHIELDでリーサルがずれたか" in tags
