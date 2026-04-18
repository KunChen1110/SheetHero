import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from backend.stages.execution.runtime import ExecutionRuntime


class _SandboxStub:
    def __init__(self):
        self.code_globals = {}
        self.output_preferences = {"mode": "file"}


class _ClientStub:
    pass


def test_offline_runtime_executes_llm_generated_code_before_any_skill_fast_path(monkeypatch):
    monkeypatch.delenv("SHEETHERO_ENABLE_SKILL_FAST_PATH", raising=False)
    monkeypatch.delenv("SHEETHERO_ENABLE_STRUCTURED_HELPER_EXECUTION", raising=False)
    runtime = ExecutionRuntime(
        client=_ClientStub(),
        deployment="offline-test",
        sandbox=_SandboxStub(),
        excel_context_execution="",
        prompt_profile="offline_strict",
    )

    fast_path_calls = {"count": 0}

    runtime.llm_client = SimpleNamespace(
        get_response=lambda *_args, **_kwargs: SimpleNamespace(
            content=(
                "**Thought:** read and write output\n"
                "```python\n"
                "tables = load_all_tables()\n"
                "create_output_sheet('Output')\n"
                "write_dataframe_to_sheet([['Metric', 'Value'], ['Total', 1]], 'Output', 'A1')\n"
                "saved_file = save_workbook_to(output_path)\n"
                "print('SAVED_FILE:', saved_file)\n"
                "saved_file\n"
                "```"
            )
        )
    )
    runtime.parser = SimpleNamespace(
        parse=lambda _content: (
            "read and write output",
            "\n".join(
                [
                    "tables = load_all_tables()",
                    "create_output_sheet('Output')",
                    "write_dataframe_to_sheet([['Metric', 'Value'], ['Total', 1]], 'Output', 'A1')",
                    "saved_file = save_workbook_to(output_path)",
                    "print('SAVED_FILE:', saved_file)",
                    "saved_file",
                ]
            ),
        )
    )
    runtime.executor = SimpleNamespace(
        check_forbidden_bounded=lambda _code: None,
        execute=lambda _code: "Wrote 2 rows to Output!A1:B2\nSAVED_FILE: /tmp/out.xlsx",
    )
    runtime.skill_fast_path_runner = SimpleNamespace(
        try_run=lambda _question: fast_path_calls.__setitem__("count", fast_path_calls["count"] + 1) or {
            "success": True,
            "answer": "/tmp/direct.xlsx",
            "_skill_fast_path": "concat_tables_with_same_headers",
        }
    )

    result = runtime.run(
        understanding_output="requires_detailed_table: YES",
        user_question="Merge the files and calculate the total spending.",
        max_turns=1,
    )

    assert result["success"] is True
    assert result["answer"] == "/tmp/out.xlsx"
    assert "_skill_fast_path" not in result
    assert fast_path_calls["count"] == 0


def test_offline_runtime_reprompts_on_format_error_instead_of_falling_back(monkeypatch):
    monkeypatch.delenv("SHEETHERO_ENABLE_SKILL_FAST_PATH", raising=False)
    runtime = ExecutionRuntime(
        client=_ClientStub(),
        deployment="offline-test",
        sandbox=_SandboxStub(),
        excel_context_execution="",
        prompt_profile="offline_strict",
    )

    responses = iter(
        [
            SimpleNamespace(content="I will think first."),
            SimpleNamespace(
                content=(
                    "**Thought:** fixed format\n"
                    "```python\n"
                    "tables = load_all_tables()\n"
                    "create_output_sheet('Output')\n"
                    "write_dataframe_to_sheet([['Metric', 'Value'], ['Total', 1]], 'Output', 'A1')\n"
                    "saved_file = save_workbook_to(output_path)\n"
                    "print('SAVED_FILE:', saved_file)\n"
                    "saved_file\n"
                    "```"
                )
            ),
        ]
    )
    runtime.llm_client = SimpleNamespace(get_response=lambda *_args, **_kwargs: next(responses))
    runtime.parser = SimpleNamespace(
        parse=lambda content: (
            ("fixed format", "\n".join(
                [
                    "tables = load_all_tables()",
                    "create_output_sheet('Output')",
                    "write_dataframe_to_sheet([['Metric', 'Value'], ['Total', 1]], 'Output', 'A1')",
                    "saved_file = save_workbook_to(output_path)",
                    "print('SAVED_FILE:', saved_file)",
                    "saved_file",
                ]
            )) if "```python" in content else ("", None)
        )
    )
    runtime.executor = SimpleNamespace(
        check_forbidden_bounded=lambda _code: None,
        execute=lambda _code: "Wrote 2 rows to Output!A1:B2\nSAVED_FILE: /tmp/out.xlsx",
    )
    fast_path_calls = {"count": 0}
    runtime.skill_fast_path_runner = SimpleNamespace(
        try_run=lambda _question: fast_path_calls.__setitem__("count", fast_path_calls["count"] + 1)
    )

    result = runtime.run(
        understanding_output="requires_detailed_table: YES",
        user_question="Merge the files and calculate the total spending.",
        max_turns=2,
    )

    assert result["success"] is True
    assert result["answer"] == "/tmp/out.xlsx"
    assert "_skill_fast_path" not in result
    assert fast_path_calls["count"] == 0


def test_offline_runtime_format_repair_demands_code_first_response(monkeypatch):
    monkeypatch.delenv("SHEETHERO_ENABLE_SKILL_FAST_PATH", raising=False)
    runtime = ExecutionRuntime(
        client=_ClientStub(),
        deployment="offline-test",
        sandbox=_SandboxStub(),
        excel_context_execution="",
        prompt_profile="offline_strict",
    )

    calls = {"count": 0, "repair_prompt": ""}

    def _get_response(messages, **_kwargs):
        calls["count"] += 1
        if calls["count"] == 2:
            calls["repair_prompt"] = messages[-1]["content"]
            return SimpleNamespace(
                content=(
                    "```python\n"
                    "tables = load_all_tables()\n"
                    "create_output_sheet('Output')\n"
                    "write_dataframe_to_sheet([['Metric', 'Value'], ['Total', 1]], 'Output', 'A1')\n"
                    "saved_file = save_workbook_to(output_path)\n"
                    "print('SAVED_FILE:', saved_file)\n"
                    "saved_file\n"
                    "```"
                )
            )
        return SimpleNamespace(content="I will think first.")

    runtime.llm_client = SimpleNamespace(get_response=_get_response)
    runtime.parser = SimpleNamespace(
        parse=lambda content: (
            (
                "",
                "\n".join(
                    [
                        "tables = load_all_tables()",
                        "create_output_sheet('Output')",
                        "write_dataframe_to_sheet([['Metric', 'Value'], ['Total', 1]], 'Output', 'A1')",
                        "saved_file = save_workbook_to(output_path)",
                        "print('SAVED_FILE:', saved_file)",
                        "saved_file",
                    ]
                ),
            )
            if "```python" in content
            else ("", None)
        )
    )
    runtime.executor = SimpleNamespace(
        check_forbidden_bounded=lambda _code: None,
        execute=lambda _code: "Wrote 2 rows to Output!A1:B2\nSAVED_FILE: /tmp/out.xlsx",
    )
    runtime.skill_fast_path_runner = SimpleNamespace(try_run=lambda _question: None)

    result = runtime.run(
        understanding_output="requires_detailed_table: YES",
        user_question="Merge the files and calculate the total spending.",
        max_turns=2,
    )

    assert result["success"] is True
    assert "Start the very first line with ```python." in calls["repair_prompt"]
    assert "Any Thought, explanation, or planning text will be discarded." in calls["repair_prompt"]


def test_offline_runtime_uses_plan_to_code_recovery_for_thought_only_response(monkeypatch):
    monkeypatch.delenv("SHEETHERO_ENABLE_SKILL_FAST_PATH", raising=False)
    runtime = ExecutionRuntime(
        client=_ClientStub(),
        deployment="offline-test",
        sandbox=_SandboxStub(),
        excel_context_execution="",
        prompt_profile="offline_strict",
    )

    calls = {"count": 0, "recovery_prompt": ""}

    def _get_response(messages, **_kwargs):
        calls["count"] += 1
        if calls["count"] == 2:
            calls["recovery_prompt"] = messages[-1]["content"]
            return SimpleNamespace(
                content=(
                    "```python\n"
                    "tables = load_all_tables()\n"
                    "create_output_sheet('Output')\n"
                    "write_dataframe_to_sheet([['Metric', 'Value'], ['Total', 1]], 'Output', 'A1')\n"
                    "saved_file = save_workbook_to(output_path)\n"
                    "print('SAVED_FILE:', saved_file)\n"
                    "saved_file\n"
                    "```"
                )
            )
        return SimpleNamespace(content="Plan: merge the tables, summarize spending, then save the workbook.")

    runtime.llm_client = SimpleNamespace(get_response=_get_response)
    runtime.parser = SimpleNamespace(
        parse=lambda content: (
            (
                "Plan: merge the tables, summarize spending, then save the workbook.",
                None,
            )
            if "Plan:" in content
            else (
                "",
                "\n".join(
                    [
                        "tables = load_all_tables()",
                        "create_output_sheet('Output')",
                        "write_dataframe_to_sheet([['Metric', 'Value'], ['Total', 1]], 'Output', 'A1')",
                        "saved_file = save_workbook_to(output_path)",
                        "print('SAVED_FILE:', saved_file)",
                        "saved_file",
                    ]
                ),
            )
        )
    )
    runtime.executor = SimpleNamespace(
        check_forbidden_bounded=lambda _code: None,
        execute=lambda _code: "Wrote 2 rows to Output!A1:B2\nSAVED_FILE: /tmp/out.xlsx",
    )
    runtime.skill_fast_path_runner = SimpleNamespace(try_run=lambda _question: None)

    result = runtime.run(
        understanding_output="requires_detailed_table: YES",
        user_question="Merge the files and calculate the total spending.",
        max_turns=1,
    )

    assert result["success"] is True
    assert calls["count"] == 2
    assert "PLAN_TO_CODE_RECOVERY" in calls["recovery_prompt"]
    assert "Plan: merge the tables, summarize spending, then save the workbook." in calls["recovery_prompt"]


def test_offline_runtime_still_calls_llm_for_skill_matched_questions(monkeypatch):
    monkeypatch.delenv("SHEETHERO_ENABLE_SKILL_FAST_PATH", raising=False)
    runtime = ExecutionRuntime(
        client=_ClientStub(),
        deployment="offline-test",
        sandbox=_SandboxStub(),
        excel_context_execution="",
        prompt_profile="offline_strict",
    )

    llm_calls = {"count": 0}
    runtime.llm_client = SimpleNamespace(
        get_response=lambda *_args, **_kwargs: llm_calls.__setitem__("count", llm_calls["count"] + 1) or SimpleNamespace(
            content=(
                "**Thought:** compute correlation\n"
                "```python\n"
                "tables = load_all_tables()\n"
                "df = tables[0]['df']\n"
                "create_output_sheet('Output')\n"
                "write_dataframe_to_sheet([['A', 'B'], [1, 1]], 'Output', 'A1')\n"
                "saved_file = save_workbook_to(output_path)\n"
                "print('SAVED_FILE:', saved_file)\n"
                "saved_file\n"
                "```"
            )
        )
    )
    runtime.parser = SimpleNamespace(
        parse=lambda _content: (
            "compute correlation",
            "\n".join(
                [
                    "tables = load_all_tables()",
                    "df = tables[0]['df']",
                    "create_output_sheet('Output')",
                    "write_dataframe_to_sheet([['A', 'B'], [1, 1]], 'Output', 'A1')",
                    "saved_file = save_workbook_to(output_path)",
                    "print('SAVED_FILE:', saved_file)",
                    "saved_file",
                ]
            ),
        )
    )
    runtime.executor = SimpleNamespace(
        check_forbidden_bounded=lambda _code: None,
        execute=lambda _code: "Wrote 2 rows to Output!A1:B2\nSAVED_FILE: /tmp/out.xlsx",
    )

    result = runtime.run(
        understanding_output="requires_detailed_table: YES",
        user_question="Calculate the correlation matrix for all numeric columns.",
        max_turns=1,
    )

    assert result["success"] is True
    assert result["answer"] == "/tmp/out.xlsx"
    assert llm_calls["count"] == 1


def test_offline_runtime_retries_after_llm_connection_error(monkeypatch):
    monkeypatch.delenv("SHEETHERO_ENABLE_SKILL_FAST_PATH", raising=False)
    runtime = ExecutionRuntime(
        client=_ClientStub(),
        deployment="offline-test",
        sandbox=_SandboxStub(),
        excel_context_execution="",
        prompt_profile="offline_strict",
    )

    calls = {"count": 0, "max_tokens": []}

    def _get_response(*_args, **kwargs):
        calls["count"] += 1
        calls["max_tokens"].append(kwargs.get("max_tokens"))
        if calls["count"] == 1:
            raise RuntimeError("Connection error.")
        return SimpleNamespace(
            content=(
                "**Thought:** recovered\n"
                "```python\n"
                "tables = load_all_tables()\n"
                "create_output_sheet('Output')\n"
                "write_dataframe_to_sheet([['Metric', 'Value'], ['Total', 1]], 'Output', 'A1')\n"
                "saved_file = save_workbook_to(output_path)\n"
                "print('SAVED_FILE:', saved_file)\n"
                "saved_file\n"
                "```"
            )
        )

    runtime.llm_client = SimpleNamespace(get_response=_get_response)
    runtime.parser = SimpleNamespace(
        parse=lambda _content: (
            "recovered",
            "\n".join(
                [
                    "tables = load_all_tables()",
                    "create_output_sheet('Output')",
                    "write_dataframe_to_sheet([['Metric', 'Value'], ['Total', 1]], 'Output', 'A1')",
                    "saved_file = save_workbook_to(output_path)",
                    "print('SAVED_FILE:', saved_file)",
                    "saved_file",
                ]
            ),
        )
    )
    runtime.executor = SimpleNamespace(
        check_forbidden_bounded=lambda _code: None,
        execute=lambda _code: "Wrote 2 rows to Output!A1:B2\nSAVED_FILE: /tmp/out.xlsx",
    )

    result = runtime.run(
        understanding_output="requires_detailed_table: YES",
        user_question="Produce a tutor meeting schedule.",
        max_turns=2,
    )

    assert result["success"] is True
    assert result["answer"] == "/tmp/out.xlsx"
    assert calls["count"] == 2
    assert calls["max_tokens"][0] == 768
    assert calls["max_tokens"][1] <= 768


def test_offline_runtime_compacts_repair_turn_after_preflight(monkeypatch):
    monkeypatch.delenv("SHEETHERO_ENABLE_SKILL_FAST_PATH", raising=False)
    runtime = ExecutionRuntime(
        client=_ClientStub(),
        deployment="offline-test",
        sandbox=_SandboxStub(),
        excel_context_execution="",
        prompt_profile="offline_strict",
    )

    calls = {"count": 0, "max_tokens": [], "message_counts": [], "last_user": []}
    responses = iter(
        [
            SimpleNamespace(content="bad-turn"),
            SimpleNamespace(content="good-turn"),
        ]
    )

    def _get_response(messages, **kwargs):
        calls["count"] += 1
        calls["max_tokens"].append(kwargs.get("max_tokens"))
        calls["message_counts"].append(len(messages))
        calls["last_user"].append(messages[-1]["content"])
        return next(responses)

    runtime.llm_client = SimpleNamespace(get_response=_get_response)
    runtime.parser = SimpleNamespace(
        parse=lambda content: (
            "repair" if content == "good-turn" else "draft",
            "\n".join(
                [
                    "tables = load_all_tables()",
                    "create_output_sheet('Output')",
                    "write_dataframe_to_sheet([['Tutor Name', 'Time Slot', 'Room', 'Students'], ['A', '09:00', 'R1', 'S1']], 'Output', 'A1')",
                    "saved_file = save_workbook_to(output_path)",
                    "print('SAVED_FILE:', saved_file)",
                    "saved_file",
                ]
            ) if content == "good-turn" else "\n".join(
                [
                    "tables = load_all_tables()",
                    "assignment_t = tables[0]",
                    "schedule_t = tables[1]",
                    "output_df = pd.merge(assignment_t['df'], schedule_t['df'], left_on='Assigned Tutor', right_on='Tutor Name')",
                    "saved_file = save_workbook_to(output_path)",
                    "print('SAVED_FILE:', saved_file)",
                    "saved_file",
                ]
            ),
        )
    )
    runtime.executor = SimpleNamespace(
        check_forbidden_bounded=lambda _code: None,
        execute=lambda _code: "Wrote 2 rows to Output!A1:D2\nSAVED_FILE: /tmp/out.xlsx",
    )
    runtime.generic_preflight = SimpleNamespace(
        offline_preflight_check=lambda code_action, _question: (
            "PREFLIGHT_ASSIGNMENT_SCHEDULE: after header-grounded table selection, use the shared grouped-assignment helper instead of a hand-written bare merge."
            if "pd.merge" in code_action else None
        )
    )
    runtime.skill_preflight = SimpleNamespace(
        metadata_routed_preflight_check=lambda *_args, **_kwargs: None
    )

    result = runtime.run(
        understanding_output="requires_detailed_table: YES",
        user_question="Produce a tutor meeting schedule.",
        max_turns=2,
    )

    assert result["success"] is True
    assert result["answer"] == "/tmp/out.xlsx"
    assert calls["count"] == 2
    assert calls["message_counts"][0] == 2
    assert calls["message_counts"][1] == 3
    assert calls["max_tokens"][0] == 768
    assert calls["max_tokens"][1] <= 768
    assert "PREFLIGHT_ASSIGNMENT_SCHEDULE" in calls["last_user"][1]


def test_offline_runtime_escalates_after_repeated_same_preflight(monkeypatch):
    monkeypatch.delenv("SHEETHERO_ENABLE_SKILL_FAST_PATH", raising=False)
    runtime = ExecutionRuntime(
        client=_ClientStub(),
        deployment="offline-test",
        sandbox=_SandboxStub(),
        excel_context_execution="",
        prompt_profile="offline_strict",
    )

    calls = {"count": 0, "last_user": []}
    responses = iter(
        [
            SimpleNamespace(content="bad-turn-1"),
            SimpleNamespace(content="bad-turn-2"),
            SimpleNamespace(content="good-turn"),
        ]
    )

    def _get_response(messages, **_kwargs):
        calls["count"] += 1
        calls["last_user"].append(messages[-1]["content"])
        return next(responses)

    runtime.llm_client = SimpleNamespace(get_response=_get_response)
    runtime.parser = SimpleNamespace(
        parse=lambda content: (
            "repair",
            "\n".join(
                [
                    "tables = load_all_tables()",
                    "concat_result = concat_tables_with_same_headers(tables)",
                    "combined_df = concat_result['output_df']",
                    "summary_df = combined_df",
                    "summary_result = summarize_numeric_column(summary_df, value_col='Daily Spending (£)')",
                    "create_output_sheet('Output')",
                    "write_dataframe_to_sheet(summary_df, 'Output', 'A1')",
                    "summary_row = len(summary_df) + 2",
                    "add_summary_row('Output', summary_row, summary_result['summary'])",
                    "row_numbers = summary_result['output_row_numbers']",
                    "highlight_rows('Output', row_numbers, {'fill_color': 'red'})",
                    "saved_file = save_workbook_to(output_path)",
                    "print('SAVED_FILE:', saved_file)",
                    "saved_file",
                ]
            ) if content == "good-turn" else "\n".join(
                [
                    "tables = load_all_tables()",
                    "concat_result = concat_tables_with_same_headers(tables)",
                    "combined_df = concat_result['output_df']",
                    "summary_df = combined_df",
                    "summary_result = summarize_numeric_column(summary_df, value_col='Daily Spending (£)')",
                    "create_output_sheet('Output')",
                    "write_dataframe_to_sheet(summary_df, 'Output', 'A1')",
                    "add_summary_row('Output', summary_result['row'], {'Total': summary_result['total']})",
                    "saved_file = save_workbook_to(output_path)",
                    "print('SAVED_FILE:', saved_file)",
                    "saved_file",
                ]
            ),
        )
    )
    runtime.executor = SimpleNamespace(
        check_forbidden_bounded=lambda _code: None,
        execute=lambda _code: "Wrote 4 rows to Output!A1:D4\nAdded summary row at row 6 in sheet 'Output'\nHighlighted row(s) [3] in sheet 'Output'\nSAVED_FILE: /tmp/out.xlsx",
    )
    repeated_issue = (
        "PREFLIGHT_SCHEMA_MERGE_SUMMARY: same-schema merge + summary + highlight tasks should use the shared concat/summary helpers.\n"
        "- Use `summary_result['summary']` for totals/averages and `summary_result['output_row_numbers']` for highlighting."
    )
    runtime.generic_preflight = SimpleNamespace(
        offline_preflight_check=lambda code_action, _question: (
            repeated_issue if "summary_result['row']" in code_action else None
        )
    )
    runtime.skill_preflight = SimpleNamespace(
        metadata_routed_preflight_check=lambda *_args, **_kwargs: None
    )

    result = runtime.run(
        understanding_output="requires_detailed_table: YES\nrequires_highlight: YES\nrequires_summary_metrics: YES",
        user_question="Merge the two spending tables, calculate the average and total spending in November, and highlight the max day.",
        max_turns=3,
    )

    assert result["success"] is True
    assert calls["count"] == 3
    assert "REPEATED_PREFLIGHT_LOOP_BREAKER" in calls["last_user"][2]
    assert "summary_result['summary']" in calls["last_user"][2]
    assert "summary_result['output_row_numbers']" in calls["last_user"][2]
