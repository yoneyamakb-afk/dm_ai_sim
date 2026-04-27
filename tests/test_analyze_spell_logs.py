import json

from dm_ai_sim import analyze_spell_logs


def test_analyze_spell_logs_writes_jsonl(tmp_path) -> None:
    output_path = tmp_path / "spell_analysis.jsonl"

    analyze_spell_logs.main(games=1, output_path=output_path)

    lines = output_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert "events" in record
    assert "tags" in record


def test_analyze_spell_logs_tags_are_available() -> None:
    tags = analyze_spell_logs._classify_spell_tags(
        [
            {
                "spell_cast": True,
                "spell_effect": "DESTROY_TARGET",
                "opponent_battle_zone_before": 1,
                "opponent_battle_zone_after": 0,
                "hand_count_before": 1,
                "hand_count_after": 0,
                "mana_count_before": 1,
                "mana_count_after": 1,
                "shield_count_before": 1,
                "shield_count_after": 1,
            },
            {
                "spell_cast": True,
                "spell_effect": "GAIN_SHIELD",
                "opponent_battle_zone_before": 0,
                "opponent_battle_zone_after": 0,
                "hand_count_before": 1,
                "hand_count_after": 0,
                "mana_count_before": 1,
                "mana_count_after": 1,
                "shield_count_before": 0,
                "shield_count_after": 1,
            },
        ],
        winner=0,
    )

    assert "DESTROY_TARGETでblockerを処理したか" in tags
    assert "GAIN_SHIELDでそのターンの敗北を防いだか" in tags
