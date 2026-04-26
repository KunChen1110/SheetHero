#!/usr/bin/env python3
"""Test script for UnderstandingStage - generates analysis from Excel context."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _repo_root() -> Path:
    """Go 3 levels up from test/stages/understanding_test.py to repo root."""
    return Path(__file__).resolve().parents[2]


def _development_dataset_dir() -> Path:
    return _repo_root() / "dataset" / "DevelopmentBenchmark"


def _load_tasks(dataset_dir: Path) -> list[dict]:
    candidates = [
        dataset_dir / "dataset.json",
        _development_dataset_dir() / "dataset.json",
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


def estimate_tokens(text: str) -> int:
    """Rough estimate: 4 characters ≈ 1 token."""
    return len(text) // 4


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Test UnderstandingStage - generates analysis plan."
    )
    parser.add_argument("--test-id", type=int, required=True, help="Dataset entry index")
    parser.add_argument("--dataset-dir", type=str, default=str(_development_dataset_dir()))
    parser.add_argument("--model", type=str, default=None, help="Model override")
    parser.add_argument("--max-files", type=int, default=2, help="Max files in schema")
    parser.add_argument("--token-budget", type=int, default=None, help="Token budget")
    parser.add_argument("--dry-run", action="store_true", help="Show prompt only")
    parser.add_argument("--enhance", type=str, default=None,
                        help="Test enhance() with validation feedback (JSON string)")

    args = parser.parse_args()

    repo_root = _repo_root()
    sys.path.insert(0, str(repo_root))

    from backend.config.settings import Config
    from backend.stages.understanding.stage import UnderstandingStage
    from backend.stages.understanding.context_builder import ExcelContextBuilder
    from backend.prompt.prompt_builder import PromptBuilder

    config = Config()
    model = args.model or config.deployment
    # Understanding uses 2x budget in stage
    token_budget = args.token_budget or min(config.total_token_budget, 3000)

    dataset_dir = Path(args.dataset_dir)
    tasks = _load_tasks(dataset_dir)

    if args.test_id < 0 or args.test_id >= len(tasks):
        raise ValueError(f"Invalid test_id: {args.test_id}")

    task = tasks[args.test_id]
    spreadsheets = task.get("spreadsheets", [])
    user_question = task.get("prompt", "Analyze the data.")

    if not spreadsheets:
        raise ValueError("Selected task has no input spreadsheets.")

    input_paths = _build_input_paths(dataset_dir, spreadsheets)

    print(f"=== UNDERSTANDING TEST ===")
    print(f"Task: {task.get('task_id', '?')} - {task.get('title', '')}")
    print(f"Query: {user_question[:80]}...")
    print(f"Model: {model}")
    print(f"Token budget: {token_budget} (stage uses 2x = {token_budget * 2})")
    print(f"Files: {len(spreadsheets)}")
    print("-" * 50)

    # Build schema manually (like stage does)
    from backend.environment import Sandbox

    sandbox = Sandbox(
        excel_paths=input_paths,
        output_preferences={"mode": "text"},
        output_path=str(repo_root / "artifacts" / "tests" / "understanding_temp.xlsx"),
        enabled_namespaces=["spreadsheet"],
        load_excel=True,
    )

    workbooks = getattr(sandbox, "workbooks", {}) or {}

    # Build context with 2x budget (as stage does)
    raw_schema = ExcelContextBuilder(
        excel_paths=list(workbooks.keys()),
        workbooks=workbooks
    ).build(total_token_budget=token_budget * 2)

    # Limit files for display/budget
    schema_summary = limit_files_in_schema(raw_schema, max_files=args.max_files)
    schema_tokens = estimate_tokens(schema_summary)

    print(f"Schema tokens: ~{schema_tokens}")

    if args.dry_run:
        print("\n[DRY RUN] Prompt preview:")
        prompt = PromptBuilder().build_understanding_prompt(user_question, schema_summary)
        print(f"\nPrompt ({estimate_tokens(prompt)} tokens):")
        print(prompt[:1500] + "..." if len(prompt) > 1500 else prompt)
        return 0

    # Setup stage
    from openai import OpenAI

    client_kwargs = {"api_key": config.api_key}
    if config.base_url:
        client_kwargs["base_url"] = config.base_url
    client = OpenAI(**client_kwargs)

    understanding_stage = UnderstandingStage(
        client=client,
        deployment=model,
        excel_paths=input_paths,
        workbooks=workbooks,
        total_token_budget=token_budget,
        load_excel=True,
        progress_logger=None
    )

    # Mock mode
    if os.environ.get("MOCK_LLM", "").lower() == "true":
        print("\n[MOCK MODE] Simulating understanding...")
        understanding = (
            f"## Analysis Plan\n\n"
            f"### Task Understanding\n"
            f"The user wants to: {user_question[:50]}...\n\n"
            f"### Data Overview\n"
            f"- {len(spreadsheets)} file(s) to analyze\n"
            f"- Key operations: load, examine, calculate\n\n"
            f"### Execution Strategy\n"
            f"1. Load all data files\n"
            f"2. Validate data integrity\n"
            f"3. Perform requested calculations\n"
            f"4. Format and return results"
        )
    else:
        print(f"\n[API CALL] Generating understanding with {model}...")

        if args.enhance:
            # Test enhance() method
            print("[ENHANCE MODE] Testing enhance() with feedback...")
            initial = "Initial understanding: analyze spending data."
            validation = json.loads(args.enhance)
            understanding = understanding_stage.enhance(initial, validation)
        else:
            # Normal run()
            understanding = understanding_stage.run(
                user_question=user_question,
                spreadsheet_context=schema_summary
            )

    print(f"\n=== UNDERSTANDING OUTPUT ===")
    print(understanding[:2000] if len(understanding) > 2000 else understanding)

    if len(understanding) > 2000:
        print(f"\n[... {len(understanding) - 2000} more characters ...]")

    print(f"\nOutput length: {len(understanding)} chars (~{estimate_tokens(understanding)} tokens)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
