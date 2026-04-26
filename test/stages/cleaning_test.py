#!/usr/bin/env python3
"""Test script for DataCleaningStage - uses Config defaults with smart token management."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from openai import OpenAI


def _repo_root() -> Path:
    """Go 3 levels up from test/stages/cleaning_test.py to repo root."""
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
    """
    Intelligently limit schema to max_files while preserving header info.
    Shows 'X of Y files' so LLM knows there are more files.
    """
    parts = schema_summary.split('============================================================')

    if len(parts) < 2:
        return schema_summary

    header = parts[0]
    file_sections = parts[1:]
    total_files = len(file_sections)

    if total_files <= max_files:
        return schema_summary

    # Update header to show "showing X of Y files"
    header = header.replace(
        f"({total_files} files)",
        f"({total_files} files total, showing first {max_files})"
    )

    kept_sections = file_sections[:max_files]

    result = header + '============================================================'
    result += '============================================================'.join(kept_sections)
    result += f"\n\n[... {total_files - max_files} additional files not shown to save tokens ...]"

    return result


def truncate_data_preview(schema_summary: str, max_chars: int = 500) -> str:
    """Truncate long data sections after 'Data:' marker."""
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

        return header + truncated + '\n[... data truncated to save tokens ...]'

    return re.sub(pattern, truncate_match, schema_summary, flags=re.DOTALL)


def estimate_tokens(text: str) -> int:
    """Rough estimate: 4 characters ≈ 1 token."""
    return len(text) // 4


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Test DataCleaningStage with smart token management."
    )
    parser.add_argument("--test-id", type=int, required=True, help="Dataset entry index")
    parser.add_argument("--dataset-dir", type=str, default=str(_development_dataset_dir()))
    parser.add_argument("--actions", type=str, default=None, help='JSON array of actions (default: ["remove duplicate rows"])')
    parser.add_argument("--model", type=str, default=None, help="Model override (default: from Config)")
    parser.add_argument("--max-files", type=int, default=2, help="Max files to show in schema")
    parser.add_argument("--token-budget", type=int, default=None, help="Token budget override (default: from Config or 3500)")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no API call")

    args = parser.parse_args()

    repo_root = _repo_root()
    sys.path.insert(0, str(repo_root))

    from backend.config.settings import Config
    from backend.environment import Sandbox

    config = Config()

    # Use Config values as defaults, allow CLI override
    model = args.model or config.deployment  # Config has gpt-4o-mini already
    token_budget = args.token_budget or min(config.total_token_budget, 3500)  # Cap at 3500 even if Config says 5000
    actions = json.loads(args.actions) if args.actions else ["remove duplicate rows"]

    dataset_dir = Path(args.dataset_dir)
    tasks = _load_tasks(dataset_dir)

    if args.test_id < 0 or args.test_id >= len(tasks):
        raise ValueError(f"Invalid test_id: {args.test_id}")

    task = tasks[args.test_id]
    spreadsheets = task.get("spreadsheets", [])

    if not spreadsheets:
        raise ValueError("Selected task has no input spreadsheets.")

    input_paths = _build_input_paths(dataset_dir, spreadsheets)

    # Setup API client
    client_kwargs = {"api_key": config.api_key}
    if config.base_url:
        client_kwargs["base_url"] = config.base_url
    client = OpenAI(**client_kwargs)

    # Setup sandbox
    output_path = repo_root / "artifacts" / "tests" / "cleaning_output.xlsx"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    sandbox = Sandbox(
        excel_paths=input_paths,
        output_preferences={"mode": "excel", "file_path": str(output_path)},
        output_path=str(output_path),
        enabled_namespaces=["spreadsheet"],
        load_excel=True,
    )

    # Build schema with smart limiting
    from backend.stages.understanding.context_builder import ExcelContextBuilder
    from backend.prompt.prompt_builder import PromptBuilder

    workbooks = getattr(sandbox, "workbooks", {}) or {}

    # Get full schema first
    raw_schema = ExcelContextBuilder(
        excel_paths=list(workbooks.keys()),
        workbooks=workbooks
    ).build(total_token_budget=9999)

    # Apply smart limits
    schema_summary = limit_files_in_schema(raw_schema, max_files=args.max_files)
    schema_summary = truncate_data_preview(schema_summary, max_chars=600)

    # Reserve tokens: 1000 for prompt wrapper + actions, 800 for completion
    schema_limit = token_budget - 1800
    if estimate_tokens(schema_summary) > schema_limit:
        # Emergency: reduce further
        schema_summary = limit_files_in_schema(raw_schema, max_files=1)
        schema_summary = truncate_data_preview(schema_summary, max_chars=400)

    # Build prompt
    prompt_text = PromptBuilder().build_cleaning_code_prompt(
        schema_summary=schema_summary,
        actions=actions
    )

    estimated_prompt = estimate_tokens(prompt_text)
    estimated_total = estimated_prompt + 800

    print(f"=== TOKEN ESTIMATE ===")
    print(f"Model: {model}")
    print(f"Budget: {token_budget}")
    print(f"Files in task: {len(spreadsheets)}")
    print(f"Files shown: {min(args.max_files, len(spreadsheets))}")
    print(f"Schema tokens: ~{estimate_tokens(schema_summary)}")
    print(f"Prompt tokens: ~{estimated_prompt}")
    print(f"Completion reserve: 800")
    print(f"Total estimate: ~{estimated_total} / {token_budget}")

    if estimated_total > token_budget:
        print(f"WARNING: Over budget! Reduce --max-files or increase --token-budget")

    if args.dry_run:
        print("\n[DRY RUN] Prompt preview:")
        print("-" * 50)
        print(prompt_text[:2000] + "..." if len(prompt_text) > 2000 else prompt_text)
        print("-" * 50)
        return 0

    # Mock mode check
    if os.environ.get("MOCK_LLM", "").lower() == "true":
        print("[MOCK MODE] Using fake response...")
        code = '''import json\nprint(json.dumps({"applied_actions": ["remove duplicate rows"], "skipped_actions": [], "notes": ["Mock"]}))'''
    else:
        print(f"\n[API CALL] Using {model}...")
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt_text}],
            max_tokens=800,
            temperature=0.1,
        )
        code = (response.choices[0].message.content or "").strip()

    print(f"Generated code: {len(code)} chars")

    # Execute
    try:
        result = sandbox.run(code)
        stdout = (result or {}).get("stdout", "")
        stderr = (result or {}).get("stderr", "")

        print("\n=== RESULT ===")
        print(f"stdout: {stdout[:1000] if stdout else '(empty)'}")
        if stderr:
            print(f"stderr: {stderr[:500]}")

        # Check if output file was actually created
        print(f"\n=== FILE CHECK ===")
        print(f"Expected output path: {output_path}")
        print(f"Path exists? {output_path.exists()}")
        if output_path.exists():
            print(f"✅ File created! Size: {output_path.stat().st_size} bytes")
        else:
            print("⚠️ WARNING: Output file was NOT created!")
            print("The generated code may not have saved the workbook.")
            # Check what files are in the directory
            output_dir = output_path.parent
            if output_dir.exists():
                existing = list(output_dir.glob("*"))
                print(f"Files in {output_dir}: {[f.name for f in existing] if existing else '(empty)'}")

    except Exception as exc:
        print(f"Execution failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
