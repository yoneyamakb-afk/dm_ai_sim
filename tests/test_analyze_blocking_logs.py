import json

from dm_ai_sim import analyze_blocking_logs
from dm_ai_sim.agents.heuristic_agent import HeuristicAgent


def test_analyze_blocking_logs_writes_jsonl(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(analyze_blocking_logs, "_make_learner", lambda: HeuristicAgent())
    output_path = tmp_path / "blocking_analysis.jsonl"

    analyze_blocking_logs.main(games=1, output_path=output_path)

    lines = output_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert "winner" in record
    assert "events" in record


def test_analyze_blocking_logs_expanded_tags_are_available() -> None:
    tags = analyze_blocking_logs._classify_loss(
        [
            {
                "current_player": 0,
                "pending_attack": True,
                "pending_target_type": "PLAYER",
                "action": {"type": "DECLINE_BLOCK"},
                "shield_counts": [0, 0],
                "own_untapped_attackers": 2,
                "opponent_untapped_blockers": 1,
                "opponent_creatures": 1,
                "attacker_power": 3000,
                "blocker_power": None,
            },
            {
                "current_player": 0,
                "pending_attack": False,
                "pending_target_type": None,
                "action": {"type": "ATTACK_SHIELD"},
                "shield_counts": [1, 0],
                "own_untapped_attackers": 2,
                "opponent_untapped_blockers": 1,
                "opponent_creatures": 1,
                "attacker_power": None,
                "blocker_power": None,
            },
            {
                "current_player": 0,
                "pending_attack": False,
                "pending_target_type": None,
                "action": {"type": "END_ATTACK"},
                "shield_counts": [1, 0],
                "own_untapped_attackers": 1,
                "opponent_untapped_blockers": 0,
                "opponent_creatures": 0,
                "attacker_power": None,
                "blocker_power": None,
            },
        ]
    )

    assert "リーサル可能だったか" in tags
    assert "DECLINE_BLOCKが敗因になったか" in tags
    assert "相手ブロッカーを攻撃で処理すべきだったか" in tags
