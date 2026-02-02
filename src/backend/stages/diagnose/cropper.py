"""Token-aware sampling for diagnose stage."""

from __future__ import annotations

from typing import Dict, List, Tuple

import pandas as pd
import os


def sample_workbook_view(workbook_view: Dict[str, pd.DataFrame],
                         token_budget: int = 3000,
                         top_k: int = 5,
                         mid_k: int = 3,
                         bottom_k: int = 3,
                         anomaly_k: int = 4,
                         tokens_per_cell: float = 3.0
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
    total_cells = sum(item["cells"] for item in sheets)

    if total_cells <= budget_cells:
        return _materialize_all_rows(workbook_view)

    remaining = budget_cells
    output: Dict[str, Tuple[List[str], List[List[str]]]] = {}
    sampled_sources: Dict[str, pd.DataFrame] = {}

    for item in sorted(sheets, key=lambda x: x["cells"]):
        sheet_key = item["sheet"]
        df = item["df"]
        cells = item["cells"]
        if cells <= remaining:
            output.update(_materialize_all_rows({sheet_key: df}))
            remaining -= cells
        else:
            sampled_sources[sheet_key] = df

    if sampled_sources:
        sampled = _sample_rows(sampled_sources, top_k, mid_k, bottom_k, anomaly_k)
        capped = _cap_samples(sampled, remaining)
        output.update(capped)

    return output


def _materialize_all_rows(workbook_view: Dict[str, pd.DataFrame]
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
        output[sheet_key] = (columns, rows)
    return output


def _sample_rows(workbook_view: Dict[str, pd.DataFrame],
                 top_k: int,
                 mid_k: int,
                 bottom_k: int,
                 anomaly_k: int) -> Dict[str, Tuple[List[str], List[List[str]]]]:
    output: Dict[str, Tuple[List[str], List[List[str]]]] = {}
    for sheet_key, df in workbook_view.items():
        if df is None or not hasattr(df, "columns"):
            continue
        df = _drop_all_empty_columns(df)
        if df.empty:
            output[sheet_key] = ([str(col) for col in df.columns], [])
            continue
        columns = [str(col) for col in df.columns]
        row_indices = _pick_row_indices(df, top_k, mid_k, bottom_k, anomaly_k)
        rows = []
        for idx in row_indices:
            row = df.iloc[idx].tolist()
            values = [_cell_to_text(value) for value in row]
            if _is_empty_row(values):
                continue
            rows.append(values)
        output[sheet_key] = (columns, rows)
    return output


def _pick_row_indices(df: pd.DataFrame,
                      top_k: int,
                      mid_k: int,
                      bottom_k: int,
                      anomaly_k: int) -> List[int]:
    total_rows = len(df)
    indices: List[int] = []

    for idx in range(min(top_k, total_rows)):
        indices.append(idx)

    if total_rows > 0:
        mid_start = max((total_rows // 2) - (mid_k // 2), 0)
        for idx in range(mid_start, min(mid_start + mid_k, total_rows)):
            indices.append(idx)

    for idx in range(max(total_rows - bottom_k, 0), total_rows):
        indices.append(idx)

    if anomaly_k > 0:
        anomaly_rows = _find_anomaly_rows(df, anomaly_k)
        indices.extend(anomaly_rows)

    deduped = sorted(set(idx for idx in indices if 0 <= idx < total_rows))
    return deduped


def _find_anomaly_rows(df: pd.DataFrame, limit: int) -> List[int]:
    candidates: List[int] = []
    for idx, row in df.iterrows():
        values = ["" if value is None else str(value) for value in row.tolist()]
        if any(value.strip() == "" for value in values):
            candidates.append(idx)
            continue
        if any(len(value) > 40 for value in values):
            candidates.append(idx)
            continue
        if any("," in value or ";" in value or "/" in value for value in values):
            candidates.append(idx)
            continue
    return candidates[:limit]


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
