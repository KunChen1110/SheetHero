import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from backend.stages.interact.stage import InteractStage


def test_workbook_matches_request_uses_llm_relevance_check(monkeypatch):
    from backend.stages.interact import stage as interact_stage_module

    captured = {}

    def fake_call_llm(_client, _deployment, messages, **_kwargs):
        captured["prompt"] = messages[0]["content"]
        return "NO\nReason: requested student tutor scheduling but workbook contains spending records."

    monkeypatch.setattr(interact_stage_module, "call_llm", fake_call_llm)

    stage = InteractStage(client=object(), deployment="test-model")

    result = stage.workbook_matches_request(
        "Produce a tutor meeting schedule for students.",
        "Files contain columns: Date, Category, Daily Spending (£), Notes.",
    )

    assert result is False
    assert "Produce a tutor meeting schedule" in captured["prompt"]
    assert "Daily Spending" in captured["prompt"]

