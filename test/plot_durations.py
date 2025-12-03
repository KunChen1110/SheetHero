#!/usr/bin/env python3
"""
Plot duration metrics for all test cases using logger_metric.json.

For each test case, this script plots a single stacked bar composed of:
  - understanding_time_s (bottom segment)
  - execution_time_s     (middle segment)
  - validation_time_s    (top segment)

X-axis: test case (e.g., 1..27)
Y-axis: duration in seconds (s)

Output:
  test/duration_metrics.png

Usage:
  cd <project-root>
  python3 test/plot_durations.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import matplotlib.pyplot as plt
import numpy as np


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    metrics_path = base_dir / "logger_metric.json"

    if not metrics_path.exists():
        raise FileNotFoundError(f"logger_metric.json not found at {metrics_path}")

    with metrics_path.open("r", encoding="utf-8") as f:
        records: List[Dict[str, Any]] = json.load(f)

    # Ensure records are sorted by test number
    def _sort_key(rec: Dict[str, Any]) -> int:
        task_id = str(rec.get("task_id") or "").strip()
        for part in task_id.split():
            if part.isdigit():
                return int(part)
        return 0

    records = sorted(records, key=_sort_key)

    test_nums: List[int] = []
    understanding_times: List[float] = []
    execution_times: List[float] = []
    validation_times: List[float] = []

    for rec in records:
        task_id = str(rec.get("task_id") or "")
        num = _sort_key(rec)
        test_nums.append(num)

        def _val(key: str) -> float:
            v = rec.get(key)
            try:
                return float(v) if v is not None else 0.0
            except Exception:
                return 0.0

        understanding_times.append(_val("understanding_time_s"))
        execution_times.append(_val("execution_time_s"))
        validation_times.append(_val("validation_time_s"))

    x = np.arange(len(test_nums))
    fig, ax = plt.subplots(figsize=(14, 6))

    # Stacked bar: understanding at bottom, execution in middle, validation on top
    bars_understanding = ax.bar(
        x,
        understanding_times,
        label="Understanding (s)",
        color="#6BAED6",  # medium blue
    )
    bars_execution = ax.bar(
        x,
        execution_times,
        bottom=understanding_times,
        label="Execution (s)",
        color="#FB6A99",  # medium pink
    )
    execution_plus_understanding = [
        u + e for u, e in zip(understanding_times, execution_times)
    ]
    bars_validation = ax.bar(
        x,
        validation_times,
        bottom=execution_plus_understanding,
        label="Validation (s)",
        color="#FDD835",  # medium yellow
    )

    ax.set_xlabel("Test case")
    ax.set_ylabel("Duration (s)")
    ax.set_title("Per-test duration metrics (stacked)")
    ax.set_xticks(x)
    ax.set_xticklabels(test_nums)
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    fig.tight_layout()

    out_path = base_dir / "duration_metrics.png"
    fig.savefig(out_path, dpi=150)
    print(f"Saved duration metrics plot to {out_path}")


if __name__ == "__main__":
    main()
