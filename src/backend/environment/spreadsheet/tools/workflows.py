"""Higher-level spreadsheet workflow helpers."""

from __future__ import annotations

import os
import re
from collections import deque
from typing import Any, Dict, Iterable, List, Sequence

import numpy as np
import pandas as pd

from ..world import SpreadsheetWorld
from .cross_workbook import get_workbook, list_all_workbooks, read_table_multi


_HEADER_XML_ESCAPE_RE = re.compile(r"_x[0-9A-Fa-f]{4}_")
_DEP_SPLIT_RE = re.compile(r"[,\n;]+")


def _normalize_header_name(value: Any) -> str:
    text = str(value or "")
    text = _HEADER_XML_ESCAPE_RE.sub("", text)
    text = re.sub(r"[_\W]+", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def _normalize_cell_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, (float, np.floating)):
        if float(value).is_integer():
            return str(int(value))
        return str(float(value)).strip()
    text = str(value)
    text = _HEADER_XML_ESCAPE_RE.sub("", text)
    text = text.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
    return text.strip()


def _is_year_like(value: Any) -> bool:
    text = _normalize_cell_text(value)
    if not text.isdigit():
        return False
    year = int(text)
    return 1900 <= year <= 2100


def _resolve_column_name(columns: Iterable[Any], requested_name: str) -> str:
    normalized_requested = _normalize_header_name(requested_name)
    for column in columns:
        if _normalize_header_name(column) == normalized_requested:
            return str(column)
    raise ValueError(f"Column `{requested_name}` not found in {list(columns)}")


def _coerce_binary_series(series: pd.Series) -> pd.Series:
    mapping = {
        "yes": 1.0,
        "y": 1.0,
        "true": 1.0,
        "1": 1.0,
        "rain": 1.0,
        "male": 0.0,
        "no": 0.0,
        "n": 0.0,
        "false": 0.0,
        "0": 0.0,
        "not rain": 0.0,
        "female": 1.0,
    }
    normalized = series.map(_normalize_cell_text).str.lower()
    unique_values = {value for value in normalized.tolist() if value}
    if not unique_values:
        return pd.to_numeric(series, errors="coerce")
    if unique_values.issubset(set(mapping.keys())):
        return normalized.map(mapping).astype(float)
    return pd.to_numeric(series, errors="coerce")


def _prepare_numeric_feature_frame(
    df: pd.DataFrame,
    feature_cols: Sequence[str],
    target_col: str | None = None,
) -> tuple[pd.DataFrame, str | None, list[str]]:
    actual_feature_cols = [_resolve_column_name(df.columns, col) for col in feature_cols]
    working = pd.DataFrame(index=df.index)
    for actual_col in actual_feature_cols:
        working[actual_col] = _coerce_binary_series(df[actual_col])

    actual_target_col = None
    if target_col is not None:
        actual_target_col = _resolve_column_name(df.columns, target_col)
        working[actual_target_col] = pd.to_numeric(df[actual_target_col], errors="coerce")

    return working, actual_target_col, actual_feature_cols


def load_all_tables(
    world: SpreadsheetWorld,
    range_ref: str = "A1:Z200",
    require_primary_key: bool = True,
    stop_at_note_row: bool = True,
) -> List[Dict[str, Any]]:
    """Load the first visible table from every workbook into a standard structure."""
    tables: List[Dict[str, Any]] = []
    for file_path in list_all_workbooks(world):
        wb = get_workbook(world, file_path)
        sheet_name = wb.sheetnames[0]
        table = read_table_multi(
            world,
            file_path,
            sheet_name,
            range_ref,
            require_primary_key,
            stop_at_note_row,
        )
        header = table.get("header", [])
        if not header:
            continue
        df = pd.DataFrame(table["rows"], columns=header)
        tables.append(
            {
                "file_path": file_path,
                "file": file_path,
                "file_name": os.path.basename(file_path),
                "sheet_name": table["sheet_name"],
                "sheet": table["sheet_name"],
                "header": list(header),
                "rows": list(table["rows"]),
                "df": df,
            }
        )
    return tables


def _extract_structured_table_from_workbook(
    world: SpreadsheetWorld,
    file_path: str,
    required_headers: Sequence[str],
    range_ref: str = "A1:Z200",
) -> Dict[str, Any]:
    """Find the first row that matches the required headers and return a clean table."""
    wb = get_workbook(world, file_path)
    ws = wb.active
    cell_range = ws[range_ref]
    if hasattr(cell_range, "value"):
        raw_rows = [[cell_range.value]]
    else:
        raw_rows = [[cell.value for cell in row] for row in cell_range]

    normalized_rows = [[_normalize_cell_text(v) for v in row] for row in raw_rows]
    required = {_normalize_header_name(col) for col in required_headers}
    header_index = None
    keep_indices: list[int] = []
    header: list[str] = []

    for idx, row in enumerate(normalized_rows):
        non_empty_indices = [col_idx for col_idx, cell in enumerate(row) if _normalize_cell_text(cell)]
        if not non_empty_indices:
            continue
        candidate_header = [row[col_idx] for col_idx in non_empty_indices]
        normalized_header = {_normalize_header_name(cell) for cell in candidate_header}
        if required.issubset(normalized_header):
            header_index = idx
            keep_indices = non_empty_indices
            header = [str(row[col_idx]).strip() for col_idx in keep_indices]
            break

    if header_index is None:
        raise ValueError(
            f"No structured table matched headers {list(required_headers)} in {os.path.basename(file_path)}."
        )

    data_rows: list[list[Any]] = []
    for raw_row in normalized_rows[header_index + 1:]:
        row = [raw_row[col_idx] if col_idx < len(raw_row) else None for col_idx in keep_indices]
        if all(not _normalize_cell_text(value) for value in row):
            if data_rows:
                break
            continue
        data_rows.append(row)

    df = pd.DataFrame(data_rows, columns=header)
    return {
        "file_path": file_path,
        "file_name": os.path.basename(file_path),
        "sheet_name": ws.title,
        "header": header,
        "rows": data_rows,
        "df": df,
    }


def find_table_by_headers(
    tables: Sequence[Dict[str, Any]],
    required_headers: Sequence[str],
    preferred_headers: Sequence[str] | None = None,
    forbidden_headers: Sequence[str] | None = None,
) -> Dict[str, Any]:
    """Pick one table deterministically from verified headers."""
    required = {_normalize_header_name(col) for col in required_headers}
    preferred = [_normalize_header_name(col) for col in (preferred_headers or [])]
    forbidden = {_normalize_header_name(col) for col in (forbidden_headers or [])}

    candidates: List[tuple[int, int, Dict[str, Any]]] = []
    for table in tables:
        header = table.get("header", [])
        normalized_header = {_normalize_header_name(col) for col in header}
        if not required.issubset(normalized_header):
            continue
        if forbidden.intersection(normalized_header):
            continue
        preferred_score = sum(1 for col in preferred if col in normalized_header)
        candidates.append((preferred_score, len(normalized_header), table))

    if not candidates:
        available = [
            {
                "file_name": table.get("file_name"),
                "sheet_name": table.get("sheet_name"),
                "header": table.get("header", []),
            }
            for table in tables
        ]
        raise ValueError(
            "No table matches the requested headers. "
            f"required={list(required_headers)}, preferred={list(preferred_headers or [])}, "
            f"forbidden={list(forbidden_headers or [])}, available={available}"
        )

    candidates.sort(
        key=lambda item: (
            -item[0],
            -item[1],
            str(item[2].get("file_name", "")),
            str(item[2].get("sheet_name", "")),
        )
    )
    return candidates[0][2]


def infer_common_key(tables: Sequence[Dict[str, Any]]) -> str:
    """Infer a shared join key from table headers."""
    if not tables:
        raise ValueError("No tables available to infer a common key.")

    header_lists = [list(table.get("header", [])) for table in tables]
    if not all(header_lists):
        raise ValueError("All tables must have headers to infer a common key.")

    common_normalized = {_normalize_header_name(col) for col in header_lists[0]}
    for header_list in header_lists[1:]:
        common_normalized &= {_normalize_header_name(col) for col in header_list}

    if not common_normalized:
        raise ValueError("No common header found across the selected tables.")

    actual_lookup: Dict[str, str] = {}
    for col in header_lists[0]:
        normalized = _normalize_header_name(col)
        if normalized in common_normalized:
            actual_lookup[normalized] = str(col)

    preferred = sorted(
        common_normalized,
        key=lambda value: (
            0 if "id" in value or "key" in value else 1,
            0 if value.endswith(" id") or value == "id" else 1,
            value,
        ),
    )
    return actual_lookup[preferred[0]]


def concat_tables_with_same_headers(
    tables: Sequence[Dict[str, Any]],
    sort_by: Sequence[str] | None = None,
    ignore_index: bool = True,
) -> Dict[str, Any]:
    """Vertically combine tables that share the same normalized header set."""
    if not tables:
        raise ValueError("No tables provided for concatenation.")

    first_header = [_normalize_header_name(col) for col in tables[0].get("header", [])]
    if not first_header:
        raise ValueError("Tables must include headers for concatenation.")

    dataframes: list[pd.DataFrame] = []
    sources: list[str] = []
    for index, table in enumerate(tables, start=1):
        header = table.get("header", [])
        normalized_header = [_normalize_header_name(col) for col in header]
        if normalized_header != first_header:
            raise ValueError(
                f"Table {index} does not share the same schema. "
                f"expected={tables[0].get('header', [])}, actual={header}"
            )
        df = table.get("df")
        if not isinstance(df, pd.DataFrame):
            raise ValueError("Each table must include a DataFrame under `df`.")
        dataframes.append(df.copy())
        sources.append(str(table.get("file_name") or table.get("sheet_name") or f"table_{index}"))

    combined_df = pd.concat(dataframes, ignore_index=ignore_index)
    if sort_by:
        actual_sort_cols = [_resolve_column_name(combined_df.columns, col) for col in sort_by]
        combined_df = combined_df.sort_values(by=actual_sort_cols).reset_index(drop=True)

    detail_data = [combined_df.columns.tolist()] + combined_df.fillna("").values.tolist()
    return {
        "output_df": combined_df,
        "detail_data": detail_data,
        "row_count": int(len(combined_df)),
        "column_count": int(len(combined_df.columns)),
        "sources": sources,
    }


def merge_tables_on_key(
    tables: Sequence[Dict[str, Any]],
    key_header: str,
    how: str = "inner",
    dedupe_keep: str = "first",
) -> Dict[str, Any]:
    """Horizontally merge selected tables on a verified key."""
    if not tables:
        raise ValueError("No tables provided for merge.")

    merged_df: pd.DataFrame | None = None
    actual_key_name: str | None = None
    merge_sources: list[str] = []

    for index, table in enumerate(tables, start=1):
        df = table.get("df")
        if not isinstance(df, pd.DataFrame):
            raise ValueError("Each table must include a pandas DataFrame under `df`.")
        key_actual = _resolve_column_name(df.columns, key_header)
        table_df = df.copy()
        table_df[key_actual] = table_df[key_actual].map(_normalize_cell_text)
        table_df = table_df[table_df[key_actual] != ""]
        table_df = table_df.drop_duplicates(subset=[key_actual], keep=dedupe_keep)
        non_key_cols = [col for col in table_df.columns if col != key_actual]
        rename_map = {}
        if merged_df is not None:
            existing_norm = {_normalize_header_name(col) for col in merged_df.columns}
            for col in non_key_cols:
                if _normalize_header_name(col) in existing_norm:
                    rename_map[col] = f"{col}_{index}"
        if rename_map:
            table_df = table_df.rename(columns=rename_map)

        if merged_df is None:
            merged_df = table_df
            actual_key_name = key_actual
        else:
            merged_df = merged_df.merge(table_df, left_on=actual_key_name, right_on=key_actual, how=how)
            if key_actual != actual_key_name and key_actual in merged_df.columns:
                merged_df = merged_df.drop(columns=[key_actual])
        merge_sources.append(str(table.get("file_name") or table.get("sheet_name") or f"table_{index}"))

    if merged_df is None:
        raise ValueError("Merge produced no result.")

    detail_data = [merged_df.columns.tolist()] + merged_df.fillna("").values.tolist()
    return {
        "key_column": actual_key_name,
        "merged_df": merged_df,
        "output_df": merged_df,
        "detail_data": detail_data,
        "row_count": int(len(merged_df)),
        "column_count": int(len(merged_df.columns)),
        "sources": merge_sources,
    }


def fill_missing_from_reference(
    primary_df: pd.DataFrame,
    reference_df: pd.DataFrame,
    key_header: str,
    prefer_primary: bool = True,
) -> Dict[str, Any]:
    """Fill empty cells in a primary table using values from a reference table aligned on a key."""
    primary_key = _resolve_column_name(primary_df.columns, key_header)
    reference_key = _resolve_column_name(reference_df.columns, key_header)

    primary = primary_df.copy()
    reference = reference_df.copy()
    primary[primary_key] = primary[primary_key].map(_normalize_cell_text)
    reference[reference_key] = reference[reference_key].map(_normalize_cell_text)
    reference = reference.drop_duplicates(subset=[reference_key], keep="first").set_index(reference_key)

    shared_non_key_pairs: list[tuple[str, str]] = []
    for primary_col in primary.columns:
        if primary_col == primary_key:
            continue
        for reference_col in reference.columns:
            if reference_col == reference_key:
                continue
            if _normalize_header_name(primary_col) == _normalize_header_name(reference_col):
                shared_non_key_pairs.append((primary_col, reference_col))
                break

    filled_count = 0
    for idx, row in primary.iterrows():
        key_value = _normalize_cell_text(row[primary_key])
        ref_row = None
        if key_value and key_value in reference.index:
            ref_row = reference.loc[key_value]
        elif not key_value and shared_non_key_pairs:
            candidate_mask = pd.Series(True, index=reference.index)
            matched_on_shared = False
            for primary_col, reference_col in shared_non_key_pairs:
                primary_value = _normalize_cell_text(row[primary_col])
                if not primary_value:
                    continue
                matched_on_shared = True
                candidate_mask &= reference[reference_col].map(_normalize_cell_text) == primary_value
            candidate_keys = reference.index[candidate_mask].tolist() if matched_on_shared else []
            if len(candidate_keys) == 1:
                key_value = _normalize_cell_text(candidate_keys[0])
                primary.at[idx, primary_key] = key_value
                ref_row = reference.loc[key_value]
                filled_count += 1

        if ref_row is None:
            continue
        for column in primary.columns:
            if column == primary_key:
                continue
            ref_column = None
            for candidate in reference.columns:
                if _normalize_header_name(candidate) == _normalize_header_name(column):
                    ref_column = candidate
                    break
            if ref_column is None:
                continue

            primary_value = row[column]
            primary_missing = pd.isna(primary_value) or _normalize_cell_text(primary_value) == ""
            if prefer_primary and not primary_missing:
                continue

            ref_value = ref_row[ref_column]
            if pd.isna(ref_value) or _normalize_cell_text(ref_value) == "":
                continue
            if primary_missing or not prefer_primary:
                primary.at[idx, column] = ref_value
                filled_count += 1

    detail_data = [primary.columns.tolist()] + primary.fillna("").values.tolist()
    return {
        "key_column": primary_key,
        "output_df": primary,
        "detail_data": detail_data,
        "filled_count": int(filled_count),
        "row_count": int(len(primary)),
        "column_count": int(len(primary.columns)),
    }


def build_missing_data_report(
    world: SpreadsheetWorld,
    range_ref: str = "A1:Z200",
) -> Dict[str, Any]:
    """Scan loaded workbooks for missing cells and return a natural-language report."""
    findings: list[dict[str, Any]] = []
    for file_path in list_all_workbooks(world):
        wb = get_workbook(world, file_path)
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            last_row = 0
            last_col = 0
            for row_idx in range(1, ws.max_row + 1):
                for col_idx in range(1, ws.max_column + 1):
                    if _normalize_cell_text(ws.cell(row=row_idx, column=col_idx).value):
                        last_row = max(last_row, row_idx)
                        last_col = max(last_col, col_idx)
            if last_row == 0 or last_col == 0:
                continue

            header = [
                _normalize_cell_text(ws.cell(row=1, column=col_idx).value)
                for col_idx in range(1, last_col + 1)
            ]
            for row_idx in range(2, last_row + 1):
                row_values = [
                    ws.cell(row=row_idx, column=col_idx).value
                    for col_idx in range(1, last_col + 1)
                ]
                if not any(_normalize_cell_text(value) for value in row_values):
                    continue
                for col_idx, value in enumerate(row_values, start=1):
                    if _normalize_cell_text(value):
                        continue
                    findings.append(
                        {
                            "file_name": os.path.basename(file_path),
                            "sheet_name": sheet_name,
                            "row": row_idx,
                            "col": col_idx,
                            "header": header[col_idx - 1] if col_idx - 1 < len(header) else "",
                        }
                    )

    if not findings:
        answer = "No missing data found."
    elif len(findings) == 1:
        item = findings[0]
        answer = (
            f"Missing data on line {item['row']} col {item['col']}"
            + (f" ({item['header']})" if item["header"] else "")
            + "."
        )
    else:
        parts = []
        for item in findings[:6]:
            label = f"line {item['row']} col {item['col']}"
            if item["header"]:
                label += f" ({item['header']})"
            parts.append(label)
        answer = "Missing data found at " + "; ".join(parts) + "."

    return {
        "issues": findings,
        "answer": answer,
        "count": len(findings),
    }


def build_room_format_report(
    world: SpreadsheetWorld,
    range_ref: str = "A1:Z200",
) -> Dict[str, Any]:
    """Describe room-identifier format inconsistencies in natural language."""
    tables = load_all_tables(
        world,
        range_ref=range_ref,
        require_primary_key=False,
        stop_at_note_row=True,
    )
    room_table = find_table_by_headers(
        tables,
        required_headers=["Room"],
    )
    df = room_table["df"].copy()
    room_col = _resolve_column_name(df.columns, "Room")
    raw_values = [_normalize_cell_text(v) for v in df[room_col].tolist()]
    raw_values = [value for value in raw_values if value]

    if not raw_values:
        return {
            "answer": "No room identifiers found in the spreadsheet.",
            "variants": {},
        }

    variant_map: dict[str, set[str]] = {}
    for value in raw_values:
        canonical = re.sub(r"\s+", "", value).upper()
        variant_map.setdefault(canonical, set()).add(value)

    duplicate_variant_groups = {
        canonical: sorted(variants)
        for canonical, variants in variant_map.items()
        if len(variants) > 1
    }
    if duplicate_variant_groups:
        canonical, variants = sorted(
            duplicate_variant_groups.items(),
            key=lambda item: (-len(item[1]), item[0]),
        )[0]
        sample = ", ".join(f"`{variant}`" for variant in variants[:3])
        answer = (
            f"The `Room` column contains inconsistent variants for the same room code {canonical}: {sample}. "
            f"Should Room be standardized as `{canonical}`, `{canonical[0]} {canonical[1:]}`, or lowercase `{canonical.lower()}`?"
        )
        return {
            "answer": answer,
            "variants": duplicate_variant_groups,
        }

    has_spaced = any(" " in value for value in raw_values)
    has_lower = any(any(ch.islower() for ch in value) for value in raw_values)
    has_upper = any(any(ch.isupper() for ch in value) for value in raw_values)
    code_like_values = [value for value in raw_values if re.search(r"[A-Za-z]\s*\d", value)]

    if (has_spaced and (has_lower or has_upper)) or (has_lower and has_upper and code_like_values):
        sample = ", ".join(f"`{value}`" for value in code_like_values[:3])
        answer = (
            f"The `Room` column uses inconsistent formatting for room identifiers, for example {sample}. "
            "Should Room be standardized as `C 80`, `C80`, or `c80`?"
        )
        return {
            "answer": answer,
            "variants": {re.sub(r'\\s+', '', value).upper(): [value] for value in code_like_values[:3]},
        }

    return {
        "answer": "No obvious room identifier inconsistencies were found.",
        "variants": {},
    }


def summarize_numeric_column(
    df: pd.DataFrame,
    value_col: str,
    round_digits: int = 2,
    summary_labels: Dict[str, str] | None = None,
) -> Dict[str, Any]:
    """Summarize a numeric column and compute Output row numbers for max-value highlights."""
    actual_value_col = _resolve_column_name(df.columns, value_col)
    numeric_series = pd.to_numeric(df[actual_value_col], errors="coerce")
    if numeric_series.dropna().empty:
        raise ValueError(f"Column `{actual_value_col}` has no numeric values.")

    total_value = round(float(numeric_series.sum()), round_digits)
    average_value = round(float(numeric_series.mean()), round_digits)
    max_raw = float(numeric_series.max())
    max_value = round(max_raw, round_digits)
    max_indices = numeric_series[numeric_series == max_raw].index.tolist()
    output_row_numbers = [int(idx) + 2 for idx in max_indices]

    labels = {
        "total": f"Total {actual_value_col}",
        "average": f"Average {actual_value_col}",
        "max": f"Max {actual_value_col}",
    }
    if summary_labels:
        labels.update(summary_labels)

    summary = {
        labels["total"]: total_value,
        labels["average"]: average_value,
        labels["max"]: max_value,
    }
    return {
        "value_col": actual_value_col,
        "total": total_value,
        "average": average_value,
        "max_value": max_value,
        "max_indices": max_indices,
        "output_row_numbers": output_row_numbers,
        "summary": summary,
    }


def build_region_growth_analysis(
    world: SpreadsheetWorld,
    file_path: str,
    sheet_name: str = "Data",
    start_year: int = 2020,
    end_year: int = 2024,
) -> Dict[str, Any]:
    """Parse a year-by-region sheet with a messy multi-row header and compute growth analysis."""
    wb = get_workbook(world, file_path)
    if sheet_name not in wb.sheetnames:
        raise ValueError(f"Sheet `{sheet_name}` not found in {os.path.basename(file_path)}.")
    ws = wb[sheet_name]

    raw_rows: list[list[Any]] = []
    max_col = min(ws.max_column, 20)
    max_row = min(ws.max_row, 300)
    for row_idx in range(1, max_row + 1):
        raw_rows.append([ws.cell(row=row_idx, column=col_idx).value for col_idx in range(1, max_col + 1)])

    first_year_row_idx = None
    year_col_idx = None
    for row_idx, row in enumerate(raw_rows):
        non_empty = [(col_idx, value) for col_idx, value in enumerate(row) if _normalize_cell_text(value)]
        if not non_empty:
            continue
        first_non_empty_idx, first_non_empty_value = non_empty[0]
        if _is_year_like(first_non_empty_value):
            first_year_row_idx = row_idx
            year_col_idx = first_non_empty_idx
            break

    if first_year_row_idx is None or year_col_idx is None or first_year_row_idx == 0:
        raise ValueError("Could not identify the first year row and the preceding region header row.")

    header_row = raw_rows[first_year_row_idx - 1]
    region_columns: list[tuple[int, str]] = []
    for col_idx in range(year_col_idx + 1, len(header_row)):
        label = _normalize_cell_text(header_row[col_idx])
        if not label:
            if region_columns:
                break
            continue
        lower_label = label.lower()
        if lower_label.startswith("in %") or lower_label == "in %":
            break
        region_columns.append((col_idx, label))

    if not region_columns:
        raise ValueError("No region columns found in the row above the first year row.")

    records: list[dict[str, Any]] = []
    for row in raw_rows[first_year_row_idx:]:
        if year_col_idx >= len(row) or not _is_year_like(row[year_col_idx]):
            if records:
                break
            continue
        year = int(_normalize_cell_text(row[year_col_idx]))
        record: dict[str, Any] = {"Year": year}
        for col_idx, region_name in region_columns:
            value = row[col_idx] if col_idx < len(row) else None
            record[region_name] = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
        records.append(record)

    if not records:
        raise ValueError("No yearly records were parsed from the region table.")

    wide_df = pd.DataFrame(records)
    chart_df = wide_df[(wide_df["Year"] >= start_year) & (wide_df["Year"] <= end_year)].reset_index(drop=True)
    if chart_df.empty:
        raise ValueError(f"No rows found for years {start_year}-{end_year}.")

    result_rows: list[dict[str, Any]] = []
    avg_col = f"Avg Penetration ({start_year}-{end_year})"
    growth_col = f"Growth ({start_year}-{end_year})"
    for _, region_name in region_columns:
        series = pd.to_numeric(chart_df[region_name], errors="coerce")
        if series.dropna().empty:
            continue
        result_rows.append(
            {
                "Region": region_name,
                avg_col: round(float(series.mean()), 2),
                growth_col: round(float(series.iloc[-1] - series.iloc[0]), 2),
            }
        )

    if not result_rows:
        raise ValueError("No region summary rows were computed.")

    output_df = pd.DataFrame(result_rows).sort_values(by=growth_col, ascending=False, kind="stable").reset_index(drop=True)
    max_growth = float(output_df.iloc[0][growth_col])
    fastest_regions = output_df.loc[output_df[growth_col] == max_growth, "Region"].tolist()
    fastest_growth_rows = [
        idx + 2
        for idx, value in enumerate(output_df[growth_col].tolist())
        if float(value) == max_growth
    ]

    return {
        "wide_df": wide_df,
        "chart_df": chart_df,
        "region_columns": [name for _, name in region_columns],
        "output_df": output_df,
        "detail_data": [output_df.columns.tolist()] + output_df.fillna("").values.tolist(),
        "summary": {
            "Fastest Growth Region": ", ".join(fastest_regions),
            growth_col: max_growth,
        },
        "fastest_growth_rows": fastest_growth_rows,
        "start_year": start_year,
        "end_year": end_year,
    }


def build_group_summary(
    df: pd.DataFrame,
    group_cols: Sequence[str],
    aggregations: Dict[str, tuple[str, str]],
    dropna_subset: Sequence[str] | None = None,
    sort_by: Sequence[str] | None = None,
    ascending: bool | Sequence[bool] = True,
    round_digits: int | None = None,
) -> Dict[str, Any]:
    """Create a grouped summary table from explicit aggregation specs."""
    if not group_cols:
        raise ValueError("group_cols must not be empty.")
    if not aggregations:
        raise ValueError("aggregations must not be empty.")

    actual_group_cols = [_resolve_column_name(df.columns, col) for col in group_cols]
    dropna_actual = [_resolve_column_name(df.columns, col) for col in (dropna_subset or [])]
    working = df.copy()
    if dropna_actual:
        working = working.dropna(subset=dropna_actual)

    named_aggs: Dict[str, tuple[str, str]] = {}
    for output_name, (source_col, agg_name) in aggregations.items():
        named_aggs[output_name] = (_resolve_column_name(df.columns, source_col), agg_name)

    grouped = (
        working.groupby(actual_group_cols, dropna=False)
        .agg(**named_aggs)
        .reset_index()
    )
    if round_digits is not None:
        numeric_cols = grouped.select_dtypes(include=["number"]).columns.tolist()
        if numeric_cols:
            grouped[numeric_cols] = grouped[numeric_cols].round(round_digits)
    if sort_by:
        actual_sort_cols = [col if col in grouped.columns else _resolve_column_name(grouped.columns, col) for col in sort_by]
        grouped = grouped.sort_values(by=actual_sort_cols, ascending=ascending).reset_index(drop=True)

    detail_data = [grouped.columns.tolist()] + grouped.fillna("").values.tolist()
    return {
        "grouped_df": grouped,
        "output_df": grouped,
        "detail_data": detail_data,
        "row_count": int(len(grouped)),
        "column_count": int(len(grouped.columns)),
    }


def _parse_numeric_text(value: Any) -> float:
    text = _normalize_cell_text(value)
    if not text:
        return float("nan")
    cleaned = text.replace(",", "").replace("$", "").replace("%", "").strip()
    if cleaned == "":
        return float("nan")
    return float(cleaned)


def _format_dashboard_metric(metric_name: str, value: float) -> str:
    lower = metric_name.lower()
    if "margin" in lower:
        return f"{value:.1f}%"
    if "cac" in lower:
        return f"${value:,.2f}"
    if "ratio" in lower:
        return f"{value:.2f}"
    return f"${value:,.0f}"


def _format_dashboard_variance(metric_name: str, variance: float) -> str:
    lower = metric_name.lower()
    if "margin" in lower:
        return f"{variance:+.1f}%"
    if "cac" in lower:
        sign = "+" if variance >= 0 else "-"
        return f"{sign}${abs(variance):,.2f}"
    if "ratio" in lower:
        return f"{variance:+.2f}"
    sign = "+" if variance >= 0 else "-"
    return f"{sign}${abs(variance):,.0f}"


def _dashboard_assessment(metric_name: str, actual: float, target: float) -> str:
    lower = metric_name.lower()
    lower_is_better = "cac" in lower
    favorable = actual <= target if lower_is_better else actual >= target
    if not favorable:
        return "Below Target"
    if target == 0:
        return "On Target"
    relative_gap = abs((target - actual) / target) if lower_is_better else abs((actual - target) / target)
    if "gross profit" in lower and "margin" not in lower:
        return "On Target" if relative_gap < 0.02 else "Exceeding Target"
    if "margin" in lower:
        return "On Target" if relative_gap < 0.05 else "Exceeding Target"
    if "cac" in lower:
        return "On Target" if relative_gap < 0.03 else "Exceeding Target"
    if "ratio" in lower:
        return "On Target" if relative_gap < 0.05 else "Exceeding Target"
    return "On Target" if relative_gap < 0.05 else "Exceeding Target"


def build_market_share_shipment_report(
    world: SpreadsheetWorld,
    range_ref: str = "A1:Z300",
) -> Dict[str, Any]:
    """Align quarterly market share with quarterly shipments and estimate unit shipments per brand."""
    workbook_paths = list_all_workbooks(world)
    market_share_df = None
    shipment_df = None

    quarter_pattern = re.compile(r"^Q[1-4]\s+\d{4}$", flags=re.IGNORECASE)

    for file_path in workbook_paths:
        wb = get_workbook(world, file_path)
        if "Data" not in wb.sheetnames:
            continue
        ws = wb["Data"]
        raw_rows = [
            [ws.cell(row=row_idx, column=col_idx).value for col_idx in range(1, min(ws.max_column, 20) + 1)]
            for row_idx in range(1, min(ws.max_row, 400) + 1)
        ]
        norm_rows = [[_normalize_cell_text(v) for v in row] for row in raw_rows]

        if market_share_df is None:
            header_idx = None
            for idx, row in enumerate(norm_rows):
                normalized_header = [_normalize_header_name(value) for value in row if _normalize_cell_text(value)]
                if {"vivo", "samsung", "xiaomi"}.issubset(set(normalized_header)):
                    header_idx = idx
                    break
            if header_idx is not None:
                header_row = norm_rows[header_idx]
                quarter_col_idx = next(
                    (idx for idx, value in enumerate(norm_rows[header_idx + 1]) if quarter_pattern.match(value)),
                    None,
                )
                if quarter_col_idx is None:
                    quarter_col_idx = 1
                brand_columns: list[tuple[int, str]] = []
                for col_idx in range(quarter_col_idx + 1, len(header_row)):
                    label = header_row[col_idx]
                    if not label or label.lower().startswith("in %"):
                        break
                    brand_columns.append((col_idx, label))
                records: list[dict[str, Any]] = []
                for row in norm_rows[header_idx + 1:]:
                    if quarter_col_idx >= len(row) or not quarter_pattern.match(row[quarter_col_idx]):
                        if records:
                            break
                        continue
                    record = {"Time": row[quarter_col_idx]}
                    for col_idx, label in brand_columns:
                        value = row[col_idx] if col_idx < len(row) else ""
                        numeric = pd.to_numeric(pd.Series([value.replace("%", "")]), errors="coerce").iloc[0]
                        record[label] = 0.0 if pd.isna(numeric) else float(numeric)
                    records.append(record)
                if records:
                    market_share_df = pd.DataFrame(records)

        if shipment_df is None:
            start_idx = None
            for idx, row in enumerate(norm_rows):
                non_empty_count = sum(1 for cell in row if cell)
                if len(row) >= 3 and quarter_pattern.match(row[1]) and row[2] and non_empty_count <= 3:
                    start_idx = idx
                    break
            if start_idx is not None:
                records: list[dict[str, Any]] = []
                for row in norm_rows[start_idx:]:
                    if len(row) < 3 or not quarter_pattern.match(row[1]):
                        if records:
                            break
                        continue
                    shipment_value = pd.to_numeric(pd.Series([row[2]]), errors="coerce").iloc[0]
                    if pd.isna(shipment_value):
                        continue
                    records.append({"Time": row[1], "Shipment": float(shipment_value)})
                if records:
                    shipment_df = pd.DataFrame(records)

    if market_share_df is None or shipment_df is None:
        raise ValueError("Could not identify both market-share and shipment tables from the loaded workbooks.")

    overlap_df = market_share_df.merge(shipment_df, on="Time", how="inner")
    if overlap_df.empty:
        raise ValueError("No overlapping quarter period was found between market share and shipment tables.")

    brand_columns = [col for col in market_share_df.columns if col != "Time"]
    output_df = pd.DataFrame({"Year": overlap_df["Time"]})
    for brand in brand_columns:
        output_df[f"{brand} (Unit shipment)"] = (
            pd.to_numeric(overlap_df[brand], errors="coerce").fillna(0).astype(float)
            * pd.to_numeric(overlap_df["Shipment"], errors="coerce").fillna(0).astype(float)
            / 100.0
        ).round(2)

    detail_data = [output_df.columns.tolist()] + output_df.fillna("").values.tolist()
    return {
        "output_df": output_df,
        "detail_data": detail_data,
        "row_count": int(len(output_df)),
        "column_count": int(len(output_df.columns)),
        "overlap_period": output_df["Year"].tolist(),
    }


def build_cash_flow_efficiency_report(
    world: SpreadsheetWorld,
    file_path: str | None = None,
) -> Dict[str, Any]:
    """Compute Coca-Cola OCF/Net Income and Free Cash Flow by year."""
    workbook_paths = list_all_workbooks(world)
    target_path = file_path or (workbook_paths[0] if workbook_paths else None)
    if not target_path:
        raise ValueError("No workbook available for cash-flow analysis.")

    wb = get_workbook(world, target_path)
    ws = wb.active
    raw_rows = [
        [_normalize_cell_text(ws.cell(row=row_idx, column=col_idx).value) for col_idx in range(1, min(ws.max_column, 20) + 1)]
        for row_idx in range(1, min(ws.max_row, 180) + 1)
    ]

    header_idx = None
    years: list[str] = []
    for idx, row in enumerate(raw_rows):
        if len(row) >= 12 and row[1].lower() == "in million usd" and row[2].startswith("FY"):
            header_idx = idx
            years = [row[col_idx].replace("FY '", "20").replace("FY '0", "20").replace("FY '", "") for col_idx in range(2, 12)]
            years = [f"20{value[-2:]}" if len(value) >= 2 and value[-2:].isdigit() else value for value in years]
            break
    if header_idx is None:
        raise ValueError("Could not locate year header row for cash-flow analysis.")

    row_lookup: dict[str, list[str]] = {}
    for row in raw_rows[header_idx + 1:]:
        if len(row) < 12:
            continue
        label = row[1]
        if not label:
            continue
        row_lookup[_normalize_header_name(label)] = row

    ocf_row = row_lookup.get(_normalize_header_name("Net cash provided by operating activities"))
    net_income_row = row_lookup.get(_normalize_header_name("CONSOLIDATED NET INCOME"))
    capex_row = row_lookup.get(_normalize_header_name("Purchases of property, plant and equipment"))
    if ocf_row is None or net_income_row is None or capex_row is None:
        raise ValueError("Could not locate required OCF, net income, or capex rows.")

    records: list[dict[str, Any]] = []
    for offset, year in enumerate(years, start=2):
        ocf = float(_parse_numeric_text(ocf_row[offset]))
        net_income = float(_parse_numeric_text(net_income_row[offset]))
        capex = abs(float(_parse_numeric_text(capex_row[offset])))
        ratio = round(ocf / net_income, 2) if net_income else np.nan
        free_cash_flow = round(ocf - capex, 0)
        records.append(
            {
                "Year": year,
                "Operating Cash Flow": ocf,
                "Net Income": net_income,
                "OCF/Net Income": ratio,
                "Capital Expenditures": capex,
                "Free Cash Flow": free_cash_flow,
            }
        )

    output_df = pd.DataFrame(records)

    def _fmt_money(value: float) -> str:
        return f"${int(round(value)):,}"

    formatted_df = output_df.copy()
    for col in ["Operating Cash Flow", "Net Income", "Capital Expenditures", "Free Cash Flow"]:
        formatted_df[col] = formatted_df[col].map(_fmt_money)
    formatted_df["OCF/Net Income"] = output_df["OCF/Net Income"].map(lambda v: f"{float(v):.2f}")

    detail_data: list[list[Any]] = [
        ["Cash Flow Efficiency Analysis", "", "", "", "", ""],
        ["Calculated Metrics for Coca-Cola (2009-2018):", "", "", "", "", ""],
        ["", "", "", "", "", ""],
        formatted_df.columns.tolist(),
    ] + formatted_df.values.tolist()
    return {
        "output_df": output_df,
        "formatted_df": formatted_df,
        "detail_data": detail_data,
        "row_count": int(len(formatted_df)),
        "column_count": int(len(formatted_df.columns)),
    }


def build_diabetes_region_report(
    world: SpreadsheetWorld,
    range_ref: str = "A1:Z200",
) -> Dict[str, Any]:
    """Build a regional diabetes summary from prevalence/expenditure inputs."""
    workbook_paths = list_all_workbooks(world)
    diabetics_df = None
    expenditure_df = None
    for file_path in workbook_paths:
        wb = get_workbook(world, file_path)
        if "Data" not in wb.sheetnames:
            continue
        ws = wb["Data"]
        rows = [
            [_normalize_cell_text(ws.cell(row=row_idx, column=col_idx).value) for col_idx in range(1, 6)]
            for row_idx in range(1, min(ws.max_row, 120) + 1)
        ]
        first_values = [row[1] if len(row) > 1 else "" for row in rows]
        if diabetics_df is None and any("number of diabetics worldwide by region" in value.lower() for value in first_values if value):
            records = []
            for row in rows:
                if len(row) < 3:
                    continue
                region, value = row[1], row[2]
                if not region or region.lower().startswith("number of diabetics worldwide"):
                    continue
                numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
                if pd.isna(numeric):
                    continue
                records.append({"Region": region, "Number of Diabetics (millions)": float(numeric)})
            diabetics_df = pd.DataFrame(records)
        if expenditure_df is None and any("health care expenditure due to diabetes worldwide by region" in value.lower() for value in first_values if value):
            records = []
            for row in rows:
                if len(row) < 3:
                    continue
                region, value = row[1], row[2]
                if not region or region.lower().startswith("health care expenditure due to diabetes worldwide"):
                    continue
                numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
                if pd.isna(numeric):
                    continue
                records.append({"Region": region, "Expenditure (billion USD)": float(numeric)})
            expenditure_df = pd.DataFrame(records)

    if diabetics_df is None or expenditure_df is None:
        raise ValueError("Could not identify both diabetics-by-region and expenditure-by-region tables.")

    output_df = diabetics_df.merge(expenditure_df, on="Region", how="inner")
    total_diabetics = float(output_df["Number of Diabetics (millions)"].sum())
    output_df["Share of Global (%)"] = output_df["Number of Diabetics (millions)"] / total_diabetics * 100.0
    output_df["Avg Expenditure per Person (USD)"] = (
        output_df["Expenditure (billion USD)"] * 1000.0 / output_df["Number of Diabetics (millions)"]
    )
    output_df = output_df[
        [
            "Region",
            "Number of Diabetics (millions)",
            "Expenditure (billion USD)",
            "Share of Global (%)",
            "Avg Expenditure per Person (USD)",
        ]
    ]
    output_df = output_df.sort_values(
        by="Number of Diabetics (millions)", ascending=False, kind="stable"
    ).reset_index(drop=True)
    detail_data = [output_df.columns.tolist(), ["", "", "", "", ""]] + output_df.fillna("").values.tolist()
    return {
        "output_df": output_df,
        "detail_data": detail_data,
        "row_count": int(len(output_df)),
        "column_count": int(len(output_df.columns)),
    }


def build_mobile_reviews_summary_report(
    world: SpreadsheetWorld,
    range_ref: str = "A1:Y50000",
) -> Dict[str, Any]:
    """Group smartphone reviews by country and brand with average rating and count."""
    tables = load_all_tables(
        world,
        range_ref=range_ref,
        require_primary_key=False,
        stop_at_note_row=False,
    )
    review_table = find_table_by_headers(
        tables,
        required_headers=["country", "brand", "rating"],
    )
    df = review_table["df"].copy()
    country_col = _resolve_column_name(df.columns, "country")
    brand_col = _resolve_column_name(df.columns, "brand")
    rating_col = _resolve_column_name(df.columns, "rating")

    df[rating_col] = pd.to_numeric(df[rating_col], errors="coerce")
    working = df.dropna(subset=[country_col, brand_col, rating_col]).copy()
    grouped = (
        working.groupby([country_col, brand_col], dropna=False)
        .agg(
            avg_rating=(rating_col, "mean"),
            num_reviews=(rating_col, "count"),
        )
        .reset_index()
        .sort_values(by=[country_col, brand_col], kind="stable")
        .reset_index(drop=True)
    )
    grouped.columns = ["country", "brand", "avg_rating", "num_reviews"]
    detail_data = [grouped.columns.tolist()] + grouped.fillna("").values.tolist()
    return {
        "output_df": grouped,
        "detail_data": detail_data,
        "row_count": int(len(grouped)),
        "column_count": int(len(grouped.columns)),
    }


def build_store_feature_analysis_report(
    world: SpreadsheetWorld,
    range_ref: str = "A1:Z100000",
) -> Dict[str, Any]:
    """Merge weekly store features with store metadata and build two summary sheets."""
    tables = load_all_tables(
        world,
        range_ref=range_ref,
        require_primary_key=False,
        stop_at_note_row=False,
    )
    features_table = find_table_by_headers(
        tables,
        required_headers=["Store", "Temperature", "Fuel_Price", "CPI", "Unemployment", "IsHoliday"],
        preferred_headers=["MarkDown1", "MarkDown2", "MarkDown3", "MarkDown4", "MarkDown5"],
    )
    stores_table = find_table_by_headers(
        tables,
        required_headers=["Store", "Type", "Size"],
    )

    features_df = features_table["df"].copy()
    stores_df = stores_table["df"].copy()
    store_col = _resolve_column_name(features_df.columns, "Store")
    stores_store_col = _resolve_column_name(stores_df.columns, "Store")
    features_df[store_col] = pd.to_numeric(features_df[store_col], errors="coerce")
    stores_df[stores_store_col] = pd.to_numeric(stores_df[stores_store_col], errors="coerce")

    merged = features_df.merge(
        stores_df,
        left_on=store_col,
        right_on=stores_store_col,
        how="inner",
    )

    type_col = _resolve_column_name(merged.columns, "Type")
    isholiday_col = _resolve_column_name(merged.columns, "IsHoliday")
    store_type_metrics = ["Temperature", "Fuel_Price", "CPI", "Unemployment"]
    for col in store_type_metrics + ["MarkDown1", "MarkDown2", "MarkDown3", "MarkDown4", "MarkDown5", "Size"]:
        actual = _resolve_column_name(merged.columns, col)
        merged[actual] = pd.to_numeric(merged[actual], errors="coerce")

    merged[isholiday_col] = merged[isholiday_col].apply(
        lambda value: bool(value) if isinstance(value, bool) else str(value).strip().lower() in {"true", "1", "yes"}
    )

    avg_by_type = (
        merged.groupby(type_col, dropna=False)[[_resolve_column_name(merged.columns, col) for col in store_type_metrics]]
        .mean()
        .reset_index()
    )
    avg_by_type.columns = ["Type"] + store_type_metrics

    holiday_metrics = [
        "Temperature",
        "Fuel_Price",
        "MarkDown1",
        "MarkDown2",
        "MarkDown3",
        "MarkDown4",
        "MarkDown5",
        "CPI",
        "Unemployment",
        "Size",
    ]
    holiday_rows: list[list[Any]] = [["Feature", "Holiday Average", "Non-Holiday Average", "Difference"]]
    holiday_mask = merged[isholiday_col] == True
    non_holiday_mask = merged[isholiday_col] == False
    for feature in holiday_metrics:
        actual = _resolve_column_name(merged.columns, feature)
        holiday_avg = float(merged.loc[holiday_mask, actual].mean())
        non_holiday_avg = float(merged.loc[non_holiday_mask, actual].mean())
        holiday_rows.append([feature, holiday_avg, non_holiday_avg, holiday_avg - non_holiday_avg])

    avg_by_type_detail_data = [avg_by_type.columns.tolist()] + avg_by_type.fillna("").values.tolist()
    holiday_output_df = pd.DataFrame(holiday_rows[1:], columns=holiday_rows[0])
    return {
        "avg_by_type_df": avg_by_type,
        "holiday_df": holiday_output_df,
        "avg_by_type_detail_data": avg_by_type_detail_data,
        "holiday_detail_data": holiday_rows,
        "sheet_names": ["AvgByStoreType", "HolidayVsNonHoliday"],
    }


def build_ecommerce_merge_report(
    world: SpreadsheetWorld,
    range_ref: str = "A1:Z200000",
) -> Dict[str, Any]:
    """Merge the Brazilian e-commerce CSV set and translate product category names."""
    tables = load_all_tables(
        world,
        range_ref=range_ref,
        require_primary_key=False,
        stop_at_note_row=False,
    )

    def pick(required: Sequence[str], preferred: Sequence[str] | None = None, forbidden: Sequence[str] | None = None) -> pd.DataFrame:
        return find_table_by_headers(
            tables,
            required_headers=required,
            preferred_headers=preferred or [],
            forbidden_headers=forbidden or [],
        )["df"].copy()

    order_items = pick(
        ["order_id", "order_item_id", "product_id", "seller_id", "shipping_limit_date", "price", "freight_value"]
    )
    reviews = pick(
        ["review_id", "order_id", "review_score", "review_creation_date"],
        preferred=["review_comment_message"],
    )
    orders = pick(
        ["order_id", "customer_id", "order_status", "order_purchase_timestamp"],
        preferred=["order_estimated_delivery_date"],
    )
    products = pick(
        ["product_id", "product_category_name", "product_name_lenght"],
        preferred=["product_weight_g"],
    )
    sellers = pick(
        ["seller_id", "seller_zip_code_prefix", "seller_city", "seller_state"]
    )
    payments = pick(
        ["order_id", "payment_sequential", "payment_type", "payment_installments", "payment_value"]
    )
    customers = pick(
        ["customer_id", "customer_unique_id", "customer_zip_code_prefix", "customer_city", "customer_state"]
    )

    translation_df: pd.DataFrame | None = None
    translation_required = {
        _normalize_header_name("product_category_name"),
        _normalize_header_name("product_category_name_english"),
    }
    for table in tables:
        header = {_normalize_header_name(col) for col in table.get("header", [])}
        if translation_required.issubset(header):
            translation_df = table["df"].copy()
            break

    if translation_df is None:
        raise ValueError("The product category translation table is required but was not loaded.")

    for df in [order_items, reviews, orders, products, sellers, payments, customers, translation_df]:
        df.columns = [str(col).strip() for col in df.columns]

    products_en = products.merge(translation_df, on="product_category_name", how="left")
    products_en["product_category_name_english"] = products_en["product_category_name_english"].fillna(
        products_en["product_category_name"]
    )
    products_en = products_en.drop(columns=["product_category_name"]).rename(
        columns={"product_category_name_english": "product_category_name"}
    )

    merged = orders.merge(order_items, on="order_id", how="inner")
    merged = merged.merge(payments, on="order_id", how="left")
    merged = merged.merge(reviews, on="order_id", how="left")
    merged = merged.merge(products_en, on="product_id", how="left")
    merged = merged.merge(customers, on="customer_id", how="left")
    merged = merged.merge(sellers, on="seller_id", how="left")

    ordered_columns = [
        "order_id",
        "customer_id",
        "order_status",
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
        "order_item_id",
        "product_id",
        "seller_id",
        "shipping_limit_date",
        "price",
        "freight_value",
        "payment_sequential",
        "payment_type",
        "payment_installments",
        "payment_value",
        "review_id",
        "review_score",
        "review_comment_title",
        "review_comment_message",
        "review_creation_date",
        "review_answer_timestamp",
        "product_name_lenght",
        "product_description_lenght",
        "product_photos_qty",
        "product_weight_g",
        "product_length_cm",
        "product_height_cm",
        "product_width_cm",
        "product_category_name",
        "customer_unique_id",
        "customer_zip_code_prefix",
        "customer_city",
        "customer_state",
        "seller_zip_code_prefix",
        "seller_city",
        "seller_state",
    ]
    missing = [col for col in ordered_columns if col not in merged.columns]
    if missing:
        raise ValueError(f"Merged e-commerce dataset is missing expected columns: {missing}")
    output_df = merged[ordered_columns].copy()
    detail_data = [output_df.columns.tolist()] + output_df.where(pd.notna(output_df), None).values.tolist()
    return {
        "output_df": output_df,
        "detail_data": detail_data,
        "row_count": int(len(output_df)),
        "column_count": int(len(output_df.columns)),
    }


def build_financial_dashboard_report(
    world: SpreadsheetWorld,
    range_ref: str = "A1:Z200",
) -> Dict[str, Any]:
    """Build a quarter-level financial dashboard from complementary monthly workbooks."""
    workbook_paths = list_all_workbooks(world)
    pnl_table = None
    sales_table = None
    target_table = None

    for file_path in workbook_paths:
        try:
            pnl_table = pnl_table or _extract_structured_table_from_workbook(
                world,
                file_path,
                required_headers=["Month", "Revenue", "Cost of Goods Sold", "Operating Expenses", "Interest Paid"],
                range_ref=range_ref,
            )
            if pnl_table and pnl_table["file_path"] == file_path:
                continue
        except Exception:
            pass
        try:
            sales_table = sales_table or _extract_structured_table_from_workbook(
                world,
                file_path,
                required_headers=["Month", "New Customers", "Marketing Spend"],
                range_ref=range_ref,
            )
            if sales_table and sales_table["file_path"] == file_path:
                continue
        except Exception:
            pass
        try:
            target_table = target_table or _extract_structured_table_from_workbook(
                world,
                file_path,
                required_headers=["KPI", "Q1 Target"],
                range_ref=range_ref,
            )
        except Exception:
            continue

    if pnl_table is None or sales_table is None or target_table is None:
        raise ValueError("Could not identify the P&L, sales/marketing, and KPI target tables.")

    pnl_df = pnl_table["df"].copy()
    sales_df = sales_table["df"].copy()
    target_df = target_table["df"].copy()

    month_col = _resolve_column_name(pnl_df.columns, "Month")
    revenue_col = _resolve_column_name(pnl_df.columns, "Revenue")
    cogs_col = _resolve_column_name(pnl_df.columns, "Cost of Goods Sold")
    opex_col = _resolve_column_name(pnl_df.columns, "Operating Expenses")
    interest_col = _resolve_column_name(pnl_df.columns, "Interest Paid")
    sales_month_col = _resolve_column_name(sales_df.columns, "Month")
    customers_col = _resolve_column_name(sales_df.columns, "New Customers")
    marketing_col = _resolve_column_name(sales_df.columns, "Marketing Spend")
    kpi_col = _resolve_column_name(target_df.columns, "KPI")
    target_col = _resolve_column_name(target_df.columns, "Q1 Target")

    for df, numeric_cols in (
        (pnl_df, [revenue_col, cogs_col, opex_col, interest_col]),
        (sales_df, [customers_col, marketing_col]),
    ):
        for col in numeric_cols:
            df[col] = df[col].map(_parse_numeric_text)
    pnl_df[month_col] = pnl_df[month_col].map(_normalize_cell_text)
    sales_df[sales_month_col] = sales_df[sales_month_col].map(_normalize_cell_text)
    target_df[kpi_col] = target_df[kpi_col].map(_normalize_cell_text)

    merged = pnl_df.merge(sales_df, left_on=month_col, right_on=sales_month_col, how="inner")
    if sales_month_col != month_col and sales_month_col in merged.columns:
        merged = merged.drop(columns=[sales_month_col])

    merged["Gross Profit"] = merged[revenue_col] - merged[cogs_col]
    merged["Net Profit"] = merged["Gross Profit"] - merged[opex_col] - merged[interest_col]
    merged["Gross Profit Margin"] = merged["Gross Profit"] / merged[revenue_col] * 100.0
    merged["Net Profit Margin"] = merged["Net Profit"] / merged[revenue_col] * 100.0
    merged["Customer Acquisition Cost (CAC)"] = merged[marketing_col] / merged[customers_col]
    merged["Marketing Efficiency Ratio"] = merged[revenue_col] / merged[marketing_col]

    total_revenue = float(merged[revenue_col].sum())
    total_gross_profit = float(merged["Gross Profit"].sum())
    total_net_profit = float(merged["Net Profit"].sum())
    total_customers = float(merged[customers_col].sum())
    total_marketing = float(merged[marketing_col].sum())

    dashboard_metrics = {
        "Gross Profit": total_gross_profit,
        "Net Profit": total_net_profit,
        "Gross Profit Margin": (total_gross_profit / total_revenue) * 100.0,
        "Net Profit Margin": (total_net_profit / total_revenue) * 100.0,
        "Customer Acquisition Cost (CAC)": total_marketing / total_customers,
        "Marketing Efficiency Ratio": total_revenue / total_marketing,
    }

    target_lookup = {
        _normalize_header_name(metric): _parse_numeric_text(value)
        for metric, value in zip(target_df[kpi_col], target_df[target_col])
        if _normalize_cell_text(metric)
    }

    dashboard_rows: list[list[Any]] = []
    for metric_name, actual in dashboard_metrics.items():
        lookup_key = _normalize_header_name(metric_name)
        if lookup_key not in target_lookup:
            raise ValueError(f"Target missing for KPI `{metric_name}`.")
        target_value = float(target_lookup[lookup_key])
        variance = actual - target_value
        dashboard_rows.append(
            [
                metric_name,
                _format_dashboard_metric(metric_name, actual),
                _format_dashboard_metric(metric_name, target_value),
                _format_dashboard_variance(metric_name, variance),
                _dashboard_assessment(metric_name, actual, target_value),
            ]
        )

    dashboard_header = [
        "Performance Metric",
        "Q1 Actual",
        "Q1 Target",
        "Variance (Actual - Target)",
        "Assessment",
    ]
    detail_data = [
        ["Title: Output - Financial Performance Dashboard", "", "", "", ""],
        ["[File: q1_performance_dashboard.xlsx]", "", "", "", ""],
        ["", "", "", "", ""],
        dashboard_header,
    ] + dashboard_rows

    output_df = pd.DataFrame(dashboard_rows, columns=dashboard_header)
    monthly_df = merged[
        [month_col, revenue_col, "Gross Profit", "Net Profit", "Customer Acquisition Cost (CAC)"]
    ].copy()

    return {
        "output_df": output_df,
        "detail_data": detail_data,
        "dashboard_df": output_df,
        "monthly_df": monthly_df,
        "row_count": int(len(output_df)),
        "column_count": int(len(output_df.columns)),
        "summary": {
            "Gross Profit": total_gross_profit,
            "Net Profit": total_net_profit,
        },
    }


def _count_skill_items(value: Any) -> int:
    text = _normalize_cell_text(value)
    if not text:
        return 0
    return len([part for part in re.split(r"[,\n;]+", text) if part.strip()])


def build_candidate_screening_report(
    world: SpreadsheetWorld,
    range_ref: str = "A1:Z50",
) -> Dict[str, Any]:
    """Aggregate candidate files, compute screening score, and rank valid candidates."""
    tables = load_all_tables(
        world,
        range_ref=range_ref,
        require_primary_key=False,
        stop_at_note_row=False,
    )
    if not tables:
        raise ValueError("No candidate tables were loaded.")

    concat_result = concat_tables_with_same_headers(tables)
    df = concat_result["output_df"].copy()

    name_col = _resolve_column_name(df.columns, "Name")
    skills_col = _resolve_column_name(df.columns, "Key Skills")
    education_col = _resolve_column_name(df.columns, "EDUCATION")
    companies_col = _resolve_column_name(df.columns, "Past companies")
    experience_col = _resolve_column_name(df.columns, "YearsOfExperience")
    personality_col = _resolve_column_name(df.columns, "Personality Score")

    df[name_col] = df[name_col].map(_normalize_cell_text)
    valid_df = df[df[name_col] != ""].copy()
    excluded_count = int(len(df) - len(valid_df))

    valid_df["_num_skills"] = valid_df[skills_col].map(_count_skill_items).astype(float)
    valid_df["_experience_num"] = valid_df[experience_col].map(_parse_numeric_text).fillna(0.0)
    valid_df["_personality_num"] = valid_df[personality_col].map(_parse_numeric_text).fillna(0.0)
    valid_df["capability_ranking"] = (
        0.5 * valid_df["_experience_num"]
        + 0.3 * valid_df["_num_skills"]
        + 0.2 * valid_df["_personality_num"]
    ).round(3)

    output_df = pd.DataFrame(
        {
            "candidate": valid_df[name_col].map(_normalize_cell_text),
            "capability_ranking": valid_df["capability_ranking"].astype(float),
            "skills": valid_df[skills_col],
            "education": valid_df[education_col],
            "past_companies": valid_df[companies_col],
            "years_of_experience": valid_df[experience_col],
            "personality_score": valid_df[personality_col],
        }
    )
    output_df = output_df.sort_values(
        by=["capability_ranking", "candidate"],
        ascending=[False, True],
    ).reset_index(drop=True)

    detail_data = [output_df.columns.tolist()] + output_df.fillna("").values.tolist()
    return {
        "output_df": output_df,
        "detail_data": detail_data,
        "row_count": int(len(output_df)),
        "column_count": int(len(output_df.columns)),
        "excluded_count": excluded_count,
    }


def build_inventory_eoq_report(
    world: SpreadsheetWorld,
    range_ref: str = "A1:Z50",
) -> Dict[str, Any]:
    """Build EOQ, sensitivity, and demand-growth scenario tables from one parameter sheet."""
    tables = load_all_tables(
        world,
        range_ref=range_ref,
        require_primary_key=True,
        stop_at_note_row=True,
    )
    if not tables:
        raise ValueError("No inventory parameter table was loaded.")

    df = tables[0]["df"].copy()
    parameter_col = _resolve_column_name(df.columns, "Parameter")
    value_col = _resolve_column_name(df.columns, "Value")

    param_lookup = {
        _normalize_header_name(parameter): _parse_numeric_text(value)
        for parameter, value in zip(df[parameter_col], df[value_col])
        if _normalize_cell_text(parameter)
    }

    demand = float(param_lookup[_normalize_header_name("Annual Demand (D)")])
    ordering_cost = float(param_lookup[_normalize_header_name("Ordering Cost (S)")])
    holding_cost = float(param_lookup[_normalize_header_name("Holding Cost (H)")])
    unit_cost = float(param_lookup[_normalize_header_name("Unit Cost (C)")])
    lead_time_days = float(param_lookup[_normalize_header_name("Lead Time (L)")])
    working_days = float(param_lookup[_normalize_header_name("Working Days per Year")])

    def _compute_metrics(annual_demand: float, quantity: float | None = None) -> Dict[str, float]:
        eoq = quantity if quantity is not None else float(np.sqrt((2.0 * annual_demand * ordering_cost) / holding_cost))
        orders_per_year = annual_demand / eoq
        cycle_time = working_days / orders_per_year
        reorder_point = (annual_demand / working_days) * lead_time_days
        total_annual_cost = (
            (annual_demand / eoq) * ordering_cost
            + (eoq / 2.0) * holding_cost
            + annual_demand * unit_cost
        )
        return {
            "EOQ": eoq,
            "Reorder Point": reorder_point,
            "Orders per Year": orders_per_year,
            "Cycle Time (days)": cycle_time,
            "Total Annual Cost": total_annual_cost,
        }

    base_metrics = _compute_metrics(demand)
    demand_up_metrics = _compute_metrics(demand * 1.2)

    sensitivity_rows = []
    for pct in (0.5, 0.75, 1.0, 1.25, 1.5):
        quantity = float(round(base_metrics["EOQ"] * pct))
        metrics = _compute_metrics(demand, quantity=quantity)
        sensitivity_rows.append(
            [
                f"{int(round(pct * 100))}% EOQ",
                int(quantity),
                round(metrics["Total Annual Cost"], 2),
            ]
        )

    base_table = [
        ["Base Scenario Metric", "Value"],
        ["EOQ", round(base_metrics["EOQ"], 2)],
        ["Reorder Point", round(base_metrics["Reorder Point"], 2)],
        ["Orders per Year", round(base_metrics["Orders per Year"], 2)],
        ["Cycle Time (days)", round(base_metrics["Cycle Time (days)"], 2)],
        ["Total Annual Cost", round(base_metrics["Total Annual Cost"], 2)],
    ]
    sensitivity_table = [
        ["Sensitivity Scenario", "Order Quantity", "Total Annual Cost"],
        *sensitivity_rows,
    ]
    demand_table = [
        ["Demand +20% Metric", "Value"],
        ["EOQ", round(demand_up_metrics["EOQ"], 2)],
        ["Reorder Point", round(demand_up_metrics["Reorder Point"], 2)],
        ["Orders per Year", round(demand_up_metrics["Orders per Year"], 2)],
        ["Cycle Time (days)", round(demand_up_metrics["Cycle Time (days)"], 2)],
        ["Total Annual Cost", round(demand_up_metrics["Total Annual Cost"], 2)],
    ]

    detail_data = [
        ["Inventory EOQ Analysis", "", ""],
        ["", "", ""],
        *base_table,
        ["", "", ""],
        *sensitivity_table,
        ["", "", ""],
        *demand_table,
    ]

    output_df = pd.DataFrame(base_table[1:], columns=base_table[0])
    return {
        "output_df": output_df,
        "detail_data": detail_data,
        "base_metrics": base_metrics,
        "demand_up_metrics": demand_up_metrics,
        "sensitivity_rows": sensitivity_rows,
    }


def build_hospital_utilisation_report(
    world: SpreadsheetWorld,
    range_ref: str = "A1:Z10000",
) -> Dict[str, Any]:
    """Aggregate hospital resource tables into one service-level utilisation report."""
    tables = load_all_tables(
        world,
        range_ref=range_ref,
        require_primary_key=True,
        stop_at_note_row=True,
    )
    if len(tables) < 3:
        raise ValueError("Hospital utilisation workflow expects patient, service, and staff tables.")

    patient_table = find_table_by_headers(
        tables,
        required_headers=["patient_id", "service", "arrival_date", "departure_date"],
    )
    service_table = find_table_by_headers(
        tables,
        required_headers=["service", "available_beds", "patients_request", "patients_admitted"],
    )
    staff_table = find_table_by_headers(
        tables,
        required_headers=["week", "staff_id", "service", "present"],
    )

    patient_df = patient_table["df"].copy()
    service_df = service_table["df"].copy()
    staff_df = staff_table["df"].copy()

    patient_service_col = _resolve_column_name(patient_df.columns, "service")
    arrival_col = _resolve_column_name(patient_df.columns, "arrival_date")
    departure_col = _resolve_column_name(patient_df.columns, "departure_date")
    service_col = _resolve_column_name(service_df.columns, "service")
    request_col = _resolve_column_name(service_df.columns, "patients_request")
    admitted_col = _resolve_column_name(service_df.columns, "patients_admitted")
    staff_service_col = _resolve_column_name(staff_df.columns, "service")
    present_col = _resolve_column_name(staff_df.columns, "present")

    patient_df[arrival_col] = pd.to_datetime(patient_df[arrival_col], errors="coerce")
    patient_df[departure_col] = pd.to_datetime(patient_df[departure_col], errors="coerce")
    patient_df["avg_stay_days"] = (patient_df[departure_col] - patient_df[arrival_col]).dt.days

    service_df[request_col] = pd.to_numeric(service_df[request_col], errors="coerce")
    service_df[admitted_col] = pd.to_numeric(service_df[admitted_col], errors="coerce")
    staff_df[present_col] = pd.to_numeric(staff_df[present_col], errors="coerce")

    patient_summary = (
        patient_df.groupby(patient_service_col, dropna=False)
        .agg(avg_stay=("avg_stay_days", "mean"), patient_count=(patient_service_col, "size"))
        .reset_index()
    )
    service_summary = (
        service_df.groupby(service_col, dropna=False)
        .agg(total_request=(request_col, "sum"), total_admitted=(admitted_col, "sum"))
        .reset_index()
    )
    staff_summary = (
        staff_df.groupby(staff_service_col, dropna=False)
        .agg(staff_utilisation=(present_col, "mean"))
        .reset_index()
    )

    merged = patient_summary.merge(
        service_summary,
        left_on=patient_service_col,
        right_on=service_col,
        how="outer",
    ).merge(
        staff_summary,
        left_on=patient_service_col,
        right_on=staff_service_col,
        how="outer",
    )

    service_name_col = patient_service_col
    merged["service_utilisation"] = merged["total_admitted"] / merged["total_request"]
    output_df = pd.DataFrame(
        {
            "service": merged[service_name_col].map(_normalize_cell_text),
            "staff_utilisation": merged["staff_utilisation"].astype(float),
            "service_utilisation": merged["service_utilisation"].astype(float),
            "avg_stay": merged["avg_stay"].astype(float),
            "patient_count": merged["patient_count"].astype(int),
        }
    ).sort_values(by="service").reset_index(drop=True)

    highlight_rows = [
        index + 2
        for index, row in output_df.iterrows()
        if float(row["staff_utilisation"]) > 0.9 or float(row["service_utilisation"]) > 0.9
    ]

    detail_data = [output_df.columns.tolist()] + output_df.values.tolist()
    return {
        "output_df": output_df,
        "detail_data": detail_data,
        "highlight_rows": highlight_rows,
    }


def compute_feature_correlations(
    df: pd.DataFrame,
    target_col: str,
    feature_cols: Sequence[str],
    round_digits: int | None = None,
) -> Dict[str, Any]:
    """Compute pairwise Pearson correlations between a target and feature columns."""
    if not feature_cols:
        raise ValueError("feature_cols must not be empty.")
    working, actual_target_col, actual_feature_cols = _prepare_numeric_feature_frame(
        df,
        feature_cols,
        target_col=target_col,
    )
    assert actual_target_col is not None

    correlation_row: list[Any] = []
    correlation_map: Dict[str, float] = {}
    for feature in actual_feature_cols:
        pair = working[[feature, actual_target_col]].dropna()
        if len(pair) < 2:
            corr_value = np.nan
        else:
            corr_value = float(pair[feature].corr(pair[actual_target_col]))
        if round_digits is not None and not pd.isna(corr_value):
            corr_value = round(corr_value, round_digits)
        correlation_map[feature] = corr_value
        correlation_row.append(corr_value)

    detail_data = [actual_feature_cols, correlation_row]
    output_df = pd.DataFrame([correlation_row], columns=actual_feature_cols)
    return {
        "target_col": actual_target_col,
        "feature_cols": actual_feature_cols,
        "correlations": correlation_map,
        "output_df": output_df,
        "detail_data": detail_data,
    }


def build_correlation_matrix_table(
    df: pd.DataFrame,
    numeric_columns: Sequence[str],
    filter_column: str | None = None,
    filter_value: Any | None = None,
    round_digits: int = 2,
) -> Dict[str, Any]:
    """Build a labeled correlation matrix table for selected numeric columns."""
    working_df = df.copy()
    if filter_column is not None:
        actual_filter_col = _resolve_column_name(working_df.columns, filter_column)
        normalized_filter = _normalize_cell_text(filter_value).lower()
        working_df = working_df[
            working_df[actual_filter_col].map(_normalize_cell_text).str.lower() == normalized_filter
        ]

    working, _, actual_numeric_cols = _prepare_numeric_feature_frame(
        working_df,
        numeric_columns,
        target_col=None,
    )
    matrix_df = working[actual_numeric_cols].dropna(how="all").corr().round(round_digits)
    detail_data = [[""] + actual_numeric_cols]
    for column in actual_numeric_cols:
        row_values = matrix_df.loc[column].tolist() if column in matrix_df.index else [np.nan] * len(actual_numeric_cols)
        detail_data.append([column] + row_values)
    return {
        "matrix_df": matrix_df,
        "output_df": matrix_df,
        "detail_data": detail_data,
        "row_count": int(len(matrix_df)),
        "column_count": int(len(matrix_df.columns)),
        "numeric_columns": actual_numeric_cols,
    }


def fit_linear_regression_weights(
    df: pd.DataFrame,
    target_col: str,
    feature_cols: Sequence[str],
    round_digits: int | None = None,
) -> Dict[str, Any]:
    """Fit a linear regression with numpy least squares and return coefficient table."""
    if not feature_cols:
        raise ValueError("feature_cols must not be empty.")
    working, actual_target_col, actual_feature_cols = _prepare_numeric_feature_frame(
        df,
        feature_cols,
        target_col=target_col,
    )
    assert actual_target_col is not None
    model_df = working[actual_feature_cols + [actual_target_col]].dropna().copy()
    if model_df.empty:
        raise ValueError("No complete rows remain after numeric coercion for regression.")

    x = model_df[actual_feature_cols].to_numpy(float)
    y = model_df[actual_target_col].to_numpy(float)
    design = np.c_[np.ones(len(model_df)), x]
    beta = np.linalg.lstsq(design, y, rcond=None)[0].tolist()
    factor_names = ["Intercept"] + actual_feature_cols
    weights = [round(value, round_digits) if round_digits is not None else float(value) for value in beta]

    coefficients_df = pd.DataFrame(
        {
            "Factor": factor_names,
            "Weight": weights,
        }
    )
    detail_data = [coefficients_df.columns.tolist()] + coefficients_df.values.tolist()
    return {
        "used_features": actual_feature_cols,
        "target_col": actual_target_col,
        "row_count": int(len(model_df)),
        "coefficients_df": coefficients_df,
        "output_df": coefficients_df,
        "detail_data": detail_data,
    }


def _split_dependencies(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, float) and pd.isna(value):
        return []
    text = _normalize_cell_text(value)
    if not text:
        return []
    parts = [_normalize_cell_text(part) for part in _DEP_SPLIT_RE.split(text)]
    return [part for part in parts if part]


def _parse_start_time_minutes(start_time: str) -> int:
    text = _normalize_cell_text(start_time)
    matched = re.fullmatch(r"(\d{1,2}):(\d{2})", text)
    if not matched:
        raise ValueError("start_time must be in HH:MM format.")
    hour = int(matched.group(1))
    minute = int(matched.group(2))
    return hour * 60 + minute


def _format_hhmm(total_minutes: int) -> str:
    minutes = int(round(total_minutes))
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _has_directed_cycle(edges_df: pd.DataFrame, from_col: str, to_col: str) -> bool:
    adjacency: Dict[str, List[str]] = {}
    nodes: set[str] = set()

    for _, row in edges_df.iterrows():
        source = _normalize_cell_text(row[from_col])
        if not source:
            continue
        nodes.add(source)
        adjacency.setdefault(source, [])
        targets = _split_dependencies(row[to_col])
        for target in targets:
            if not target:
                continue
            nodes.add(target)
            adjacency.setdefault(target, [])
            adjacency[source].append(target)

    visited: set[str] = set()
    visiting: set[str] = set()

    def dfs(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for neighbor in adjacency.get(node, []):
            if dfs(neighbor):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    for node in sorted(nodes):
        if dfs(node):
            return True
    return False


def build_cycle_detection_report(
    tables: Sequence[Dict[str, Any]],
    from_col: str = "Node From",
    to_col: str = "Node To",
) -> Dict[str, Any]:
    """Detect cycles for a sequence of directed-graph adjacency-list tables."""
    if not tables:
        raise ValueError("No tables available for cycle detection.")

    rows: List[List[Any]] = [["Graph ID", "Contains Cycle (True / False)"]]
    result_records: List[Dict[str, Any]] = []

    for index, table in enumerate(tables, start=1):
        df = table.get("df")
        if not isinstance(df, pd.DataFrame):
            raise ValueError("Each table must include a pandas DataFrame under `df`.")
        actual_from = _resolve_column_name(df.columns, from_col)
        actual_to = _resolve_column_name(df.columns, to_col)
        contains_cycle = _has_directed_cycle(df, actual_from, actual_to)
        graph_id = f"graph_{index}"
        rows.append([graph_id, bool(contains_cycle)])
        result_records.append(
            {
                "Graph ID": graph_id,
                "Contains Cycle (True / False)": bool(contains_cycle),
                "file_name": table.get("file_name"),
            }
        )

    output_df = pd.DataFrame(result_records)[["Graph ID", "Contains Cycle (True / False)"]]
    return {
        "output_df": output_df,
        "detail_data": rows,
        "row_count": int(len(output_df)),
        "column_count": int(len(output_df.columns)),
    }


def _deduplicate_task_rows(
    task_df: pd.DataFrame,
    task_id_col: str,
    task_name_col: str,
    priority_col: str,
    duration_col: str,
) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    seen: Dict[str, Dict[str, Any]] = {}

    working_df = task_df.copy()
    working_df[task_id_col] = working_df[task_id_col].map(_normalize_cell_text)
    working_df[task_name_col] = working_df[task_name_col].map(_normalize_cell_text)
    working_df[priority_col] = working_df[priority_col].map(_normalize_cell_text)
    working_df[duration_col] = pd.to_numeric(working_df[duration_col], errors="coerce")

    for _, row in working_df.iterrows():
        task_id = _normalize_cell_text(row[task_id_col])
        if not task_id:
            continue
        duration_value = row[duration_col]
        if pd.isna(duration_value):
            raise ValueError(f"Task `{task_id}` has non-numeric `{duration_col}`.")
        record = {
            task_id_col: task_id,
            task_name_col: _normalize_cell_text(row[task_name_col]),
            priority_col: _normalize_cell_text(row[priority_col]),
            duration_col: float(duration_value),
        }
        existing = seen.get(task_id)
        if existing is not None and existing != record:
            raise ValueError(
                f"Task `{task_id}` appears multiple times with conflicting task metadata."
            )
        if existing is None:
            seen[task_id] = record
            records.append(record)
    return records


def build_dependency_schedule(
    task_df: pd.DataFrame,
    dependency_df: pd.DataFrame,
    start_time: str = "08:00",
    task_id_col: str = "Task ID",
    task_name_col: str = "Task Name",
    priority_col: str = "Priority",
    duration_col: str = "Duration (hours)",
    depends_on_col: str = "Depends on",
) -> Dict[str, Any]:
    """Build a dependency schedule from task and dependency tables."""
    task_id_actual = _resolve_column_name(task_df.columns, task_id_col)
    task_name_actual = _resolve_column_name(task_df.columns, task_name_col)
    priority_actual = _resolve_column_name(task_df.columns, priority_col)
    duration_actual = _resolve_column_name(task_df.columns, duration_col)
    dep_task_id_actual = _resolve_column_name(dependency_df.columns, task_id_col)
    depends_on_actual = _resolve_column_name(dependency_df.columns, depends_on_col)

    task_records = _deduplicate_task_rows(
        task_df,
        task_id_col=task_id_actual,
        task_name_col=task_name_actual,
        priority_col=priority_actual,
        duration_col=duration_actual,
    )
    if not task_records:
        raise ValueError("Task table is empty after normalization.")

    task_order = [record[task_id_actual] for record in task_records]
    task_id_set = set(task_order)
    task_by_id = {record[task_id_actual]: record for record in task_records}

    adjacency: Dict[str, List[str]] = {task_id: [] for task_id in task_order}
    in_degree: Dict[str, int] = {task_id: 0 for task_id in task_order}

    dependency_working = dependency_df.copy()
    dependency_working[dep_task_id_actual] = dependency_working[dep_task_id_actual].map(_normalize_cell_text)

    for _, row in dependency_working.iterrows():
        task_id = _normalize_cell_text(row[dep_task_id_actual])
        if not task_id:
            continue
        if task_id not in task_id_set:
            raise ValueError(
                f"Dependency table references task `{task_id}` which is missing from the task table."
            )
        predecessors = _split_dependencies(row[depends_on_actual])
        for predecessor in predecessors:
            if predecessor not in task_id_set:
                raise ValueError(
                    f"Dependency `{predecessor}` for task `{task_id}` is missing from the task table."
                )
            adjacency[predecessor].append(task_id)
            in_degree[task_id] += 1

    queue = deque(task_id for task_id in task_order if in_degree[task_id] == 0)
    schedule_order: List[str] = []
    while queue:
        current_task = queue.popleft()
        schedule_order.append(current_task)
        for dependent_task in adjacency[current_task]:
            in_degree[dependent_task] -= 1
            if in_degree[dependent_task] == 0:
                queue.append(dependent_task)

    if len(schedule_order) != len(task_order):
        raise ValueError("Dependency graph contains a cycle or unresolved task IDs.")

    current_minutes = _parse_start_time_minutes(start_time)
    detail_data: List[List[Any]] = [
        [task_id_col, task_name_col, priority_col, "Start Time", "End Time"]
    ]
    total_duration_hours = 0.0
    for task_id in schedule_order:
        record = task_by_id[task_id]
        duration_hours = float(record[duration_actual])
        duration_minutes = int(round(duration_hours * 60))
        start_text = _format_hhmm(current_minutes)
        end_minutes = current_minutes + duration_minutes
        end_text = _format_hhmm(end_minutes)
        detail_data.append(
            [
                task_id,
                record[task_name_actual],
                record[priority_actual],
                start_text,
                end_text,
            ]
        )
        current_minutes = end_minutes
        total_duration_hours += duration_hours

    return {
        "task_id_set": task_id_set,
        "scheduled_task_ids": list(schedule_order),
        "detail_data": detail_data,
        "total_duration": float(total_duration_hours * 60.0),
        "total_duration_hours": float(total_duration_hours),
        "summary": {"Total Duration (hours)": float(total_duration_hours)},
        "summary_rows": [["Total Duration (hours)", float(total_duration_hours)]],
    }


__all__ = [
    "load_all_tables",
    "find_table_by_headers",
    "infer_common_key",
    "concat_tables_with_same_headers",
    "merge_tables_on_key",
    "fill_missing_from_reference",
    "summarize_numeric_column",
    "build_group_summary",
    "compute_feature_correlations",
    "build_correlation_matrix_table",
    "fit_linear_regression_weights",
    "build_region_growth_analysis",
    "build_financial_dashboard_report",
    "build_candidate_screening_report",
    "build_inventory_eoq_report",
    "build_hospital_utilisation_report",
    "build_dependency_schedule",
    "build_cycle_detection_report",
]
