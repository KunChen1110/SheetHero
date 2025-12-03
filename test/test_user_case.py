#!/usr/bin/env python3
"""
Batch dataset tester.

Usage examples:
    # Run specific tests (Test 1~5)
    python3 test_user_case.py --tests 1 2 3 4 5

    # Run a continuous range (Test 1~10)
    python3 test_user_case.py --range 1 10

Outputs:
    - test/output.json
    - test/Task01_output/...
    - test/Task02_output/...
      Each TaskXX_output folder will contain:
        * The generated Excel file (if any)
        * README.md (copied logger content for that task)
"""

import argparse
import json
import subprocess
import sys
import shutil
from pathlib import Path
from typing import List, Dict, Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_RUN = PROJECT_ROOT / "src" / "backend" / "datasetRun.py"
DATASET_DIR = PROJECT_ROOT / "dataset"
TEST_OUTPUT_DIR = PROJECT_ROOT / "test"
SUMMARY_JSON = TEST_OUTPUT_DIR / "output.json"


def get_expected_output_path_for_test(test_n: int) -> Path | None:
    """
    Reconstruct the expected Excel output path for a given test number,
    using the same logic as src/backend/datasetRun.py, but without
    modifying or importing it.
    """
    json_path = DATASET_DIR / "dataset.json"
    if not json_path.exists():
        return None

    try:
        with json_path.open("r", encoding="utf-8") as f:
            tasks = json.load(f)
    except Exception:
        return None

    task_id = f"Test {test_n}"
    task = None
    for t in tasks:
        if t.get("task_id") == task_id:
            task = t
            break

    if task is None:
        return None

    spreadsheets = task.get("spreadsheets") or []
    expected_output_file = task.get("expected_output_file") or []

    # Mirror datasetRun.determine_output_path logic
    if spreadsheets:
        first_input = DATASET_DIR / spreadsheets[0]
        output_dir = first_input.parent
    elif expected_output_file:
        expected_path = DATASET_DIR / expected_output_file[0]
        output_dir = expected_path.parent
    else:
        task_num = str(test_n)
        output_dir = DATASET_DIR / f"Task{task_num.zfill(2)}"

    output_filename = task_id.lower().replace(" ", "") + "_output.xlsx"
    output_path = (output_dir / output_filename).resolve()
    return output_path


def run_single_test(test_n: int, output_mode: str) -> Dict[str, Any]:
    """
    Run a single TestN by invoking datasetRun.py as a subprocess.

    This does NOT modify any backend code. It simply shells out to the
    existing runner and captures stdout/stderr and return code.

    Returns a dict containing:
      - test_id: "Test N"
      - test_number: N (int)
      - return_code: subprocess return code
      - stdout: captured standard output
      - stderr: captured standard error
      - answer: same as stdout (for now)
      - output_file_path: best-effort extraction of an .xlsx path from stdout
        (only meaningful when running in 'file' output mode)
    """
    cmd = [
        sys.executable,
        str(DATASET_RUN),
        "--test-n",
        str(test_n),
        "--dataset-dir",
        str(DATASET_DIR),
    ]

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )

    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()

    result: Dict[str, Any] = {
        "test_id": f"Test {test_n}",
        "test_number": test_n,
        "return_code": proc.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "answer": None,
        "output_file_path": None,
    }

    # For now we treat the whole stdout as the "answer".
    result["answer"] = stdout

    # Best-effort extraction of an Excel output path from stdout.
    # Prefer the LAST .xlsx token (usually the "Result file saved to" line),
    # so we don't accidentally pick up input files like tc01_input01.xlsx.
    path_candidates = [
        token
        for token in stdout.split()
        if token.endswith(".xlsx") and "/" in token
    ]
    if path_candidates:
        result["output_file_path"] = path_candidates[-1]

    # Fallback: if stdout does not contain a usable .xlsx path,
    # reconstruct the expected path from dataset.json.
    if result["output_file_path"] is None:
        expected = get_expected_output_path_for_test(test_n)
        if expected is not None:
            result["output_file_path"] = str(expected)

    return result


def ensure_task_output_dirs(test_ids: List[int]) -> None:
    """
    Ensure a TaskXX_output folder exists for each requested test under test/.

    This only creates folders; it does not move or copy any files yet.
    """
    for n in test_ids:
        task_dir_name = f"Task{str(n).zfill(2)}_output"
        out_dir = TEST_OUTPUT_DIR / task_dir_name
        out_dir.mkdir(exist_ok=True)


def find_latest_logger_for_test(test_n: int) -> Path | None:
    """
    Find the latest logger markdown file for a given test number.

    Log files follow the pattern: sheethero_tcXX_*.md under src/backend/loggers.
    Returns the most recent one, or None if not found.
    """
    log_dir = PROJECT_ROOT / "src" / "backend" / "loggers"
    if not log_dir.exists():
        return None

    pattern = f"sheethero_tc{str(test_n).zfill(2)}_*.md"
    candidates = list(log_dir.glob(pattern))
    if not candidates:
        return None

    try:
        latest = max(candidates, key=lambda p: p.stat().st_mtime)
    except Exception:
        return None

    return latest


def copy_outputs_to_task_dirs(results: List[Dict[str, Any]]) -> None:
    """
    For each test result, copy the generated Excel file (if any) into
    the corresponding test/TaskXX_output folder and write README.md
    containing the logger content for that task (if available).

    This keeps backend code untouched and only operates on files.
    """
    for res in results:
        test_n = res.get("test_number")
        if test_n is None:
            continue

        task_dir_name = f"Task{str(test_n).zfill(2)}_output"
        out_dir = TEST_OUTPUT_DIR / task_dir_name
        out_dir.mkdir(exist_ok=True)

        # Copy Excel output file into TaskXX_output, if path is known and exists
        output_path_str = res.get("output_file_path")
        if output_path_str:
            src = Path(output_path_str)
            if not src.is_absolute():
                # Interpret relative paths with respect to project root
                src = (PROJECT_ROOT / output_path_str).resolve()

            if src.exists():
                dest = out_dir / src.name
                try:
                    shutil.copy2(src, dest)
                    # Update recorded output path to point to test/TaskXX_output
                    res["output_file_path"] = str(dest)

                    # If the original file lives under dataset/, treat it as a backup
                    # and remove it after copying to test/TaskXX_output.
                    try:
                        if DATASET_DIR in src.parents and src.is_file():
                            src.unlink()
                    except Exception as e:
                        res.setdefault("delete_errors", [])
                        res["delete_errors"].append(
                            f"Failed to delete backup file {src}: {e}"
                        )
                except Exception as e:
                    # Record copy error into the result for visibility
                    res.setdefault("copy_errors", [])
                    res["copy_errors"].append(
                        f"Failed to copy {src} -> {dest}: {e}"
                    )

        # Copy latest logger file into a per-test logger file for this task, if available
        try:
            logger_filename = f"Test{test_n}_logger.md"
            logger_path = find_latest_logger_for_test(test_n)
            if logger_path and logger_path.exists():
                dest_logger = out_dir / logger_filename
                shutil.copy2(logger_path, dest_logger)

                # Remove original verbose log under src/backend/loggers
                try:
                    logger_path.unlink()
                except Exception as e:
                    res.setdefault("delete_errors", [])
                    res["delete_errors"].append(
                        f"Failed to delete logger file {logger_path}: {e}"
                    )
            else:
                # Fallback: write a simple logger file if no logger is found
                fallback = out_dir / logger_filename
                with fallback.open("w", encoding="utf-8") as f:
                    f.write(f"No logger file found for Test {test_n}.\n")
        except Exception as e:
            res.setdefault("write_errors", [])
            res["write_errors"].append(
                f"Failed to prepare README.md in {out_dir}: {e}"
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch runner for dataset tests")
    parser.add_argument(
        "--tests",
        nargs="+",
        type=int,
        help="Explicit list of test numbers, e.g. --tests 1 2 3 4 5",
    )
    parser.add_argument(
        "--range",
        nargs=2,
        type=int,
        metavar=("START", "END"),
        help="Inclusive range of test numbers, e.g. --range 1 5",
    )
    parser.add_argument(
        "--output-mode",
        type=str,
        choices=["file", "text"],
        default="file",
        help="Output mode to use when calling datasetRun.py: "
             "'file' (default) to generate Excel outputs, or 'text' to only "
             "produce textual answers without writing result workbooks.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not DATASET_RUN.exists():
        print(f"datasetRun.py not found at: {DATASET_RUN}", file=sys.stderr)
        sys.exit(1)

    # Decide which test numbers to run
    test_ids: List[int] = []
    if args.tests:
        test_ids.extend(args.tests)
    if args.range:
        start, end = args.range
        test_ids.extend(list(range(start, end + 1)))

    if not test_ids:
        print("Please specify tests via --tests or --range", file=sys.stderr)
        sys.exit(1)

    # Deduplicate and sort
    test_ids = sorted(set(test_ids))

    # Ensure test/ directory exists
    TEST_OUTPUT_DIR.mkdir(exist_ok=True)

    # Ensure TaskXX_output folders exist under dataset/
    ensure_task_output_dirs(test_ids)

    results: List[Dict[str, Any]] = []

    # Run each test sequentially
    for n in test_ids:
        print(f"Running Test {n} ...")
        res = run_single_test(n, args.output_mode)
        results.append(res)
        status = "OK" if res["return_code"] == 0 else "FAIL"
        print(f"  Test {n}: {status}")

    # Copy outputs and write per-task output.txt into TaskXX_output
    copy_outputs_to_task_dirs(results)

    # Build compact summary records for output.json
    summary_records: List[Dict[str, Any]] = []
    for res in results:
        summary_records.append(
            {
                "task_id": res.get("test_id"),
                "answer": res.get("answer"),
                "output_file": res.get("output_file_path"),
            }
        )

    # Write global summary JSON into test/output.json
    with SUMMARY_JSON.open("w", encoding="utf-8") as f:
        json.dump(summary_records, f, ensure_ascii=False, indent=2)

    print(f"\nSummary written to: {SUMMARY_JSON}")


if __name__ == "__main__":
    main()
