#!/usr/bin/env python3
"""
Dataset Runner - Unified Test Execution Script

Usage:
    python3 datasetRun.py --test-n 1
"""

import sys
import json
import argparse
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

# Suppress all logging output to console BEFORE importing other modules
logging.getLogger().setLevel(logging.CRITICAL)
root_logger = logging.getLogger()
for handler in root_logger.handlers[:]:
    if isinstance(handler, logging.StreamHandler):
        root_logger.removeHandler(handler)

from .agent.core.SheetHero import SheetHero
from .config.settings import Config
from .agent.io.formatter import OutputFormatter

# Suppress all logging output AFTER importing modules (to catch any loggers created during import)
logging.getLogger().setLevel(logging.CRITICAL)
root_logger = logging.getLogger()
for handler in root_logger.handlers[:]:
    if isinstance(handler, logging.StreamHandler):
        root_logger.removeHandler(handler)

# Suppress all child loggers
for logger_name in list(logging.Logger.manager.loggerDict.keys()):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.CRITICAL)
    for handler in logger.handlers[:]:
        if isinstance(handler, logging.StreamHandler):
            logger.removeHandler(handler)


class DatasetRunner:
    """Runs dataset tasks with SheetHero and formats results."""

    def __init__(self, dataset_dir: Path, formatter: Optional[OutputFormatter] = None):
        self.dataset_dir = dataset_dir
        self.formatter = formatter or OutputFormatter()

    def load_dataset_json(self) -> List[Dict[str, Any]]:
        json_path = self.dataset_dir / "dataset.json"
        if not json_path.exists():
            raise FileNotFoundError(f"dataset.json file not found: {json_path}")

        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    @staticmethod
    def find_task_by_id(tasks: List[Dict[str, Any]], test_n: int) -> Dict[str, Any]:
        task_id = f"Test {test_n}"
        for task in tasks:
            if task.get("task_id") == task_id:
                return task

        available_ids = [t.get("task_id") for t in tasks]
        raise ValueError(
            f"Task '{task_id}' not found. "
            f"Available task IDs: {', '.join(available_ids)}"
        )

    def build_input_paths(self, spreadsheets: List[str]) -> List[str]:
        input_paths = []
        for spreadsheet in spreadsheets:
            full_path = self.dataset_dir / spreadsheet
            if not full_path.exists():
                raise FileNotFoundError(f"Input file not found: {full_path}")
            input_paths.append(str(full_path.absolute()))
        return input_paths

    def determine_output_path(self, spreadsheets: List[str], task_id: str,
                              expected_output_file: Optional[List[str]] = None) -> str:
        if expected_output_file is None:
            expected_output_file = []

        if spreadsheets:
            first_input = self.dataset_dir / spreadsheets[0]
            output_dir = first_input.parent
        elif expected_output_file and len(expected_output_file) > 0:
            expected_path = self.dataset_dir / expected_output_file[0]
            output_dir = expected_path.parent
        else:
            task_num = task_id.replace("Test ", "").strip()
            output_dir = self.dataset_dir / f"Task{task_num.zfill(2)}"

        output_filename = task_id.lower().replace(" ", "") + "_output.xlsx"
        output_path = output_dir / output_filename

        return str(output_path.absolute())

    def run_task(self, test_n: int) -> int:
        tasks = self.load_dataset_json()
        task = self.find_task_by_id(tasks, test_n)

        spreadsheets = task.get("spreadsheets", [])
        if not spreadsheets:
            raise ValueError("This task has no input files")

        input_paths = self.build_input_paths(spreadsheets)

        expected_output_file = task.get("expected_output_file", [])
        output_path = self.determine_output_path(
            spreadsheets,
            task['task_id'],
            expected_output_file
        )

        config = Config()
        config.output_mode = "file"
        config.output_file = output_path

        agent = SheetHero(excel_paths=input_paths, config=config)
        result = agent.run(user_question=task.get("prompt", ""))

        output = self.formatter.format_user_mode(
            result,
            input_paths,
            task.get("prompt", ""),
            output_mode=config.output_mode
        )

        print(output)
        return 0 if result['success'] else 1


def main():
    parser = argparse.ArgumentParser(
        description="Dataset Runner - Unified Test Execution Script"
    )

    parser.add_argument(
        "--test-n",
        type=int,
        required=True,
        help="Test task number (e.g., 1, 2, 3...)"
    )
    parser.add_argument(
        "--dataset-dir",
        type=str,
        default=None,
        help="Dataset directory path (default: dataset folder in project root)"
    )

    args = parser.parse_args()

    try:
        if args.dataset_dir:
            dataset_dir = Path(args.dataset_dir).resolve()
        else:
            current_dir = Path(__file__).parent
            project_root = current_dir.parent.parent
            dataset_dir = project_root / "dataset"

        if not dataset_dir.exists():
            raise FileNotFoundError(f"Dataset directory not found: {dataset_dir}")

        runner = DatasetRunner(dataset_dir)
        exit_code = runner.run_task(args.test_n)
        sys.exit(exit_code)

    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
