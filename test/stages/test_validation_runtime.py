import os
import sys
from types import SimpleNamespace

from openpyxl import Workbook

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from backend.stages.validation.runtime import ValidationRuntime


class _ClientStub:
    pass


def test_validation_runtime_rule_passes_saved_workbook_without_llm(tmp_path):
    output_path = tmp_path / "out.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Output"
    sheet.append(["Date", "Category", "Daily Spending (£)", "Notes"])
    sheet.append(["2025-11-01", "Food", 20, "Lunch"])
    sheet.append(["2025-11-02", "Travel", 15, "Bus"])
    sheet.append(["Total Spending in November", 35])
    workbook.save(output_path)

    runtime = ValidationRuntime(
        client=_ClientStub(),
        deployment="offline-test",
        excel_context_understanding="",
        prompt_profile="offline_strict",
    )
    runtime.llm_client = SimpleNamespace(
        get_response=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("validation LLM should not be called")
        )
    )

    execution_result = {
        "success": True,
        "answer": str(output_path),
        "conversation_history": [],
        "total_turns": 3,
        "execution_summary": {
            "total_code_executions": 1,
            "successful_executions": 1,
            "failed_executions": 0,
            "execution_steps": [
                {
                    "turn": 3,
                    "success": True,
                    "code": "save_workbook_to(output_path)",
                    "result": (
                        "Wrote 3 rows to Output!A1:D3\n"
                        "Added summary row at row 4 in sheet 'Output'\n"
                        "Highlighted row(s) [2] in sheet 'Output'\n"
                        f"Workbook saved to: {output_path}\n"
                    ),
                }
            ],
        },
    }

    understanding_output = "\n".join(
        [
            "requires_detailed_table: YES",
            "requires_highlight: YES",
            "requires_summary_metrics: YES",
        ]
    )

    result = runtime.run(
        execution_result=execution_result,
        user_question=(
            "Merge the two spending tables, calculate the average daily spending and total spending "
            "in November, highlight the maximum spending days, and output a new spreadsheet."
        ),
        understanding_output=understanding_output,
    )

    assert result["validation_passed"] is True
    assert result["verified_answer"] == str(output_path)
    assert result["requires_reexecution"] is False
