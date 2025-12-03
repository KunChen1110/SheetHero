#!/usr/bin/env python3
"""
Extract key evaluation metrics from per-test logger files.

Scans all `TaskXX_output/TestXX_logger.md` files under test/ and writes a
summary JSON file `logger_metric.json` containing, for each test:

  - task_id               (e.g., "Test 8")
  - understanding_time_s  (float or null)
  - execution_time_s      (float or null)
  - validation_time_s     (float or null)
  - total_duration_s      (float or null)
  - final_answer          (string or null)

Usage:
    cd <project-root>
    python3 test/logger_metrics.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


def extract_metrics_from_log(path: Path) -> Dict[str, Any]:
    """Extract timing info and final answer from a single logger file."""
    text = path.read_text(encoding="utf-8", errors="ignore")

    # Derive task_id from filename, e.g. "Test8_logger.md" -> "Test 8"
    m_id = re.search(r"Test(\d+)_logger\.md", path.name)
    task_id = f"Test {m_id.group(1)}" if m_id else path.name

    def _extract_first(pattern: str) -> Optional[float]:
        m = re.search(pattern, text)
        if not m:
            return None
        try:
            return float(m.group(1))
        except Exception:
            return None

    understanding_time = _extract_first(r"Understanding completed in ([\d\.]+)s")
    execution_time = _extract_first(r"Execution completed in ([\d\.]+)s")
    validation_time = _extract_first(r"Validation completed in ([\d\.]+)s")
    total_duration = _extract_first(r"Total Duration:\s*([\d\.]+)s")

    # Final Answer may appear multiple times; take the last one.
    final_answers = re.findall(r"Final Answer:\s*(.*)", text)
    final_answer: Optional[str] = final_answers[-1].strip() if final_answers else None

    return {
        "task_id": task_id,
        "understanding_time_s": understanding_time,
        "execution_time_s": execution_time,
        "validation_time_s": validation_time,
        "total_duration_s": total_duration,
        "final_answer": final_answer,
    }


def main() -> None:
    base_dir = Path(__file__).resolve().parent

    metrics: List[Dict[str, Any]] = []
    for logger_path in sorted(base_dir.glob("Task*_output/Test*_logger.md")):
        try:
            metrics.append(extract_metrics_from_log(logger_path))
        except Exception as e:  # pragma: no cover - defensive
            metrics.append(
                {
                    "task_id": None,
                    "understanding_time_s": None,
                    "execution_time_s": None,
                    "validation_time_s": None,
                    "total_duration_s": None,
                    "final_answer": None,
                    "error": f"Failed to parse logger: {e}",
                }
            )

    # Sort by task_id numeric suffix where possible
    def _sort_key(rec: Dict[str, Any]) -> int:
        task_id = str(rec.get("task_id") or "").strip()
        m = re.search(r"(\d+)$", task_id)
        if not m:
            return 0
        try:
            return int(m.group(1))
        except Exception:
            return 0

    metrics_sorted = sorted(metrics, key=_sort_key)

    out_path = base_dir / "logger_metric.json"
    out_path.write_text(
        json.dumps(metrics_sorted, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Wrote {len(metrics_sorted)} records to {out_path}")


if __name__ == "__main__":
    main()
