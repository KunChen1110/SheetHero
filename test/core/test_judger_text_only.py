import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from backend.Judger import evaluator


def test_evaluate_task_scores_text_only_dataset(monkeypatch, tmp_path):
    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_text(
        json.dumps(
            [
                {
                    "task_id": "Test 27",
                    "answer": "Product codes A-101 and a101 are inconsistent.",
                    "expected_output_file": [],
                }
            ]
        ),
        encoding="utf-8",
    )
    logger_path = tmp_path / "logger.md"
    logger_path.write_text(
        "Short Answer: Product codes A-101 and a101 are inconsistent.\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(evaluator, "_openai_client", lambda: object())
    monkeypatch.setattr(evaluator, "score_text", lambda _client, _output, _reference: (100.0, "No errors found."))

    result = evaluator.evaluate_task("Test 27", str(logger_path), dataset_path=str(dataset_path))

    assert result["structure_type"] == "text_only"
    assert result["total_score"] == 100.0
    assert result["text_weight"] == 1.0
