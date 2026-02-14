#!/usr/bin/env python3
"""CLI test for diagnose geometric row sampling on a dataset testcase."""

from __future__ import annotations

import argparse
import json
import math
import os
import random
from datetime import date, datetime
from pathlib import Path

pd = None


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


def _estimate_cell_budget(token_budget: int, tokens_per_cell: float) -> int:
    if token_budget <= 0:
        return 0
    if tokens_per_cell <= 0:
        tokens_per_cell = 3.0
    return max(int(token_budget / tokens_per_cell), 1)


def _drop_all_empty_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or not hasattr(df, "columns"):
        return df
    drop_cols: list[str] = []
    for col in df.columns:
        series = df[col]
        if series is None:
            drop_cols.append(col)
            continue
        non_empty = False
        for value in series.tolist():
            if value is None:
                continue
            if isinstance(value, float) and pd.isna(value):
                continue
            if pd.isna(value):
                continue
            if str(value).strip() == "":
                continue
            non_empty = True
            break
        if not non_empty:
            drop_cols.append(col)
    if not drop_cols:
        return df
    return df.drop(columns=drop_cols)


def _coerce_workbook_view(workbook_view: dict[str, object]) -> dict[str, pd.DataFrame]:
    if not workbook_view:
        return {}

    view: dict[str, pd.DataFrame] = {}
    for path, payload in workbook_view.items():
        if isinstance(payload, pd.DataFrame):
            file_key = os.path.basename(str(path))
            base_key = f"{file_key}::Sheet1"
            key = base_key
            suffix = 2
            while key in view:
                key = f"{base_key}#{suffix}"
                suffix += 1
            view[key] = payload
            continue

        workbook = payload
        if workbook is None or not hasattr(workbook, "worksheets"):
            continue
        file_key = os.path.basename(str(path))
        for sheet in workbook.worksheets:
            rows = list(sheet.values)
            if not rows:
                df = pd.DataFrame()
            else:
                header = list(rows[0])
                if not any(h is not None and str(h).strip() != "" for h in header):
                    header = [f"col_{i + 1}" for i in range(len(header))]
                else:
                    header = [
                        (str(h).strip() if h is not None and str(h).strip() != "" else f"col_{i + 1}")
                        for i, h in enumerate(header)
                    ]
                data = rows[1:]
                df = pd.DataFrame(data, columns=header)

            base_key = f"{file_key}::{sheet.title}"
            key = base_key
            suffix = 2
            while key in view:
                key = f"{base_key}#{suffix}"
                suffix += 1
            view[key] = df
    return view


def _load_tabular_inputs(input_paths: list[str], openpyxl_module) -> dict[str, object]:
    loaded: dict[str, object] = {}
    for path in input_paths:
        ext = Path(path).suffix.lower()
        if ext == ".csv":
            loaded[path] = pd.read_csv(path)
            continue
        loaded[path] = openpyxl_module.load_workbook(path, data_only=True)
    return loaded


def _build_value_mask(row: list[object]) -> list[int]:
    return [_value_type(value) for value in row]


def _value_type(value: object) -> int:
    if value is None:
        return 0
    if isinstance(value, float) and pd.isna(value):
        return 0
    if pd.isna(value):
        return 0
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return 4
    if isinstance(value, int) and not isinstance(value, bool):
        return 1
    if isinstance(value, float):
        return 2
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return 0
        if text.startswith("="):
            return 5
        try:
            pd.to_datetime(text)
            return 4
        except Exception:
            return 3
    return 3


def _mask_similarity(mask: list[int], ref_mask: list[int]) -> float:
    if not ref_mask:
        return 0.0
    pairs = list(zip(mask, ref_mask))
    denom = sum(1 for v, r in pairs if v != 0 or r != 0)
    if denom == 0:
        return 1.0
    matches = sum(1 for v, r in pairs if v == r and (v != 0 or r != 0))
    return matches / denom


def _geometric_scan_indices(
    df: pd.DataFrame,
    budget_cells: int,
    tau: float = 0.7,
    p_at_dist1: float = 0.8,
    lambda_decay: float = 5.0,
    debug_hook=None,
) -> list[int]:
    total_rows = len(df)
    if total_rows <= 0:
        return []

    total_cells = max(int(df.shape[0]) * max(int(df.shape[1]), 1), 1)
    budget_factor = min(max(budget_cells / total_cells, 0.0), 1.0)

    selected: list[int] = []
    ref_mask: list[int] | None = None
    last_change_idx = 0

    debug = os.getenv("DIAGNOSE_GEOM_DEBUG") == "1"

    def _emit(msg: str) -> None:
        if not debug:
            return
        if debug_hook:
            debug_hook(msg)

    for pos, (_, row) in enumerate(df.iterrows()):
        mask = _build_value_mask(row.tolist())
        if ref_mask is None:
            selected.append(pos)
            ref_mask = mask
            last_change_idx = pos
            _emit(f"[GEOM] select row {pos + 1}: first row")
            continue

        sim = _mask_similarity(mask, ref_mask)
        if sim < tau:
            selected.append(pos)
            ref_mask = mask
            last_change_idx = pos
            _emit(f"[GEOM] select row {pos + 1}: structural change (sim={sim:.2f} < tau={tau})")
            continue

        dist = max(pos - last_change_idx, 0)
        base = p_at_dist1 * math.exp(-(max(dist, 1) - 1) / max(lambda_decay, 1e-6))
        p = base * budget_factor
        if random.random() < max(min(p, 1.0), 0.0):
            selected.append(pos)
            _emit(f"[GEOM] select row {pos + 1}: probabilistic (p={p:.3f}, sim={sim:.2f}, dist={dist})")

    return sorted(set(selected))


def main() -> int:
    global pd
    try:
        import pandas as _pd
    except ModuleNotFoundError as exc:
        raise RuntimeError("pandas is required. Install dependencies first (e.g. `pip install -r requirements.txt`).") from exc
    pd = _pd

    try:
        import openpyxl
    except ModuleNotFoundError as exc:
        raise RuntimeError("openpyxl is required. Install dependencies first (e.g. `pip install -r requirements.txt`).") from exc

    parser = argparse.ArgumentParser(
        description="Print geometric sampling rows for a dataset testcase."
    )
    parser.add_argument(
        "--test-id",
        type=int,
        required=True,
        help="Dataset entry index (1-based).",
    )
    parser.add_argument(
        "--dataset-dir",
        type=str,
        default=str(_repo_root() / "dataset"),
        help="Path to dataset directory (default: ./dataset).",
    )
    parser.add_argument(
        "--token-budget",
        type=int,
        default=5000,
        help="Token budget used to derive sampling budget (default: 5000).",
    )
    parser.add_argument(
        "--tokens-per-cell",
        type=float,
        default=3.0,
        help="Token estimate per cell (default: 3.0).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for probabilistic sampling (default: 42).",
    )
    args = parser.parse_args()

    os.environ.setdefault("DIAGNOSE_GEOM_DEBUG", "1")
    random.seed(args.seed)

    repo_root = _repo_root()

    dataset_dir = Path(args.dataset_dir)
    tasks = _load_tasks(dataset_dir)
    task = _select_task(tasks, args.test_id)
    spreadsheets = task.get("spreadsheets", [])
    if not spreadsheets:
        raise ValueError("Selected task has no input spreadsheets.")

    input_paths = _build_input_paths(dataset_dir, spreadsheets)

    workbook_view = _load_tabular_inputs(input_paths, openpyxl)
    df_view = _coerce_workbook_view(workbook_view)
    budget_cells = _estimate_cell_budget(args.token_budget, args.tokens_per_cell)

    print(f"Task: {task.get('task_id', 'Unknown')} - {task.get('title', '')}".strip())
    print(f"Prompt: {task.get('prompt', '').strip()}")
    print(f"DIAGNOSE_GEOM_DEBUG={os.getenv('DIAGNOSE_GEOM_DEBUG')}")
    print(f"seed={args.seed}, token_budget={args.token_budget}, budget_cells={budget_cells}")
    print("")

    for sheet_key, raw_df in df_view.items():
        df = _drop_all_empty_columns(raw_df)
        debug_lines: list[str] = []
        sampled_indices = _geometric_scan_indices(
            df=df,
            budget_cells=budget_cells,
            debug_hook=debug_lines.append,
        )

        print(f"=== {sheet_key} ===")
        if debug_lines:
            print("[debug]")
            for line in debug_lines:
                print(line)

        if not sampled_indices:
            print("sampled rows: []")
            print("")
            continue

        sampled_rows_1_based = [idx + 2 for idx in sampled_indices]
        print(f"sampled rows (excel row no): {sampled_rows_1_based}")
        print("[sampled values]")
        for idx in sampled_indices:
            row_values = [str(v) if v is not None else "" for v in df.iloc[idx].tolist()]
            print(f"row {idx + 2}: {row_values}")
        print("")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
