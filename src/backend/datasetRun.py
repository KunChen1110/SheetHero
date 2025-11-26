#!/usr/bin/env python3
"""
Dataset Runner - Unified Test Execution Script

Usage:
    python3 datasetRun.py --test-n 2
"""

import sys
import json
import argparse
import logging
from pathlib import Path
from typing import Dict, Any, List

from core.agent import SheetBrain
from config.settings import Config
from utils.output_formatter import format_output_user_mode, format_output_verbose_mode
from utils.logger import set_log_level


def load_dataset_json(dataset_dir: Path) -> List[Dict[str, Any]]:
    """Load dataset.json file"""
    json_path = dataset_dir / "dataset.json"
    if not json_path.exists():
        raise FileNotFoundError(f"dataset.json file not found: {json_path}")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def find_task_by_id(tasks: List[Dict[str, Any]], test_n: int) -> Dict[str, Any]:
    """Find corresponding task by test_n"""
    task_id = f"Test {test_n}"
    for task in tasks:
        if task.get("task_id") == task_id:
            return task
    
    available_ids = [t.get("task_id") for t in tasks]
    raise ValueError(
        f"Task '{task_id}' not found. "
        f"Available task IDs: {', '.join(available_ids)}"
    )


def build_input_paths(dataset_dir: Path, spreadsheets: List[str]) -> List[str]:
    """Build full paths for input files"""
    input_paths = []
    for spreadsheet in spreadsheets:
        full_path = dataset_dir / spreadsheet
        if not full_path.exists():
            raise FileNotFoundError(f"Input file not found: {full_path}")
        input_paths.append(str(full_path.absolute()))
    return input_paths


def determine_output_path(dataset_dir: Path, spreadsheets: List[str], task_id: str, 
                          expected_output_file: List[str] = None) -> str:
    """Determine output file path"""
    if expected_output_file is None:
        expected_output_file = []
    
    if spreadsheets:
        first_input = dataset_dir / spreadsheets[0]
        output_dir = first_input.parent
    elif expected_output_file and len(expected_output_file) > 0:
        expected_path = dataset_dir / expected_output_file[0]
        output_dir = expected_path.parent
    else:
        task_num = task_id.replace("Test ", "").strip()
        output_dir = dataset_dir / f"Task{task_num.zfill(2)}"
    
    output_filename = task_id.lower().replace(" ", "") + "_output.xlsx"
    output_path = output_dir / output_filename
    
    return str(output_path.absolute())


def main():
    parser = argparse.ArgumentParser(description="Dataset Runner - Unified Test Execution Script")
    
    parser.add_argument("--test-n", type=int, required=True,
                        help="Test task number (e.g., 1, 2, 3...)")
    parser.add_argument("--dataset-dir", type=str, default=None,
                        help="Dataset directory path (default: dataset folder in project root)")
    parser.add_argument("--verbose", action="store_true", default=False,
                        help="Enable verbose output mode")
    
    args = parser.parse_args()
    
    try:
        # Determine dataset directory
        if args.dataset_dir:
            dataset_dir = Path(args.dataset_dir).resolve()
        else:
            CURRENT_DIR = Path(__file__).parent
            project_root = CURRENT_DIR.parent.parent
            dataset_dir = project_root / "dataset"
        
        if not dataset_dir.exists():
            raise FileNotFoundError(f"Dataset directory not found: {dataset_dir}")
        
        # Load JSON and find task
        tasks = load_dataset_json(dataset_dir)
        task = find_task_by_id(tasks, args.test_n)
        
        # Build input paths
        spreadsheets = task.get("spreadsheets", [])
        if not spreadsheets:
            raise ValueError("This task has no input files")
        
        input_paths = build_input_paths(dataset_dir, spreadsheets)
        
        # Determine output path
        expected_output_file = task.get("expected_output_file", [])
        output_path = determine_output_path(
            dataset_dir, spreadsheets, task['task_id'], expected_output_file
        )
        
        # Configure and run
        config = Config()
        config.output_mode = "file"
        config.output_file = output_path
        config.verbose = args.verbose
        
        log_level = logging.INFO if config.verbose else logging.ERROR
        set_log_level(log_level)
        
        agent = SheetBrain(excel_paths=input_paths, config=config)
        result = agent.run(user_question=task.get("prompt", ""))
        
        # Display Results based on verbose mode
        if config.verbose:
            output = format_output_verbose_mode(result, input_paths, task.get("prompt", ""))
        else:
            output = format_output_user_mode(
                result,
                input_paths,
                task.get("prompt", ""),
                output_mode=config.output_mode
            )
        
        print(output)
        
        sys.exit(0 if result['success'] else 1)
        
    except Exception as e:
        print(f"❌ Error: {str(e)}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
