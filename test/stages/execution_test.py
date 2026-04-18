#!/usr/bin/env python3
"""Test script for ExecutionStage - mocks understanding, tests execution in isolation."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from openai import OpenAI


def _repo_root() -> Path:
    """Go 3 levels up from test/stages/execution_test.py to repo root."""
    return Path(__file__).resolve().parents[2]


def _load_tasks(dataset_dir: Path) -> list[dict]:
    candidates = [
        dataset_dir / "dataset.json",
        _repo_root() / "dataset" / "dataset.json",
        ]
    for path in candidates:
        if path.exists():
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
    raise FileNotFoundError(f"dataset.json not found. Checked: {[str(c) for c in candidates]}")


def _build_input_paths(dataset_dir: Path, spreadsheets: list[str]) -> list[str]:
    paths: list[str] = []
    for rel in spreadsheets:
        full_path = dataset_dir / rel
        if not full_path.exists():
            raise FileNotFoundError(f"Input file not found: {full_path}")
        paths.append(str(full_path.resolve()))
    return paths


def _build_output_instruction(mode: str = "text", output_path: str = "") -> str:
    """Copy of SheetHero._build_output_instruction()"""
    if mode == "file":
        return (
            "**OUTPUT REQUIREMENTS:**\n"
            f"1. Save final results to: `output_path` (variable available in code: \"{output_path}\")\n"
            "2. Use the UNIFIED OUTPUT WORKFLOW:\n"
            "   - Convert DataFrame to 2D list: `[df.columns.tolist()] + df.values.tolist()`\n"
            "   - Create output sheet: `create_output_sheet(\"Output\")`\n"
            "   - Write data: `write_dataframe_to_sheet(data_2d, \"Output\", \"A1\")`\n"
            "   - Add summary if needed: `add_summary_row(\"Output\", row_num, {\"Total\": val, \"Average\": avg})`\n"
            "   - Highlight important rows: `highlight_rows(\"Output\", [row_nums], {\"fill_color\": \"red\"})`\n"
            "   - Save: `save_workbook_to(output_path)`\n"
            "3. Return the saved file path in Final Answer\n"
            "4. DO NOT use DataFrame.to_excel() or pd.ExcelWriter()"
        )

    return (
        "Final results must be presented directly in the final answer as a clean markdown "
        "table or list. Do not save any files unless the user explicitly asks."
    )


def build_minimal_system_prompt(output_instruction: str) -> str:
    """Minimal system prompt for testing (saves tokens)."""
    return (
        "You are an Excel data analyst with Python access.\n\n"
        "Respond in ONE of these formats:\n\n"
        "FORMAT 1 - Code:\n"
        "**Thought:** Reasoning\n\n"
        "```python\n# Code to execute\n```\n\n"
        "FORMAT 2 - Final Answer:\n"
        "**Thought:** Reasoning\n\n"
        "Final Answer: Your answer\n\n"
        f"{output_instruction}\n\n"
        "Pre-loaded: pandas as pd, openpyxl. Access data via workbook_view dict."
    )


def limit_files_in_schema(schema_summary: str, max_files: int = 2) -> str:
    """Limit schema to max_files while showing total count."""
    parts = schema_summary.split('============================================================')

    if len(parts) < 2:
        return schema_summary

    header = parts[0]
    file_sections = parts[1:]
    total_files = len(file_sections)

    if total_files <= max_files:
        return schema_summary

    header = header.replace(
        f"({total_files} files)",
        f"({total_files} files total, showing first {max_files})"
    )

    kept = file_sections[:max_files]
    result = header + '============================================================'
    result += '============================================================'.join(kept)
    result += f"\n\n[... {total_files - max_files} additional files not shown ...]"

    return result


def truncate_data_preview(schema_summary: str, max_chars: int = 600) -> str:
    """Truncate data sections."""
    import re
    pattern = r'(Data:\s*\n\s*)(\|[^\n]*(?:\n\|[^\n]*)*)'

    def truncate_match(match):
        header, data = match.group(1), match.group(2)
        if len(data) <= max_chars:
            return match.group(0)
        truncated = data[:max_chars]
        last_row = truncated.rfind('|\n|')
        if last_row > max_chars * 0.6:
            truncated = truncated[:last_row + 1]
        return header + truncated + '\n[... data truncated ...]'

    return re.sub(pattern, truncate_match, schema_summary, flags=re.DOTALL)


def estimate_tokens(text: str) -> int:
    """Rough estimate: 4 characters ≈ 1 token."""
    return len(text) // 4


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Test ExecutionStage with mocked understanding."
    )
    parser.add_argument("--test-id", type=int, required=True, help="Dataset entry index")
    parser.add_argument("--dataset-dir", type=str, default=str(_repo_root() / "dataset"))
    parser.add_argument("--model", type=str, default=None, help="Model override")
    parser.add_argument("--output-mode", type=str, choices=["text", "file"], default="text",
                        help="Output mode: text (return answer) or file (save to Excel)")
    parser.add_argument("--max-files", type=int, default=2, help="Max files in schema")
    parser.add_argument("--max-turns", type=int, default=10, help="Max execution turns")
    parser.add_argument("--token-budget", type=int, default=None, help="Token budget")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show first prompt only, don't call API")
    parser.add_argument("--understanding", type=str, default=None,
                        help="Custom understanding text (default: auto-generated mock)")

    args = parser.parse_args()

    repo_root = _repo_root()
    sys.path.insert(0, str(repo_root))

    from backend.config.settings import Config
    from backend.environment import Sandbox
    from backend.stages.execution.stage import ExecutionStage
    from backend.stages.understanding.context_builder import ExcelContextBuilder
    from backend.prompt.prompt_builder import PromptBuilder

    config = Config()
    model = args.model or config.deployment
    token_budget = args.token_budget or min(config.total_token_budget, 4000)

    dataset_dir = Path(args.dataset_dir)
    tasks = _load_tasks(dataset_dir)

    if args.test_id < 0 or args.test_id >= len(tasks):
        raise ValueError(f"Invalid test_id: {args.test_id}")

    task = tasks[args.test_id]
    spreadsheets = task.get("spreadsheets", [])
    user_query = task.get("prompt", "Analyze the data.")

    if not spreadsheets:
        raise ValueError("Selected task has no input spreadsheets.")

    input_paths = _build_input_paths(dataset_dir, spreadsheets)

    # Setup client
    client_kwargs = {"api_key": config.api_key}
    if config.base_url:
        client_kwargs["base_url"] = config.base_url
    client = OpenAI(**client_kwargs)

    # Setup sandbox
    output_path = repo_root / "artifacts" / "tests" / "execution_output.xlsx"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    sandbox = Sandbox(
        excel_paths=input_paths,
        output_preferences={"mode": args.output_mode, "file_path": str(output_path)},
        output_path=str(output_path),
        enabled_namespaces=["spreadsheet"],
        load_excel=True,
    )

    # Build execution context (schema)
    workbooks = getattr(sandbox, "workbooks", {}) or {}
    raw_schema = ExcelContextBuilder(
        excel_paths=list(workbooks.keys()),
        workbooks=workbooks
    ).build(total_token_budget=9999)

    schema_summary = limit_files_in_schema(raw_schema, max_files=args.max_files)
    schema_summary = truncate_data_preview(schema_summary, max_chars=800)

    # Check token usage
    schema_tokens = estimate_tokens(schema_summary)
    if schema_tokens > token_budget - 1500:
        print(f"WARNING: Schema ({schema_tokens} tokens) may exceed budget. Reducing...")
        schema_summary = limit_files_in_schema(raw_schema, max_files=1)
        schema_summary = truncate_data_preview(schema_summary, max_chars=400)
        schema_tokens = estimate_tokens(schema_summary)

    # Mock understanding output
    if args.understanding:
        understanding = args.understanding
    else:
        understanding = (
            f"Task: {user_query}\n\n"
            f"Analysis Plan:\n"
            f"1. Load the data from {len(spreadsheets)} file(s)\n"
            f"2. Examine the structure and columns\n"
            f"3. Perform necessary calculations or transformations\n"
            f"4. Provide the final answer in the requested format\n\n"
            f"Key considerations: Ensure data types are correct, handle any missing values, "
            f"and verify calculations before providing the final answer."
        )

    # Build output instruction
    output_instruction = _build_output_instruction(
        mode=args.output_mode,
        output_path=str(output_path)
    )

    # Setup execution stage
    execution_stage = ExecutionStage(
        client=client,
        deployment=model,
        sandbox=sandbox,
        output_instruction=output_instruction,
        progress_log_file=None
    )

    print(f"=== EXECUTION TEST ===")
    print(f"Task: {task.get('task_id', '?')} - {task.get('title', '')}")
    print(f"Query: {user_query[:80]}...")
    print(f"Model: {model}")
    print(f"Token budget: {token_budget} (schema: ~{schema_tokens})")
    print(f"Output mode: {args.output_mode}")
    print(f"Max turns: {args.max_turns}")
    print(f"Files: {len(spreadsheets)} (showing {min(args.max_files, len(spreadsheets))})")
    print("-" * 50)

    if args.dry_run:
        print("\n[DRY RUN] First prompt preview:")

        # Use MINIMAL system prompt instead of full one
        system_prompt = build_minimal_system_prompt(output_instruction)
        user_prompt = PromptBuilder().build_execution_user_prompt(
            schema_summary, user_query, understanding
        )

        sys_tokens = estimate_tokens(system_prompt)
        user_tokens = estimate_tokens(user_prompt)
        total = sys_tokens + user_tokens + 800  # +completion

        print(f"\nSystem ({sys_tokens} tokens):")
        print(system_prompt[:800] + "..." if len(system_prompt) > 800 else system_prompt)
        print(f"\nUser ({user_tokens} tokens):")
        print(user_prompt[:1000] + "..." if len(user_prompt) > 1000 else user_prompt)
        print(f"\n=== TOKEN ESTIMATE ===")
        print(f"System: {sys_tokens}")
        print(f"User: {user_tokens}")
        print(f"Completion reserve: 800")
        print(f"Total: ~{total} / {token_budget}")

        if total > token_budget:
            print(f"WARNING: Over budget by ~{total - token_budget} tokens!")
        else:
            print(f"✅ Within budget")
        return 0

    # Mock mode
    if os.environ.get("MOCK_LLM", "").lower() == "true":
        print("\n[MOCK MODE] Simulating execution...")
        result = {
            "success": True,
            "answer": "Mock execution result: Analysis complete. Total spending is $1,234.",
            "total_turns": 1,
            "execution_summary": {
                "total_code_executions": 2,
                "successful_executions": 2,
                "failed_executions": 0
            }
        }
    else:
        print(f"\n[API CALL] Running execution with {model}...")
        print("This may take a while (multiple turns possible)...")

        result = execution_stage.run(
            user_query=user_query,
            execution_context=schema_summary,
            understanding_output=understanding,
            max_turns=args.max_turns
        )

    # Display results
    print(f"\n=== RESULT ===")
    print(f"Success: {result.get('success')}")
    print(f"Total turns: {result.get('total_turns')}")

    summary = result.get('execution_summary', {})
    print(f"Code executions: {summary.get('total_code_executions', 0)} "
          f"(successful: {summary.get('successful_executions', 0)}, "
          f"failed: {summary.get('failed_executions', 0)})")

    print(f"\nAnswer:")
    answer = result.get('answer', 'No answer')
    print(answer[:500] + "..." if len(answer) > 500 else answer)

    if args.output_mode == "file":
        if output_path.exists():
            print(f"\n✅ Output file: {output_path} ({output_path.stat().st_size} bytes)")
        else:
            print(f"\n⚠️ Output file not created at: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())