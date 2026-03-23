#!/usr/bin/env python3
"""Lightweight benchmark runner for diagnose / QA regression."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.backend.diagnose_benchmark import DEFAULT_BENCHMARK_ROOT, run_diagnose_benchmark


def main() -> int:
    parser = argparse.ArgumentParser(description="Run lightweight diagnose benchmark regression.")
    parser.add_argument(
        "--benchmark-root",
        type=str,
        default=str(DEFAULT_BENCHMARK_ROOT),
        help="Root directory of the diagnose benchmark dataset.",
    )
    parser.add_argument(
        "--split",
        choices=["dataset_small", "dataset_median", "all"],
        default="dataset_small",
        help="Which benchmark split to run.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional limit on number of cases.",
    )
    parser.add_argument(
        "--report-path",
        type=str,
        default="",
        help="Optional markdown report path. Defaults to artifacts/test_report/diagnose_benchmark/...",
    )
    args = parser.parse_args()

    result = run_diagnose_benchmark(
        benchmark_root=Path(args.benchmark_root),
        split=args.split,
        limit=args.limit,
        report_path=args.report_path or None,
    )
    print(f"Wrote report to: {result['report_path']}")
    print(f"Cases evaluated: {result['cases_evaluated']}")
    print(f"Loose expected-family matches: {result['matched']}/{result['expected_total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
