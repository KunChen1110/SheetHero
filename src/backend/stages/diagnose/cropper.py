"""Token-aware sampling for diagnose stage."""

from __future__ import annotations

from typing import Dict, List, Tuple

import pandas as pd
import os
import math
import random
import re
from datetime import date, datetime

from ...log.logger_registry import LoggerRegistry

logger = LoggerRegistry.setup_logger(__name__)


def sample_workbook_view(workbook_view: Dict[str, pd.DataFrame],
                         token_budget: int = 3000,
                         top_k: int = 5,
                         mid_k: int = 3,
                         bottom_k: int = 3,
                         anomaly_k: int = 4,
                         tokens_per_cell: float = 3.0,
                         max_rows_per_sheet: int = 20,
                         debug_hook=None
                         ) -> Dict[str, Tuple[List[str], List[List[str]]]]:
    """
    Return sampled rows per sheet as {sheet_key: (columns, rows)}.
    Sampling is token-aware and preserves schema + representative values.
    """
    if not isinstance(workbook_view, dict):
        return {}

    workbook_view = _coerce_workbook_view(workbook_view)
    if not workbook_view:
        return {}

    budget_cells = _estimate_cell_budget(token_budget, tokens_per_cell)
    sheets = _collect_sheet_stats(workbook_view)
    output: Dict[str, Tuple[List[str], List[List[str]]]] = {}
    sampled_sources: Dict[str, pd.DataFrame] = {
        item["sheet"]: item["df"] for item in sheets
    }

    sampled = _sample_rows_geometric(sampled_sources, budget_cells, debug_hook=debug_hook)
    capped = _cap_samples(sampled, budget_cells)
    output.update(capped)

    return output


def _materialize_all_rows(workbook_view: Dict[str, pd.DataFrame],
                          max_rows_per_sheet: int | None = None
                          ) -> Dict[str, Tuple[List[str], List[List[str]]]]:
    output: Dict[str, Tuple[List[str], List[List[str]]]] = {}
    for sheet_key, df in workbook_view.items():
        if df is None or not hasattr(df, "columns"):
            continue
        df = _drop_all_empty_columns(df)
        columns = [str(col) for col in df.columns]
        rows: List[List[str]] = []
        for _, row in df.iterrows():
            values = [_cell_to_text(value) for value in row.tolist()]
            if _is_empty_row(values):
                continue
            rows.append(values)
            if max_rows_per_sheet is not None and max_rows_per_sheet > 0:
                if len(rows) >= max_rows_per_sheet:
                    break
        output[sheet_key] = (columns, rows)
    return output


def _sample_rows_geometric(workbook_view: Dict[str, pd.DataFrame],
                           budget_cells: int,
                           debug_hook=None) -> Dict[str, Tuple[List[str], List[List[str]]]]:
    output: Dict[str, Tuple[List[str], List[List[str]]]] = {}
    for sheet_key, df in workbook_view.items():
        if df is None or not hasattr(df, "columns"):
            continue
        df = _drop_all_empty_columns(df)
        if df.empty:
            output[sheet_key] = ([str(col) for col in df.columns], [])
            continue
        columns = [str(col) for col in df.columns]
        row_indices = _geometric_scan_indices(df, budget_cells, debug_hook=debug_hook)
        rows = []
        for idx in row_indices:
            row = df.iloc[idx].tolist()
            values = [_cell_to_text(value) for value in row]
            if _is_empty_row(values):
                continue
            rows.append(values)
        output[sheet_key] = (columns, rows)
    return output


def _geometric_scan_indices(df: pd.DataFrame,
                            budget_cells: int,
                            tau: float = 0.7,
                            p_at_dist1: float = 0.8,
                            lambda_decay: float = 3.0,
                            debug_hook=None) -> List[int]:
    total_rows = len(df)
    if total_rows <= 0:
        return []

    total_cells = max(int(df.shape[0]) * max(int(df.shape[1]), 1), 1)
    budget_factor = min(max(budget_cells / total_cells, 0.0), 1.0)

    selected: List[int] = []
    ref_mask: List[int] | None = None
    last_change_idx = 0

    debug = os.getenv("DIAGNOSE_GEOM_DEBUG") == "1"
    def _emit(msg: str) -> None:
        if not debug:
            return
        if debug_hook:
            debug_hook(msg)
        else:
            logger.info(msg)
    for idx, row in df.iterrows():
        mask = _build_value_mask(row.tolist())
        if ref_mask is None:
            selected.append(idx)
            ref_mask = mask
            last_change_idx = idx
            _emit(f"[GEOM] select row {idx + 1}: first row")
            continue

        sim = _mask_similarity(mask, ref_mask)
        if sim < tau:
            selected.append(idx)
            ref_mask = mask
            last_change_idx = idx
            _emit(f"[GEOM] select row {idx + 1}: structural change (sim={sim:.2f} < tau={tau})")
            continue

        dist = max(idx - last_change_idx, 0)
        base = p_at_dist1 * math.exp(-(max(dist, 1) - 1) / max(lambda_decay, 1e-6))
        p = base * budget_factor
        if random.random() < max(min(p, 1.0), 0.0):
            selected.append(idx)
            _emit(f"[GEOM] select row {idx + 1}: probabilistic (p={p:.3f}, sim={sim:.2f}, dist={dist})")

    return sorted(set(selected))


def _build_value_mask(row: List[object]) -> List[int]:
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
    if isinstance(value, (int,)) and not isinstance(value, bool):
        return 1
    if isinstance(value, float):
        return 2
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return 0
        if text.startswith("="):
            return 5
        # simple date detection
        try:
            pd.to_datetime(text)
            return 4
        except Exception:
            return 3
    return 3


def _mask_similarity(mask: List[int], ref_mask: List[int]) -> float:
    if not ref_mask:
        return 0.0
    pairs = list(zip(mask, ref_mask))
    denom = sum(1 for v, r in pairs if v != 0 or r != 0)
    if denom == 0:
        return 1.0
    matches = sum(1 for v, r in pairs if v == r and (v != 0 or r != 0))
    return matches / denom


def _cap_samples(sampled: Dict[str, Tuple[List[str], List[List[str]]]],
                 budget_cells: int) -> Dict[str, Tuple[List[str], List[List[str]]]]:
    if not sampled:
        return sampled
    if budget_cells <= 0:
        return {sheet: (columns, []) for sheet, (columns, _) in sampled.items()}
    sheets = list(sampled.keys())
    per_sheet_cells = max(budget_cells // max(len(sheets), 1), 0)
    capped: Dict[str, Tuple[List[str], List[List[str]]]] = {}
    for sheet_key, (columns, rows) in sampled.items():
        cols_count = max(len(columns), 1)
        max_rows = max(per_sheet_cells // cols_count, 0)
        capped[sheet_key] = (columns, rows[:max_rows])
    return capped


def _cell_to_text(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "| |"
    if pd.isna(value):
        return "| |"
    text = str(value)
    text = text.replace("\n", " ").strip()
    if not text:
        return "| |"
    return text


def _is_empty_row(values: List[str]) -> bool:
    if not values:
        return True
    return all(value == "| |" for value in values)


def _estimate_cell_budget(token_budget: int, tokens_per_cell: float) -> int:
    if token_budget <= 0:
        return 0
    if tokens_per_cell <= 0:
        tokens_per_cell = 3.0
    return max(int(token_budget / tokens_per_cell), 1)


def _collect_sheet_stats(workbook_view: Dict[str, pd.DataFrame]) -> List[dict]:
    sheets: List[dict] = []
    for sheet_key, df in workbook_view.items():
        if df is None or not hasattr(df, "shape"):
            continue
        rows = int(df.shape[0])
        cols = int(df.shape[1])
        cells = rows * cols
        sheets.append({"sheet": sheet_key, "df": df, "cells": cells})
    return sheets


def _coerce_workbook_view(workbook_view: Dict[str, object]) -> Dict[str, pd.DataFrame]:
    if not workbook_view:
        return {}
    if any(isinstance(value, pd.DataFrame) for value in workbook_view.values()):
        return {
            key: value for key, value in workbook_view.items()
            if value is not None and hasattr(value, "columns")
        }

    view: Dict[str, pd.DataFrame] = {}
    for path, workbook in workbook_view.items():
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


def _drop_all_empty_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or not hasattr(df, "columns"):
        return df
    drop_cols: List[str] = []
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
