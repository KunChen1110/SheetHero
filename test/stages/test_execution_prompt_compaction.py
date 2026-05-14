import os
import json
import sys
from types import SimpleNamespace
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from backend.config.settings import Config
from backend.environment import Sandbox
from backend.prompt.prompt_builder import PromptBuilder
from backend.agent.core.SheetHero import _resolve_openai_timeout
from backend.stages.base.llm_utils import _resolve_wall_timeout as _resolve_shared_wall_timeout
from backend.stages.execution.core.llm_client import ExecutionLLMClient
from backend.stages.execution.core.llm_client import _resolve_wall_timeout as _resolve_execution_wall_timeout
from backend.stages.execution.core.parser import ExecutionResponseParser
from backend.stages.execution.runtime import ExecutionRuntime
from backend.stages.understanding.context_builder import ExcelContextBuilder
from backend.stages.understanding.stage import UnderstandingStage


class _SandboxStub:
    code_globals = {}


def test_offline_execution_system_prompt_stays_compact():
    prompt = PromptBuilder(profile="offline_strict").build_execution_system_prompt(
        "write result to output file"
    )

    assert "load_all_tables()" in prompt
    assert "read_table_multi" in prompt
    assert "save_workbook_to(output_path)" in prompt
    assert len(prompt) <= 2800


def test_offline_execution_and_understanding_prompts_align_on_helper_first_loading():
    execution_prompt = PromptBuilder(profile="offline_strict").build_execution_system_prompt(
        "write result to output file"
    )
    understanding_prompt = PromptBuilder(profile="offline_strict").build_understanding_prompt(
        "Build a multi-sheet utilisation workbook.",
        "📁 **File: input.csv**\n**📄 Sheet: 'Sheet1'**\n- Candidate headers: SectionID, Instructor, Capacity",
        "",
    )

    assert "load_all_tables()" in execution_prompt
    assert "load_all_tables()" in understanding_prompt
    assert "/no_think" in understanding_prompt
    assert "Do not output hidden reasoning" in understanding_prompt
    assert "read_table_multi" not in understanding_prompt


def test_execution_runtime_uses_tighter_offline_token_budget_by_default(monkeypatch):
    monkeypatch.delenv("SHEETHERO_EXECUTION_MAX_TOKENS", raising=False)

    runtime = ExecutionRuntime(
        client=SimpleNamespace(),
        deployment="offline-test",
        sandbox=_SandboxStub(),
        excel_context_execution="",
        prompt_profile="offline_strict",
    )

    assert runtime._bounded_exec_max_tokens == 1536


def test_qwen3_execution_runtime_uses_context_safe_initial_and_recovery_budgets(monkeypatch):
    monkeypatch.delenv("SHEETHERO_EXECUTION_MAX_TOKENS", raising=False)
    monkeypatch.delenv("SHEETHERO_INITIAL_EXEC_MAX_TOKENS", raising=False)
    monkeypatch.delenv("SHEETHERO_LLM_RECOVERY_MAX_TOKENS", raising=False)

    runtime = ExecutionRuntime(
        client=SimpleNamespace(),
        deployment="qwen3:8b",
        sandbox=_SandboxStub(),
        excel_context_execution="",
        prompt_profile="offline_strict",
    )

    assert runtime._bounded_exec_max_tokens == 1536
    assert runtime._initial_exec_max_tokens == 768
    assert runtime._llm_recovery_max_tokens == 768


def test_offline_initial_and_recovery_prompts_frontload_helper_first_policy():
    runtime = ExecutionRuntime(
        client=SimpleNamespace(),
        deployment="qwen3:8b",
        sandbox=_SandboxStub(),
        excel_context_execution="",
        prompt_profile="offline_strict",
    )
    question = (
        "First merge the two tables into a single table, then calculate the average daily spending "
        "and total spending. Highlight the day with the highest spending."
    )

    initial = runtime._create_initial_user_prompt("", question)["content"]
    recovery = runtime._create_llm_recovery_prompt(question)["content"]

    for prompt in (initial, recovery):
        assert "OFFLINE HELPER-FIRST START" in prompt
        assert "Do not choose a pandas fallback before selected helper calls" in prompt
        assert "Pandas may only prepare helper inputs or format helper outputs" in prompt
    assert "HELPER-FIRST POLICY FOR THIS PLAN" in initial
    assert "Do not compute final summary/highlight rows with sum(), mean(), max(), idxmax(), argmax(), or DataFrame.index" in initial


def test_execution_llm_client_uses_tighter_wall_timeout_by_default(monkeypatch):
    monkeypatch.delenv("SHEETHERO_LLM_TIMEOUT_SECONDS", raising=False)

    client = ExecutionLLMClient(SimpleNamespace(), "offline-test")

    assert client._wall_timeout == 300


def test_execution_llm_client_disables_wall_timeout_for_qwen3_by_default(monkeypatch):
    monkeypatch.delenv("SHEETHERO_LLM_TIMEOUT_SECONDS", raising=False)

    client = ExecutionLLMClient(SimpleNamespace(), "qwen3:8b")

    assert _resolve_execution_wall_timeout("qwen3:8b") is None
    assert client._wall_timeout is None


def test_shared_llm_calls_disable_wall_timeout_for_qwen3_by_default(monkeypatch):
    monkeypatch.delenv("SHEETHERO_LLM_TIMEOUT_SECONDS", raising=False)

    assert _resolve_shared_wall_timeout("qwen3:8b") is None


def test_sheethero_disables_openai_client_timeout_for_local_qwen3():
    assert _resolve_openai_timeout(timeout=120, base_url="http://localhost:11434/v1", deployment="qwen3:8b") is None
    assert _resolve_openai_timeout(timeout=120, base_url="", deployment="qwen3:8b") == 120


def test_offline_qwen3_understanding_calls_llm_with_compact_context(monkeypatch):
    captured = {"messages": None}

    def _fake_call(_client, _deployment, messages, **_kwargs):
        captured["messages"] = messages
        return "### 1. Sheet Summary\n- Files: spending.xlsx\n### 2. Execution Plan\n- Use runtime schema.\n### 3. Output Contract\nrequires_detailed_table: YES\nrequires_summary_metrics: YES\nrequires_highlight: NO"

    monkeypatch.setattr("backend.stages.understanding.stage.call_llm", _fake_call)

    stage = UnderstandingStage(client=None, deployment="qwen3:8b", prompt_profile="offline_strict")
    stage.run(
        "Merge the two spending tables and calculate the total spending.",
        "\n".join(
            [
                "📁 **File: spending.xlsx**",
                "**📄 Sheet: 'Sheet1'**",
                "- Candidate headers: Date, Category, Daily Spending (£), Notes",
                "- Preview rows: 200 rows shown here that should not survive compaction",
            ]
        ),
    )

    prompt = captured["messages"][-1]["content"]
    assert "Preview rows" not in prompt
    assert "Candidate headers" in prompt
    assert len(prompt) < 2500


def test_offline_execution_prompt_bans_think_tags():
    prompt = PromptBuilder(profile="offline_strict").build_execution_system_prompt(
        "write result to output file"
    )

    assert "/no_think" in prompt
    assert "<think>" in prompt
    assert "Do not output hidden reasoning" in prompt


def test_understanding_sanitizer_removes_think_blocks():
    stage = UnderstandingStage(client=None, deployment="offline-test")

    cleaned = stage._sanitize_understanding_output(
        "the<think>\nprivate reasoning\n</think>\n### 1. Sheet Summary\n- Files: a.csv",
        "calculate a matrix",
    )

    assert "<think>" not in cleaned
    assert "</think>" not in cleaned
    assert "private reasoning" not in cleaned
    assert "### 1. Sheet Summary" in cleaned


def test_understanding_falls_back_to_minimal_plan_when_llm_call_fails(monkeypatch):
    def _raise(*_args, **_kwargs):
        raise RuntimeError("Connection error.")

    monkeypatch.setattr("backend.stages.understanding.stage.call_llm", _raise)

    stage = UnderstandingStage(client=None, deployment="offline-test", prompt_profile="offline_strict")
    output = stage.run(
        "produce a tutor schedule",
        "📁 **File: tutors.csv**\n**📄 Sheet: 'tutors'**\n- Candidate headers: Tutor Name, Day, Time Slot",
    )

    assert "### 1. Sheet Summary" in output
    assert "downstream stages must inspect the runtime schema directly" in output


def test_understanding_offline_context_summary_keeps_all_visible_files():
    stage = UnderstandingStage(client=None, deployment="offline-test", prompt_profile="offline_strict")

    prompt_lines = stage._extract_context_summary_lines(
        "\n".join(
            [
                "📁 **File: tc01_input01.csv**",
                "**📄 Sheet: 'Sheet1'**",
                "- Candidate headers: StoreID, StoreName, Region",
                "📁 **File: tc01_input02.csv**",
                "**📄 Sheet: 'Sheet1'**",
                "- Candidate headers: ProductID, ProductName, Category",
                "📁 **File: tc01_input03.csv**",
                "**📄 Sheet: 'Sheet1'**",
                "- Candidate headers: SaleID, StoreID, ProductID, Month",
                "📁 **File: tc01_input04.csv**",
                "**📄 Sheet: 'Sheet1'**",
                "- Candidate headers: TargetID, StoreID, Category, Month",
            ]
        )
    )

    assert any("tc01_input01.csv" in line for line in prompt_lines)
    assert any("tc01_input02.csv" in line for line in prompt_lines)
    assert any("tc01_input03.csv" in line for line in prompt_lines)
    assert any("tc01_input04.csv" in line for line in prompt_lines)


def test_offline_runtime_schema_snapshot_does_not_hide_small_case_tables():
    runtime = ExecutionRuntime(
        client=SimpleNamespace(),
        deployment="offline-test",
        sandbox=_SandboxStub(),
        excel_context_execution="",
        prompt_profile="offline_strict",
    )

    runtime.grounding = SimpleNamespace(
        build_schema_snapshot=lambda: "\n".join(
            [
                "- `tc01_input01.csv` | columns=StoreID, StoreName, Region",
                "- `tc01_input02.csv` | columns=ProductID, ProductName, Category",
                "- `tc01_input03.csv` | columns=SaleID, StoreID, ProductID, Month",
                "- `tc01_input04.csv` | columns=TargetID, StoreID, Category, Month",
            ]
        ),
        available_workbook_basenames=lambda: [
            "tc01_input01.csv",
            "tc01_input02.csv",
            "tc01_input03.csv",
            "tc01_input04.csv",
        ],
        observed_header_set=lambda: set(),
        detect_unknown_filename_lookup=lambda _code: None,
    )
    runtime._active_understanding_output = (
        "### 1. Sheet Summary\n"
        "- Files: tc01_input01.csv, tc01_input02.csv, tc01_input03.csv\n"
    )

    snapshot = runtime._build_schema_snapshot()

    assert "tc01_input01.csv" in snapshot
    assert "tc01_input02.csv" in snapshot
    assert "tc01_input03.csv" in snapshot
    assert "tc01_input04.csv" in snapshot


def test_understanding_contract_does_not_require_summary_for_target_feature_correlation():
    flags = UnderstandingStage._infer_contract_from_question(
        "Calculate the correlation coefficient between survival and other factors such as sex, age, fare, cabin, and embarked. "
        "Output an Excel file with columns Sex, Age, Fare, Cabin, Embarked."
    )

    assert flags["requires_detailed_table"] is True
    assert flags["requires_summary_metrics"] is False


def test_understanding_contract_does_not_require_summary_for_regression_weights_output():
    flags = UnderstandingStage._infer_contract_from_question(
        "Assume a linear relationship between ice-cream sales and three factors: temperature, price, and number of tourists. "
        "Fit a linear regression model to estimate the weight (coefficient) of each factor in predicting sales. "
        "Output the learned weights in an Excel file."
    )

    assert flags["requires_detailed_table"] is False
    assert flags["requires_summary_metrics"] is False


def test_understanding_contract_does_not_require_summary_for_market_share_overlap_table():
    flags = UnderstandingStage._infer_contract_from_question(
        "Here are two tables. One gives the total EV units sold in India by quarter (2020-2022), "
        "and the other gives market share by brand (2021-2022). Find the overlapping time period, "
        "then estimate the number of EVs sold for each brand as market_share × total_units. "
        "Output a table with columns Quarter, Tata (thou), MG, Hyundai, Mahindra, Kia, Others."
    )

    assert flags["requires_detailed_table"] is True
    assert flags["requires_summary_metrics"] is False


def test_execution_parser_ignores_think_prefix_before_code():
    parser = ExecutionResponseParser()

    thought, code = parser.parse(
        "<think>internal</think>\n```python\nprint('ok')\n```"
    )

    assert thought is None
    assert code == "print('ok')"


def test_execution_parser_rewrites_top_level_return_tail():
    parser = ExecutionResponseParser()

    thought, code = parser.parse(
        "```python\nsaved_file = save_workbook_to(output_path)\nprint(f'SAVED_FILE: {saved_file}')\nreturn saved_file\n```"
    )

    assert thought is None
    assert code is not None
    assert "return saved_file" not in code
    assert code.splitlines()[-1] == "saved_file"


def test_execution_parser_rewrites_all_top_level_return_lines():
    parser = ExecutionResponseParser()

    thought, code = parser.parse(
        "```python\n"
        "saved_file = save_workbook_to(output_path)\n"
        "return saved_file\n"
        "print('done')\n"
        "return saved_file\n"
        "```"
    )

    assert thought is None
    assert code is not None
    assert "return saved_file" not in code
    assert code.splitlines()[1] == "saved_file"
    assert code.splitlines()[-1] == "saved_file"


def test_execution_parser_rewrites_indented_top_level_return_lines_without_functions():
    parser = ExecutionResponseParser()

    thought, code = parser.parse(
        "```python\n"
        "    saved_file = save_workbook_to(output_path)\n"
        "    return saved_file\n"
        "```"
    )

    assert thought is None
    assert code is not None
    assert "return saved_file" not in code
    assert code.splitlines()[-1] == "saved_file"


def test_execution_parser_does_not_treat_prose_with_code_snippets_as_bare_code():
    parser = ExecutionResponseParser()

    content = (
        "I will use tables = load_all_tables() after checking the schema.\n"
        "Then I can call create_output_sheet('Output') once the plan is clear."
    )

    thought, code = parser.parse(content)

    assert thought == content
    assert code is None


def test_execution_parser_still_accepts_real_bare_code_without_fences():
    parser = ExecutionResponseParser()

    content = (
        "tables = load_all_tables()\n"
        "create_output_sheet('Output')\n"
        "saved_file = save_workbook_to(output_path)\n"
        "saved_file"
    )

    thought, code = parser.parse(content)

    assert thought is None
    assert code == content


def test_execution_parser_rejects_bare_code_when_prefixed_by_explanation():
    parser = ExecutionResponseParser()

    content = (
        "Here is the plan before I write code.\n"
        "tables = load_all_tables()\n"
        "create_output_sheet('Output')\n"
        "saved_file = save_workbook_to(output_path)\n"
        "saved_file"
    )

    thought, code = parser.parse(content)

    assert thought == content
    assert code is None


def test_offline_understanding_prompt_stays_compact_for_real_multi_file_task():
    dataset_root = Path(__file__).resolve().parents[2] / "dataset" / "DevelopmentBenchmark"
    tasks = json.loads((dataset_root / "dataset.json").read_text(encoding="utf-8"))
    task = next(item for item in tasks if item["task_id"] == "Test 2")
    input_paths = [str((dataset_root / rel).resolve()) for rel in task["spreadsheets"]]

    config = Config()
    sandbox = Sandbox(
        excel_paths=input_paths,
        output_preferences={"mode": "file"},
        output_path=str(Path("artifacts/output/test_understanding_prompt.xlsx").resolve()),
        enabled_namespaces=["spreadsheet"],
        load_excel=True,
    )
    context = ExcelContextBuilder(input_paths, sandbox.workbooks).build(config.total_token_budget)
    prompt = PromptBuilder(profile="offline_strict").build_understanding_prompt(
        task["prompt"],
        context,
        "",
    )

    assert "- Preview rows" not in context
    assert len(context) <= 1600
    assert len(prompt) <= 3200


def test_default_spreadsheet_context_includes_small_preview_for_few_workbooks():
    dataset_root = Path(__file__).resolve().parents[2] / "dataset" / "DevelopmentBenchmark"
    input_paths = [str((dataset_root / "Task01" / "tc01_input01.xlsx").resolve())]

    config = Config()
    sandbox = Sandbox(
        excel_paths=input_paths,
        output_preferences={"mode": "file"},
        output_path=str(Path("artifacts/output/test_context_preview.xlsx").resolve()),
        enabled_namespaces=["spreadsheet"],
        load_excel=True,
    )

    context = ExcelContextBuilder(input_paths, sandbox.workbooks).build(config.total_token_budget)

    assert "- Preview rows (5 shown," in context
    assert "  - r1:" in context
    assert "  - r5:" in context
    assert "  - r6:" not in context


def test_default_spreadsheet_context_stays_header_only_for_many_workbooks():
    dataset_root = Path(__file__).resolve().parents[2] / "dataset" / "DevelopmentBenchmark"
    input_paths = [
        str((dataset_root / "Task02" / f"tc02_input0{index}.csv").resolve())
        for index in range(1, 6)
    ]

    config = Config()
    sandbox = Sandbox(
        excel_paths=input_paths,
        output_preferences={"mode": "file"},
        output_path=str(Path("artifacts/output/test_context_header_only.xlsx").resolve()),
        enabled_namespaces=["spreadsheet"],
        load_excel=True,
    )

    context = ExcelContextBuilder(input_paths, sandbox.workbooks).build(config.total_token_budget)

    assert "- Candidate headers:" in context
    assert "- Preview rows" not in context
