#!/usr/bin/env python3
"""
Dataset Runner - Unified Test Execution Script

Usage:
    python3 test/core/run_test.py --test-n 1
    python3 test/core/run_test.py --test-n 3 --dataset-dir dataset
"""

import sys
import json
import argparse
import logging
from pathlib import Path
from typing import Dict, Any, List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Suppress all logging output before and after imports
def _silence_loggers():
    logging.getLogger().setLevel(logging.CRITICAL)
    root = logging.getLogger()
    for h in root.handlers[:]:
        if isinstance(h, logging.StreamHandler):
            root.removeHandler(h)
    for name in list(logging.Logger.manager.loggerDict.keys()):
        lg = logging.getLogger(name)
        lg.setLevel(logging.CRITICAL)
        for h in lg.handlers[:]:
            if isinstance(h, logging.StreamHandler):
                lg.removeHandler(h)

_silence_loggers()

from src.backend.service.sheethero_service import SheetHeroService
from src.backend.config.settings import Config

_silence_loggers()


class DatasetRunner:
    """Runs dataset tasks via SheetHeroService and prints a result summary."""

    def __init__(self, dataset_dir: Path):
        self.dataset_dir = dataset_dir

    def load_dataset_json(self) -> List[Dict[str, Any]]:
        json_path = self.dataset_dir / "dataset.json"
        if not json_path.exists():
            raise FileNotFoundError(f"dataset.json not found: {json_path}")
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def find_task_by_id(tasks: List[Dict[str, Any]], test_n: int) -> Dict[str, Any]:
        task_id = f"Test {test_n}"
        for task in tasks:
            if task.get("task_id") == task_id:
                return task
        available = [t.get("task_id") for t in tasks]
        raise ValueError(f"Task '{task_id}' not found. Available: {', '.join(available)}")

    def build_input_paths(self, spreadsheets: List[str]) -> List[str]:
        paths = []
        for name in spreadsheets:
            full = self.dataset_dir / name
            if not full.exists():
                raise FileNotFoundError(f"Input file not found: {full}")
            paths.append(str(full.absolute()))
        return paths

    def determine_output_path(self, task_id: str) -> str:
        output_dir = PROJECT_ROOT / "artifacts" / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = task_id.lower().replace(" ", "") + "_output.xlsx"
        return str((output_dir / filename).absolute())

    def run_task(self, test_n: int) -> int:
        tasks = self.load_dataset_json()
        task = self.find_task_by_id(tasks, test_n)

        spreadsheets = task.get("spreadsheets", [])
        if not spreadsheets:
            raise ValueError("Task has no input files")

        input_paths = self.build_input_paths(spreadsheets)
        output_path = self.determine_output_path(task["task_id"])
        prompt = task.get("prompt", "")

        config = Config()
        config.output_mode = "file"
        config.output_file = output_path

        service = SheetHeroService(config=config)
        response = service.submit_turn(prompt, input_paths)

        response_type = response.get("type", "")

        if response_type == "clarification":
            print(f"[CLARIFICATION REQUIRED] {response.get('message', '')}")
            return 1

        result = response.get("result") or {}
        success = bool(result.get("success", False))
        confidence = result.get("confidence_score", 0.0)
        duration = result.get("total_duration", 0.0)
        short_answer = str(result.get("short_answer") or response.get("message") or "").strip()

        print(f"Task:       {task['task_id']}")
        print(f"Prompt:     {prompt[:80]}{'...' if len(prompt) > 80 else ''}")
        print(f"Success:    {'YES' if success else 'NO'}")
        print(f"Confidence: {confidence:.2f}")
        print(f"Duration:   {duration:.2f}s")
        print(f"Output:     {output_path}")
        if short_answer:
            print(f"Summary:    {short_answer}")

        return 0 if success else 1


def main():
    parser = argparse.ArgumentParser(description="Dataset Runner")
    parser.add_argument("--test-n", type=int, required=True,
                        help="Task number to run (e.g. 1, 2, 3)")
    parser.add_argument("--dataset-dir", type=str, default=None,
                        help="Path to dataset directory (default: <project_root>/dataset)")
    args = parser.parse_args()

    dataset_dir = (
        Path(args.dataset_dir).resolve()
        if args.dataset_dir
        else PROJECT_ROOT / "dataset"
    )
    if not dataset_dir.exists():
        print(f"Error: dataset directory not found: {dataset_dir}", file=sys.stderr)
        sys.exit(1)

    runner = DatasetRunner(dataset_dir)
    sys.exit(runner.run_task(args.test_n))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
