#!/usr/bin/env python3
"""Run understanding stage for a dataset entry and save the markdown report."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from openai import OpenAI


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_tasks(dataset_dir: Path) -> list[dict]:
    candidates = [
        dataset_dir / "dataset.json",
        _repo_root() / "dataset.json",
    ]
    for path in candidates:
        if path.exists():
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
    raise FileNotFoundError("dataset.json not found in dataset/ or repo root.")


def _select_task(tasks: list[dict], test_id: int) -> dict:
    if test_id <= 0 or test_id > len(tasks):
        raise ValueError(f"test id out of range: {test_id} (valid range 1..{len(tasks)})")
    return tasks[test_id - 1]


def _build_input_paths(dataset_dir: Path, spreadsheets: list[str]) -> list[str]:
    paths: list[str] = []
    for rel in spreadsheets:
        full_path = dataset_dir / rel
        if not full_path.exists():
            raise FileNotFoundError(f"Input file not found: {full_path}")
        paths.append(str(full_path.resolve()))
    return paths


class _CliProgressLogger:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def log(self, message: str, to_terminal: bool = False) -> None:
        print(message)
        self.lines.append(message)

    def log_raw(self, message: str) -> None:
        print(message)
        self.lines.append(message)

    def write_report(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        content = "\n".join(self.lines).strip()
        if not content:
            content = "(empty)"
        path.write_text(content + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run understanding stage for a dataset entry and save the markdown report."
    )
    parser.add_argument(
        "--test-id",
        type=int,
        required=True,
        help="Dataset entry index (1-based, e.g. 1 maps to the first task).",
    )
    parser.add_argument(
        "--dataset-dir",
        type=str,
        default=str(_repo_root() / "dataset"),
        help="Path to dataset directory (default: ./dataset).",
    )
    args = parser.parse_args()

    repo_root = _repo_root()
    sys.path.insert(0, str(repo_root))

    from backend.config.settings import Config
    from backend.environment import Sandbox
    from backend.stages.understanding.context_builder import ExcelContextBuilder
    from backend.stages.understanding.stage import UnderstandingStage

    dataset_dir = Path(args.dataset_dir)
    tasks = _load_tasks(dataset_dir)
    task = _select_task(tasks, args.test_id)

    spreadsheets = task.get("spreadsheets", [])
    if not spreadsheets:
        raise ValueError("Selected task has no input spreadsheets.")

    input_paths = _build_input_paths(dataset_dir, spreadsheets)

    config = Config()
    if not config.api_key:
        raise ValueError("OpenAI API key is missing in Config")

    client_kwargs = {"api_key": config.api_key}
    if config.base_url:
        client_kwargs["base_url"] = config.base_url
    client = OpenAI(**client_kwargs)

    output_path = repo_root / "artifacts" / "tests" / "understanding_output.xlsx"
    sandbox = Sandbox(
        excel_paths=input_paths,
        output_preferences={"mode": "text", "file_path": None},
        output_path=str(output_path),
        enabled_namespaces=["spreadsheet"],
        load_excel=True,
    )

    progress_logger = _CliProgressLogger()
    understanding = UnderstandingStage(
        client,
        config.deployment,
        progress_logger=progress_logger,
    )

    context_builder = ExcelContextBuilder(input_paths, sandbox.workbooks)
    understanding_context = context_builder.build(config.total_token_budget)
    understanding_output = understanding.run(
        task.get("prompt", ""),
        understanding_context,
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = (
        repo_root
        / "artifacts"
        / "test_report"
        / "understanding"
        / f"understanding_{timestamp}.md"
    )
    progress_logger.write_report(report_path)

    print(f"Task: {task.get('task_id', 'Unknown')} - {task.get('title', '')}".strip())
    print("\nUnderstanding output:")
    print(understanding_output or "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
