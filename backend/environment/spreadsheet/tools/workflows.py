"""Higher-level spreadsheet workflow helpers."""

from __future__ import annotations

import os
import re
from collections import deque
from typing import Any, Callable, Dict, Iterable, List, Sequence

import numpy as np
import pandas as pd

from ..world import SpreadsheetWorld
from .cross_workbook import get_workbook, list_all_workbooks, read_table_multi


_HEADER_XML_ESCAPE_RE = re.compile(r"_x[0-9A-Fa-f]{4}_")
_DEP_SPLIT_RE = re.compile(r"[,\n;]+")
_CAMEL_CASE_BOUNDARY_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def _normalize_header_name(value: Any) -> str:
    text = str(value or "")
    text = _HEADER_XML_ESCAPE_RE.sub("", text)
    text = _CAMEL_CASE_BOUNDARY_RE.sub(" ", text)
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


def _select_contiguous_labeled_columns(
    header_row: Sequence[Any],
    start_col_idx: int,
    stop_markers: Sequence[str] = (),
) -> list[tuple[int, str]]:
    """Return the first contiguous block of non-empty labels after ``start_col_idx``."""
    selected: list[tuple[int, str]] = []
    normalized_stops = tuple(_normalize_header_name(marker) for marker in stop_markers if marker)
    for col_idx in range(start_col_idx, len(header_row)):
        label = _normalize_cell_text(header_row[col_idx])
        if not label:
            if selected:
                break
            continue
        normalized_label = _normalize_header_name(label)
        if normalized_stops and normalized_label in normalized_stops:
            break
        selected.append((col_idx, label))
    return selected


def _find_first_period_cell(
    rows: Sequence[Sequence[Any]],
    is_period_value: Callable[[Any], bool],
) -> tuple[int, int] | None:
    """Find the first row/column whose first non-empty cell matches a period predicate."""
    for row_idx, row in enumerate(rows):
        non_empty = [(col_idx, value) for col_idx, value in enumerate(row) if _normalize_cell_text(value)]
        if not non_empty:
            continue
        first_non_empty_idx, first_non_empty_value = non_empty[0]
        if is_period_value(first_non_empty_value):
            return row_idx, first_non_empty_idx
    return None


def _extract_period_records(
    rows: Sequence[Sequence[Any]],
    period_col_idx: int,
    labeled_columns: Sequence[tuple[int, str]],
    is_period_value: Callable[[Any], bool],
    period_transform: Callable[[Any], Any] | None = None,
    period_key: str = "Year",
) -> list[dict[str, Any]]:
    """Extract a contiguous period/value block into records."""
    records: list[dict[str, Any]] = []
    transform = period_transform or (lambda value: value)
    for row in rows:
        if period_col_idx >= len(row) or not is_period_value(row[period_col_idx]):
            if records:
                break
            continue
        period_value = transform(row[period_col_idx])
        record: dict[str, Any] = {period_key: period_value}
        for col_idx, label in labeled_columns:
            record[label] = row[col_idx] if col_idx < len(row) else None
        records.append(record)
    return records


def _merge_on_shared_period(
    left_records: Sequence[dict[str, Any]] | pd.DataFrame,
    right_records: Sequence[dict[str, Any]] | pd.DataFrame,
    period_col: str,
) -> pd.DataFrame:
    """Inner-join two period-indexed datasets and require at least one shared period."""
    left_df = left_records.copy() if isinstance(left_records, pd.DataFrame) else pd.DataFrame(left_records)
    right_df = right_records.copy() if isinstance(right_records, pd.DataFrame) else pd.DataFrame(right_records)
    overlap_df = left_df.merge(right_df, on=period_col, how="inner")
    if overlap_df.empty:
        raise ValueError(f"No overlapping period was found on `{period_col}`.")
    return overlap_df


def _build_grouped_assignment_join(
    assignment_df: pd.DataFrame,
    assignment_col: str,
    entity_col: str,
    schedule_df: pd.DataFrame,
    resource_col: str,
    schedule_cols: Sequence[str],
) -> pd.DataFrame:
    """Group assigned entities by resource and join them onto schedule rows."""
    grouped_entities = (
        assignment_df.groupby(assignment_col, sort=False)[entity_col]
        .apply(lambda values: ", ".join(value for value in values if _normalize_cell_text(value)))
        .reset_index()
        .rename(columns={assignment_col: resource_col})
    )
    selected_schedule_cols = [resource_col] + [column for column in schedule_cols if column != resource_col]
    output_df = schedule_df[selected_schedule_cols].copy()
    output_df = output_df.merge(grouped_entities, on=resource_col, how="left")
    output_df[entity_col] = output_df[entity_col].fillna("")
    sort_cols = [resource_col] + [column for column in schedule_cols if column in output_df.columns]
    return output_df.sort_values(by=sort_cols, kind="stable").reset_index(drop=True)


def _build_weighted_period_output(
    overlap_df: pd.DataFrame,
    period_col: str,
    value_columns: Sequence[str],
    weight_col: str,
    output_period_col: str,
    output_label_template: str = "{name}",
    scale: float = 100.0,
    round_digits: int = 2,
) -> pd.DataFrame:
    """Scale per-period value columns by a shared weight column into a new output table."""
    output_df = pd.DataFrame({output_period_col: overlap_df[period_col]})
    weights = pd.to_numeric(overlap_df[weight_col], errors="coerce").fillna(0).astype(float)
    for column in value_columns:
        values = pd.to_numeric(overlap_df[column], errors="coerce").fillna(0).astype(float)
        output_df[output_label_template.format(name=column)] = ((values * weights) / scale).round(round_digits)
    return output_df


def select_contiguous_labeled_columns(
    header_row: Sequence[Any],
    start_col_idx: int,
    stop_markers: Sequence[str] = (),
) -> list[tuple[int, str]]:
    """Public wrapper for selecting a contiguous labeled column block."""
    return _select_contiguous_labeled_columns(
        header_row,
        start_col_idx=start_col_idx,
        stop_markers=stop_markers,
    )


def find_first_period_cell(
    rows: Sequence[Sequence[Any]],
    match_regex: str,
) -> tuple[int, int] | None:
    """Public wrapper that finds the first period-like cell by regex."""
    pattern = re.compile(match_regex)
    return _find_first_period_cell(
        rows,
        is_period_value=lambda value: bool(pattern.match(_normalize_cell_text(value))),
    )


def extract_period_records(
    rows: Sequence[Sequence[Any]],
    period_col_idx: int,
    labeled_columns: Sequence[tuple[int, str]],
    match_regex: str,
    cast_period: str | None = None,
    period_key: str = "Year",
) -> list[dict[str, Any]]:
    """Public wrapper that turns a contiguous period/value block into records."""
    pattern = re.compile(match_regex)

    def _transform_period(value: Any) -> Any:
        normalized = _normalize_cell_text(value)
        if cast_period == "int":
            return int(normalized)
        return normalized

    return _extract_period_records(
        rows,
        period_col_idx=period_col_idx,
        labeled_columns=labeled_columns,
        is_period_value=lambda value: bool(pattern.match(_normalize_cell_text(value))),
        period_transform=_transform_period,
        period_key=period_key,
    )


def merge_on_shared_period(
    left_records: Sequence[dict[str, Any]] | pd.DataFrame,
    right_records: Sequence[dict[str, Any]] | pd.DataFrame,
    period_col: str,
) -> pd.DataFrame:
    """Public wrapper for joining two period-indexed datasets."""
    return _merge_on_shared_period(left_records, right_records, period_col=period_col)


def build_grouped_assignment_join(
    assignment_df: pd.DataFrame,
    assignment_col: str,
    entity_col: str,
    schedule_df: pd.DataFrame,
    resource_col: str,
    schedule_cols: Sequence[str],
) -> pd.DataFrame:
    """Public wrapper for grouped assignment schedule joins."""
    return _build_grouped_assignment_join(
        assignment_df=assignment_df,
        assignment_col=assignment_col,
        entity_col=entity_col,
        schedule_df=schedule_df,
        resource_col=resource_col,
        schedule_cols=schedule_cols,
    )


def build_weighted_period_output(
    overlap_df: pd.DataFrame,
    period_col: str,
    value_columns: Sequence[str],
    weight_col: str,
    output_period_col: str,
    output_label_template: str = "{name}",
    scale: float = 100.0,
    round_digits: int = 2,
) -> pd.DataFrame:
    """Public wrapper for scaling value columns by a shared period weight."""
    return _build_weighted_period_output(
        overlap_df,
        period_col=period_col,
        value_columns=value_columns,
        weight_col=weight_col,
        output_period_col=output_period_col,
        output_label_template=output_label_template,
        scale=scale,
        round_digits=round_digits,
    )


def _resolve_column_name(columns: Iterable[Any], requested_name: str, *fallback_names: str) -> str:
    requested_names = (requested_name,) + tuple(fallback_names)
    normalized_candidates = {_normalize_header_name(name) for name in requested_names if name}
    for column in columns:
        if _normalize_header_name(column) in normalized_candidates:
            return str(column)
    raise ValueError(f"Column `{requested_name}` not found in {list(columns)}")


def _detail_data_from_df(df: pd.DataFrame) -> list[list[Any]]:
    return [df.columns.tolist()] + df.fillna("").values.tolist()


def _tabular_result(output_df: pd.DataFrame, metadata: Dict[str, Any] | None = None, **extra: Any) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "output_df": output_df,
        "detail_data": _detail_data_from_df(output_df),
        "row_count": int(len(output_df)),
        "column_count": int(len(output_df.columns)),
        "metadata": metadata or {},
    }
    result.update(extra)
    return result


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


def _is_identifier_like_column(series: pd.Series, column_name: str) -> bool:
    normalized = _normalize_header_name(column_name)
    header_markers = (
        "room",
        "venue",
        "location",
        "seat",
        "desk",
        "lab",
        "code",
        "identifier",
        "id",
    )
    if any(marker in normalized for marker in header_markers):
        return True

    non_empty = [_normalize_cell_text(value) for value in series.tolist() if _normalize_cell_text(value)]
    if len(non_empty) < 2:
        return False
    code_like = [value for value in non_empty[:20] if re.search(r"[A-Za-z]\s*\d", value)]
    return len(code_like) >= 2


def load_all_tables(
    world: SpreadsheetWorld,
    range_ref: str = "A1:Z200",
    require_primary_key: bool = True,
    stop_at_note_row: bool = True,
) -> List[Dict[str, Any]]:
    """Load the best visible table from every workbook into a standard structure."""
    tables: List[Dict[str, Any]] = []
    for file_path in list_all_workbooks(world):
        wb = get_workbook(world, file_path)
        best_table: Dict[str, Any] | None = None
        best_score: tuple[int, int, int] | None = None

        for sheet_name in wb.sheetnames:
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
            score = (
                1 if str(sheet_name).strip().lower() == "data" else 0,
                len(header),
                len(table.get("rows", [])),
            )
            if best_score is None or score > best_score:
                best_score = score
                best_table = table

        if best_table is None:
            continue

        table = best_table
        header = table.get("header", [])
        if not header:
            continue
        df = pd.DataFrame(table["rows"], columns=header)
        tables.append(
            {
                "file_path": file_path,
                "file": os.path.basename(file_path),
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


def infer_common_keys(
    tables: Sequence[Dict[str, Any]],
    preferred_headers: Sequence[str] | None = None,
    max_keys: int = 2,
) -> list[str]:
    """Infer a small composite key from headers shared by all selected tables."""
    if not tables:
        raise ValueError("No tables available to infer common keys.")

    header_lists = [list(table.get("header", [])) for table in tables]
    if not all(header_lists):
        raise ValueError("All tables must have headers to infer common keys.")

    common_normalized = {_normalize_header_name(col) for col in header_lists[0]}
    for header_list in header_lists[1:]:
        common_normalized &= {_normalize_header_name(col) for col in header_list}

    if not common_normalized:
        raise ValueError("No common headers found across the selected tables.")

    actual_lookup: Dict[str, str] = {}
    for col in header_lists[0]:
        normalized = _normalize_header_name(col)
        if normalized in common_normalized and normalized not in actual_lookup:
            actual_lookup[normalized] = str(col)

    preferred_normalized = [
        _normalize_header_name(col)
        for col in (preferred_headers or [])
        if _normalize_header_name(col) in common_normalized
    ]

    def _score_key(normalized: str) -> tuple[int, int, str]:
        score = 0
        if normalized in preferred_normalized:
            score += 200
        if any(marker in normalized for marker in ("id", "code", "number", "key")):
            score += 90
        if any(marker in normalized for marker in ("term", "semester", "quarter", "year", "month", "date", "day", "time", "slot")):
            score += 70
        if any(marker in normalized for marker in ("section", "class", "group", "course", "program", "room", "session", "campus")):
            score += 55
        if any(marker in normalized for marker in ("name", "title", "status", "email", "phone", "address", "note", "description")):
            score -= 30
        return (score, -len(normalized), normalized)

    ordered = sorted(common_normalized, key=_score_key, reverse=True)
    selected: list[str] = []
    for normalized in preferred_normalized:
        if normalized not in selected:
            selected.append(normalized)
    for normalized in ordered:
        if normalized not in selected:
            selected.append(normalized)
        if len(selected) >= max_keys:
            break

    resolved = [actual_lookup[key] for key in selected[:max_keys] if key in actual_lookup]
    if len(resolved) < 2:
        raise ValueError(
            f"Unable to infer a stable composite key. common_headers={sorted(actual_lookup.values())}"
        )
    return resolved


def _join_key_score(normalized: str) -> int:
    score = 0
    if any(marker in normalized for marker in ("id", "code", "key", "number")):
        score += 100
    if any(marker in normalized for marker in ("month", "date", "year", "quarter", "week", "day", "period", "time")):
        score += 70
    if any(marker in normalized for marker in ("category", "region", "segment", "department", "group", "class", "type")):
        score += 45
    if any(marker in normalized for marker in ("name", "title", "description", "manager", "city", "note")):
        score -= 25
    return score


def _shared_join_key_candidates(
    left_headers: Sequence[Any],
    right_headers: Sequence[Any],
    max_keys: int = 3,
) -> list[tuple[str, str, str, int]]:
    left_lookup = {
        _normalize_header_name(col): str(col)
        for col in left_headers
    }
    right_lookup = {
        _normalize_header_name(col): str(col)
        for col in right_headers
    }
    shared = set(left_lookup) & set(right_lookup)
    scored: list[tuple[str, str, str, int]] = []
    for normalized in shared:
        score = _join_key_score(normalized)
        if score <= 0:
            continue
        scored.append((left_lookup[normalized], right_lookup[normalized], normalized, score))
    scored.sort(key=lambda item: (-item[3], item[2]))
    return scored[:max_keys]


def _count_numeric_non_key_columns(df: pd.DataFrame, key_columns: Sequence[str]) -> int:
    key_set = {_normalize_header_name(col) for col in key_columns}
    count = 0
    for col in df.columns:
        if _normalize_header_name(col) in key_set:
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            count += 1
    return count


def _rows_are_unique_for_keys(df: pd.DataFrame, key_columns: Sequence[str]) -> bool:
    if df.empty or not key_columns:
        return False
    working = df.copy()
    for column in key_columns:
        working[column] = working[column].map(_normalize_cell_text)
    non_empty_mask = pd.Series(True, index=working.index)
    for column in key_columns:
        non_empty_mask &= working[column] != ""
    working = working[non_empty_mask]
    if working.empty:
        return False
    return not working.duplicated(subset=list(key_columns)).any()


def _merge_current_with_table(
    left_df: pd.DataFrame,
    right_df: pd.DataFrame,
    left_keys: Sequence[str],
    right_keys: Sequence[str],
    how: str,
    suffix_index: int,
) -> pd.DataFrame:
    merged_left = left_df.copy()
    merged_right = right_df.copy()
    for key_name in left_keys:
        merged_left[key_name] = merged_left[key_name].map(_normalize_cell_text)
    for key_name in right_keys:
        merged_right[key_name] = merged_right[key_name].map(_normalize_cell_text)

    merged_right = merged_right.drop_duplicates(subset=list(right_keys), keep="first")
    existing_norm = {_normalize_header_name(col) for col in merged_left.columns}
    rename_map: dict[str, str] = {}
    for col in merged_right.columns:
        if col in right_keys:
            continue
        if _normalize_header_name(col) in existing_norm:
            rename_map[col] = f"{col}_{suffix_index}"
    if rename_map:
        merged_right = merged_right.rename(columns=rename_map)

    merged = merged_left.merge(
        merged_right,
        left_on=list(left_keys),
        right_on=list(right_keys),
        how=how,
    )
    for left_key, right_key in zip(left_keys, right_keys):
        if right_key != left_key and right_key in merged.columns:
            merged = merged.drop(columns=[right_key])
    return merged


def _choose_bridge_join_seed_index(tables: Sequence[Dict[str, Any]]) -> int:
    best_index = 0
    best_score: tuple[int, int, int] | None = None
    for idx, table in enumerate(tables):
        df = table.get("df")
        if not isinstance(df, pd.DataFrame):
            continue
        headers = list(df.columns)
        pair_score = 0
        for other_idx, other in enumerate(tables):
            if idx == other_idx:
                continue
            other_df = other.get("df")
            if not isinstance(other_df, pd.DataFrame):
                continue
            pair_score += sum(score for *_rest, score in _shared_join_key_candidates(headers, list(other_df.columns)))
        table_score = (
            pair_score,
            len(headers),
            int(len(df)),
        )
        if best_score is None or table_score > best_score:
            best_index = idx
            best_score = table_score
    return best_index


def _is_dimension_like_join_candidate(current_df: pd.DataFrame, table_df: pd.DataFrame) -> bool:
    candidates = _shared_join_key_candidates(list(current_df.columns), list(table_df.columns))
    if len(candidates) != 1:
        return False
    right_key = candidates[0][1]
    if not _rows_are_unique_for_keys(table_df, [right_key]):
        return False
    return _count_numeric_non_key_columns(table_df, [right_key]) <= 2


def _bridge_join_tables(
    tables: Sequence[Dict[str, Any]],
    how: str = "inner",
) -> Dict[str, Any]:
    if not tables:
        raise ValueError("No tables provided for bridge join.")

    seed_index = _choose_bridge_join_seed_index(tables)
    seed_table = tables[seed_index]
    merged_df = seed_table["df"].copy()
    sources = [str(seed_table.get("file_name") or seed_table.get("sheet_name") or f"table_{seed_index + 1}")]
    remaining = [table for idx, table in enumerate(tables) if idx != seed_index]
    join_path: list[str] = []

    while remaining:
        dimension_candidates = [
            table for table in remaining
            if isinstance(table.get("df"), pd.DataFrame)
            and _is_dimension_like_join_candidate(merged_df, table["df"])
        ]
        candidate_pool = dimension_candidates or remaining

        best: tuple[tuple[int, int, int], Dict[str, Any], list[tuple[str, str, str, int]]] | None = None
        for table in candidate_pool:
            table_df = table.get("df")
            if not isinstance(table_df, pd.DataFrame):
                continue
            join_candidates = _shared_join_key_candidates(list(merged_df.columns), list(table_df.columns))
            if not join_candidates:
                continue
            join_keys = join_candidates[:3]
            right_keys = [right for _left, right, _norm, _score in join_keys]
            unique_on_join_keys = _rows_are_unique_for_keys(table_df, right_keys)
            candidate_score = (
                1 if unique_on_join_keys else 0,
                len(join_keys),
                sum(score for *_rest, score in join_keys),
                -_count_numeric_non_key_columns(table_df, right_keys),
            )
            if best is None or candidate_score > best[0]:
                best = (candidate_score, table, join_keys)

        if best is None:
            unresolved = [
                str(table.get("file_name") or table.get("sheet_name") or "table")
                for table in remaining
            ]
            raise ValueError(
                f"Unable to bridge-join remaining tables: {', '.join(unresolved)}"
            )

        _, table, join_keys = best
        table_df = table["df"]
        left_keys = [left for left, _right, _norm, _score in join_keys]
        right_keys = [right for _left, right, _norm, _score in join_keys]
        merged_df = _merge_current_with_table(
            merged_df,
            table_df,
            left_keys=left_keys,
            right_keys=right_keys,
            how=how,
            suffix_index=len(sources) + 1,
        )
        source_name = str(table.get("file_name") or table.get("sheet_name") or f"table_{len(sources) + 1}")
        sources.append(source_name)
        join_path.append(f"{source_name} on {', '.join(left_keys)}")
        remaining.remove(table)

    detail_data = [merged_df.columns.tolist()] + merged_df.fillna("").values.tolist()
    return {
        "output_df": merged_df,
        "detail_data": detail_data,
        "sources": sources,
        "join_path": join_path,
    }


def concat_tables_with_same_headers(
    tables: Sequence[Any],
    sort_by: Sequence[str] | None = None,
    ignore_index: bool = True,
) -> Dict[str, Any]:
    """Vertically combine tables that share the same normalized header set.

    Accepts any of the following per-table formats:
    - dict with ``df`` key (from ``load_all_tables()``)
    - dict with ``rows``/``header`` keys (from ``read_table_multi()``)
    - bare ``pd.DataFrame``
    """
    if not tables:
        raise ValueError("No tables provided for concatenation.")

    def _normalise_entry(entry: Any, index: int) -> Dict[str, Any]:
        """Convert any supported format into ``{"df": ..., "header": [...]}``."""
        if isinstance(entry, pd.DataFrame):
            return {"df": entry, "header": list(entry.columns)}
        if isinstance(entry, dict):
            # read_table_multi() output: has "rows" and "header"
            if "rows" in entry and "header" in entry and "df" not in entry:
                df = pd.DataFrame(entry["rows"], columns=entry["header"])
                return {"df": df, "header": list(entry["header"]), **{k: v for k, v in entry.items() if k not in ("rows", "header")}}
            # load_all_tables() output: has "df"
            if "df" in entry:
                return entry
        raise TypeError(
            f"Table {index}: unsupported format {type(entry).__name__}. "
            "Pass a DataFrame, a read_table_multi() result, or a load_all_tables() entry."
        )

    normalised = [_normalise_entry(t, i + 1) for i, t in enumerate(tables)]

    def _resolve_header(table: Dict[str, Any]) -> list[str]:
        header = list(table.get("header", []) or [])
        if header:
            return header
        df = table.get("df")
        if isinstance(df, pd.DataFrame):
            return [str(col) for col in df.columns]
        return []

    first_header_actual = _resolve_header(normalised[0])
    first_header = [_normalize_header_name(col) for col in first_header_actual]
    if not first_header:
        raise ValueError("Tables must include headers for concatenation.")

    dataframes: list[pd.DataFrame] = []
    sources: list[str] = []
    for index, table in enumerate(normalised, start=1):
        header = _resolve_header(table)
        normalized_header = [_normalize_header_name(col) for col in header]
        if normalized_header != first_header:
            raise ValueError(
                f"Table {index} does not share the same schema. "
                f"expected={first_header_actual}, actual={header}"
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


def merge_tables_on_keys(
    tables: Sequence[Dict[str, Any]],
    key_headers: Sequence[str],
    how: str = "inner",
    dedupe_keep: str = "first",
) -> Dict[str, Any]:
    """Horizontally merge selected tables on a verified composite key."""
    if not tables:
        raise ValueError("No tables provided for merge.")
    if len(key_headers) < 2:
        raise ValueError("At least two key headers are required for a composite-key merge.")

    merged_df: pd.DataFrame | None = None
    actual_key_names: list[str] | None = None
    merge_sources: list[str] = []

    for index, table in enumerate(tables, start=1):
        df = table.get("df")
        if not isinstance(df, pd.DataFrame):
            raise ValueError("Each table must include a pandas DataFrame under `df`.")
        table_key_names = [_resolve_column_name(df.columns, key_header) for key_header in key_headers]
        table_df = df.copy()
        for key_name in table_key_names:
            table_df[key_name] = table_df[key_name].map(_normalize_cell_text)
        non_empty_mask = pd.Series(True, index=table_df.index)
        for key_name in table_key_names:
            non_empty_mask &= table_df[key_name] != ""
        table_df = table_df[non_empty_mask]
        table_df = table_df.drop_duplicates(subset=table_key_names, keep=dedupe_keep)
        non_key_cols = [col for col in table_df.columns if col not in table_key_names]
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
            actual_key_names = list(table_key_names)
        else:
            merged_df = merged_df.merge(table_df, left_on=actual_key_names, right_on=table_key_names, how=how)
            for left_key, right_key in zip(actual_key_names, table_key_names):
                if right_key != left_key and right_key in merged_df.columns:
                    merged_df = merged_df.drop(columns=[right_key])
        merge_sources.append(str(table.get("file_name") or table.get("sheet_name") or f"table_{index}"))

    if merged_df is None or actual_key_names is None:
        raise ValueError("Merge produced no result.")

    detail_data = [merged_df.columns.tolist()] + merged_df.fillna("").values.tolist()
    return {
        "key_columns": actual_key_names,
        "merged_df": merged_df,
        "output_df": merged_df,
        "detail_data": detail_data,
        "row_count": int(len(merged_df)),
        "column_count": int(len(merged_df.columns)),
        "sources": merge_sources,
    }


def build_relational_join_enrichment_report(
    world: SpreadsheetWorld,
    range_ref: str = "A1:Z200000",
    key_header: str | None = None,
    how: str = "inner",
) -> Dict[str, Any]:
    """Join multiple related tables on a shared key and return one enriched table.

    This is a generic relational family helper for situations where multiple
    files/sheets describe the same entities from different perspectives and the
    desired output is a single denormalized table.
    """
    tables = load_all_tables(
        world,
        range_ref=range_ref,
        require_primary_key=False,
        stop_at_note_row=True,
    )
    if len(tables) < 2:
        raise ValueError("At least two related tables are required for relational join enrichment.")

    if key_header is not None:
        merge_result = merge_tables_on_key(
            tables,
            key_header=key_header,
            how=how,
        )
    else:
        try:
            actual_key_header = infer_common_key(tables)
        except ValueError:
            merge_result = _bridge_join_tables(tables, how=how)
        else:
            merge_result = merge_tables_on_key(
                tables,
                key_header=actual_key_header,
                how=how,
            )

    output_df = merge_result["output_df"].copy()
    detail_data = [output_df.columns.tolist()] + output_df.fillna("").values.tolist()
    key_summary = merge_result.get("key_column") or ", ".join(merge_result.get("join_path", [])) or "bridge_join"
    return {
        "output_df": output_df,
        "detail_data": detail_data,
        "summary": {
            "Key Column": key_summary,
            "Source Tables": ", ".join(merge_result["sources"]),
            "Rows Used": int(len(output_df)),
        },
        "metadata": {
            "key_column": merge_result.get("key_column"),
            "join_path": merge_result.get("join_path", []),
            "how": how,
            "sources": merge_result["sources"],
        },
    }


def build_multi_key_relational_join_report(
    world: SpreadsheetWorld,
    range_ref: str = "A1:Z200000",
    key_headers: Sequence[str] | None = None,
    how: str = "inner",
) -> Dict[str, Any]:
    """Join multiple related tables on a composite key and return one enriched table."""
    tables = load_all_tables(
        world,
        range_ref=range_ref,
        require_primary_key=False,
        stop_at_note_row=True,
    )
    if len(tables) < 2:
        raise ValueError("At least two related tables are required for multi-key relational join.")

    actual_key_headers = list(key_headers) if key_headers else infer_common_keys(tables, max_keys=2)
    merge_result = merge_tables_on_keys(
        tables,
        key_headers=actual_key_headers,
        how=how,
    )
    output_df = merge_result["output_df"].copy()
    detail_data = [output_df.columns.tolist()] + output_df.fillna("").values.tolist()
    return {
        "output_df": output_df,
        "detail_data": detail_data,
        "summary": {
            "Key Columns": ", ".join(merge_result["key_columns"]),
            "Source Tables": ", ".join(merge_result["sources"]),
            "Rows Used": int(len(output_df)),
        },
        "metadata": {
            "key_columns": merge_result["key_columns"],
            "how": how,
            "sources": merge_result["sources"],
        },
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
    """Describe identifier-format inconsistencies in natural language."""
    tables = load_all_tables(
        world,
        range_ref=range_ref,
        require_primary_key=False,
        stop_at_note_row=True,
    )
    candidate_columns: list[tuple[str, str, list[str]]] = []
    for table in tables:
        df = table["df"].copy()
        for column_name in map(str, df.columns):
            if not _is_identifier_like_column(df[column_name], column_name):
                continue
            raw_values = [_normalize_cell_text(v) for v in df[column_name].tolist()]
            raw_values = [value for value in raw_values if value]
            if len(raw_values) < 2:
                continue
            candidate_columns.append((table["file_name"], column_name, raw_values))

    if not candidate_columns:
        return {
            "answer": "No identifier-like columns with obvious format inconsistencies were found.",
            "variants": {},
        }

    for _file_name, column_name, raw_values in candidate_columns:
        variant_map: dict[str, set[str]] = {}
        for value in raw_values:
            canonical = re.sub(r"[^A-Za-z0-9]+", "", value).upper()
            variant_map.setdefault(canonical, set()).add(value)

        duplicate_variant_groups = {
            canonical: sorted(variants)
            for canonical, variants in variant_map.items()
            if len(variants) > 1
        }
        if duplicate_variant_groups:
            group_parts: list[str] = []
            question_parts: list[str] = []
            for canonical, variants in sorted(
                duplicate_variant_groups.items(),
                key=lambda item: (-len(item[1]), item[0]),
            )[:5]:
                display_variants = variants[:4]
                sample = ", ".join(f"`{variant}`" for variant in display_variants)
                group_parts.append(f"{canonical}: {sample}")
                if not question_parts:
                    question_parts = display_variants
            question_sample = ", ".join(f"`{variant}`" for variant in question_parts)
            answer = (
                f"The `{column_name}` column contains inconsistent variants for the same identifier families: "
                f"{'; '.join(group_parts)}. "
                f"Should `{column_name}` be standardized to one format such as {question_sample}?"
            )
            return {
                "answer": answer,
                "variants": duplicate_variant_groups,
            }

    for _file_name, column_name, raw_values in candidate_columns:
        code_like_values = [value for value in raw_values if re.search(r"[A-Za-z]\s*\d", value)]
        has_spaced = any(" " in value for value in code_like_values)
        has_compact = any(" " not in value for value in code_like_values)
        has_lower = any(any(ch.islower() for ch in value) for value in code_like_values)
        has_upper = any(any(ch.isupper() for ch in value) for value in code_like_values)
        if len(code_like_values) >= 2 and ((has_spaced and has_compact) or (has_lower and has_upper)):
            sample_values: list[str] = []
            for value in code_like_values:
                if value not in sample_values:
                    sample_values.append(value)
                if len(sample_values) >= 3:
                    break
            sample = ", ".join(f"`{value}`" for value in sample_values)
            preferred = min(sample_values, key=lambda value: (len(value), value.lower()))
            answer = (
                f"The `{column_name}` column uses inconsistent identifier formatting, for example {sample}. "
                f"Should `{column_name}` be standardized as `{preferred}`?"
            )
            return {
                "answer": answer,
                "variants": {
                    re.sub(r"[^A-Za-z0-9]+", "", value).upper(): [value]
                    for value in sample_values
                },
            }

    return {
        "answer": "No obvious identifier-format inconsistencies were found.",
        "variants": {},
    }


def build_relational_assignment_schedule_report(
    world: SpreadsheetWorld,
    range_ref: str = "A1:Z200",
) -> Dict[str, Any]:
    """Build an assignment-aware schedule by joining assigned entities to resource/session slots."""
    tables = load_all_tables(
        world,
        range_ref=range_ref,
        require_primary_key=False,
        stop_at_note_row=True,
    )
    if len(tables) < 2:
        raise ValueError("Assignment schedule workflow expects at least two related tables.")

    assignment_prefix_markers = (
        "assigned tutor",
        "assigned professor",
        "assigned teacher",
        "assigned advisor",
        "assigned mentor",
        "assigned supervisor",
        "assigned room",
        "assigned seat",
        "assigned lab",
        "assigned group",
        "assigned session",
    )
    resource_markers = (
        "tutor",
        "professor",
        "teacher",
        "advisor",
        "mentor",
        "supervisor",
        "room",
        "seat",
        "lab",
        "group",
        "session",
    )
    schedule_markers = (
        "day",
        "date",
        "time slot",
        "time",
        "room",
        "location",
        "building",
        "seat",
        "lab",
        "session",
        "group",
    )

    def _find_assignment_column(columns: Sequence[Any]) -> str | None:
        for column in columns:
            normalized = _normalize_header_name(column)
            if any(marker in normalized for marker in assignment_prefix_markers):
                return str(column)
        return None

    def _canonical_resource_key(column_name: str) -> str:
        normalized = _normalize_header_name(column_name)
        normalized = normalized.replace("assigned", "").strip()
        for marker in resource_markers:
            if marker in normalized:
                return marker
        return normalized

    def _find_entity_column(columns: Sequence[Any], assigned_col: str) -> str | None:
        preferred = (
            "student name",
            "name",
            "student",
            "candidate",
            "participant",
            "attendee",
            "entity name",
            "student id",
            "person id",
            "entity id",
        )
        for candidate in preferred:
            for column in columns:
                if str(column) == assigned_col:
                    continue
                normalized = _normalize_header_name(column)
                if candidate == normalized or candidate in normalized:
                    return str(column)
        for column in columns:
            if str(column) == assigned_col:
                continue
            normalized = _normalize_header_name(column)
            if not any(marker in normalized for marker in schedule_markers):
                return str(column)
        return None

    assignment_table = None
    assignment_col = None
    entity_col = None
    canonical_resource = None
    for table in tables:
        candidate_assigned = _find_assignment_column(table["df"].columns)
        if not candidate_assigned:
            continue
        candidate_entity = _find_entity_column(table["df"].columns, candidate_assigned)
        if not candidate_entity:
            continue
        assignment_table = table
        assignment_col = candidate_assigned
        entity_col = candidate_entity
        canonical_resource = _canonical_resource_key(candidate_assigned)
        break

    if assignment_table is None or assignment_col is None or entity_col is None or not canonical_resource:
        raise ValueError("Could not identify an assignment table with assigned-resource and entity columns.")

    schedule_table = None
    resource_col = None
    schedule_cols: list[str] = []
    for table in tables:
        if table is assignment_table:
            continue
        columns = [str(column) for column in table["df"].columns]
        candidate_resource = None
        for column in columns:
            normalized = _normalize_header_name(column)
            if canonical_resource in normalized:
                candidate_resource = column
                break
        if not candidate_resource:
            continue
        candidate_schedule_cols = [
            column for column in columns
            if column != candidate_resource
            and any(marker in _normalize_header_name(column) for marker in schedule_markers)
        ]
        if not candidate_schedule_cols and len(columns) <= 1:
            continue
        schedule_table = table
        resource_col = candidate_resource
        schedule_cols = candidate_schedule_cols
        break

    if schedule_table is None or resource_col is None:
        raise ValueError("Could not identify a scheduling/resource table that matches the assignment table.")

    assignment_df = assignment_table["df"].copy()
    schedule_df = schedule_table["df"].copy()

    assignment_df[entity_col] = assignment_df[entity_col].map(_normalize_cell_text)
    assignment_df[assignment_col] = assignment_df[assignment_col].map(_normalize_cell_text)
    schedule_df[resource_col] = schedule_df[resource_col].map(_normalize_cell_text)
    for column in schedule_cols:
        schedule_df[column] = schedule_df[column].map(_normalize_cell_text)

    assignment_df = assignment_df[
        assignment_df[entity_col].astype(bool)
        & assignment_df[assignment_col].astype(bool)
    ].copy()
    schedule_df = schedule_df[schedule_df[resource_col].astype(bool)].copy()

    output_df = _build_grouped_assignment_join(
        assignment_df=assignment_df,
        assignment_col=assignment_col,
        entity_col=entity_col,
        schedule_df=schedule_df,
        resource_col=resource_col,
        schedule_cols=schedule_cols,
    )

    detail_data = [output_df.columns.tolist()] + output_df.fillna("").values.tolist()
    return {
        "output_df": output_df,
        "detail_data": detail_data,
        "row_count": int(len(output_df)),
        "entity_count": int(assignment_df[entity_col].nunique()),
        "resource_count": int(output_df[resource_col].nunique()),
        "metadata": {
            "entity_column": entity_col,
            "assignment_column": assignment_col,
            "resource_column": resource_col,
        },
    }

def build_capacity_constrained_allocation_report(
    world: SpreadsheetWorld,
    range_ref: str = "A1:Z200000",
) -> Dict[str, Any]:
    """Assign entities to resources with capacities using a deterministic greedy policy."""
    tables = load_all_tables(
        world,
        range_ref=range_ref,
        require_primary_key=False,
        stop_at_note_row=True,
    )
    if len(tables) < 2:
        raise ValueError("Capacity-constrained allocation requires at least two tables.")

    capacity_markers = (
        "capacity",
        "capacities",
        "available seats",
        "seat count",
        "seat limit",
        "slot count",
        "slots",
        "max students",
        "max participants",
        "max capacity",
    )
    resource_markers = (
        "resource",
        "room",
        "group",
        "section",
        "lab",
        "seat",
        "session",
        "professor",
        "advisor",
        "mentor",
        "supervisor",
    )
    entity_markers = (
        "student",
        "candidate",
        "participant",
        "attendee",
        "applicant",
        "member",
        "name",
        "id",
    )
    demand_markers = (
        "demand",
        "quantity",
        "required seats",
        "required slots",
        "students",
        "participants",
        "attendees",
    )

    def _find_capacity_column(columns: Sequence[Any]) -> str | None:
        candidates: list[tuple[int, str]] = []
        for column in columns:
            normalized = _normalize_header_name(column)
            score = 0
            if any(marker in normalized for marker in capacity_markers):
                score += 100
            if any(marker in normalized for marker in ("capacity", "slot", "seat")):
                score += 40
            if score > 0:
                candidates.append((score, str(column)))
        if not candidates:
            return None
        candidates.sort(key=lambda item: (-item[0], item[1]))
        return candidates[0][1]

    def _find_resource_column(columns: Sequence[Any], capacity_col: str) -> str | None:
        candidates: list[tuple[int, str]] = []
        for column in columns:
            column_str = str(column)
            if column_str == capacity_col:
                continue
            normalized = _normalize_header_name(column)
            score = 0
            if any(marker in normalized for marker in resource_markers):
                score += 80
            if any(marker in normalized for marker in ("id", "name", "number", "code")):
                score += 15
            if score > 0:
                candidates.append((score, column_str))
        if not candidates:
            fallback = [str(column) for column in columns if str(column) != capacity_col]
            return fallback[0] if fallback else None
        candidates.sort(key=lambda item: (-item[0], item[1]))
        return candidates[0][1]

    def _find_entity_column(columns: Sequence[Any], forbidden: Sequence[str]) -> str | None:
        forbidden_set = {str(col) for col in forbidden}
        candidates: list[tuple[int, str]] = []
        for column in columns:
            column_str = str(column)
            if column_str in forbidden_set:
                continue
            normalized = _normalize_header_name(column)
            score = 0
            if any(marker in normalized for marker in entity_markers):
                score += 80
            if any(marker in normalized for marker in ("student", "candidate", "participant", "applicant")):
                score += 30
            if score > 0:
                candidates.append((score, column_str))
        if not candidates:
            fallback = [str(column) for column in columns if str(column) not in forbidden_set]
            return fallback[0] if fallback else None
        candidates.sort(key=lambda item: (-item[0], item[1]))
        return candidates[0][1]

    def _find_demand_column(columns: Sequence[Any], forbidden: Sequence[str]) -> str | None:
        forbidden_set = {str(col) for col in forbidden}
        candidates: list[tuple[int, str]] = []
        for column in columns:
            column_str = str(column)
            if column_str in forbidden_set:
                continue
            normalized = _normalize_header_name(column)
            score = 0
            if any(marker in normalized for marker in demand_markers):
                score += 80
            if score > 0:
                candidates.append((score, column_str))
        if not candidates:
            return None
        candidates.sort(key=lambda item: (-item[0], item[1]))
        return candidates[0][1]

    resource_table = None
    resource_col = None
    capacity_col = None
    for table in tables:
        candidate_capacity = _find_capacity_column(table["df"].columns)
        if not candidate_capacity:
            continue
        candidate_resource = _find_resource_column(table["df"].columns, candidate_capacity)
        if not candidate_resource:
            continue
        resource_table = table
        resource_col = candidate_resource
        capacity_col = candidate_capacity
        break

    if resource_table is None or resource_col is None or capacity_col is None:
        raise ValueError("Could not identify a resource table with a capacity column.")

    entity_table = None
    entity_col = None
    demand_col = None
    for table in tables:
        if table is resource_table:
            continue
        candidate_entity = _find_entity_column(table["df"].columns, [])
        if not candidate_entity:
            continue
        candidate_demand = _find_demand_column(table["df"].columns, [candidate_entity])
        entity_table = table
        entity_col = candidate_entity
        demand_col = candidate_demand
        break

    if entity_table is None or entity_col is None:
        raise ValueError("Could not identify an entity table to allocate.")

    resource_df = resource_table["df"].copy()
    entity_df = entity_table["df"].copy()
    resource_df[resource_col] = resource_df[resource_col].map(_normalize_cell_text)
    resource_df[capacity_col] = pd.to_numeric(resource_df[capacity_col], errors="coerce").fillna(0)
    resource_df = resource_df[(resource_df[resource_col] != "") & (resource_df[capacity_col] > 0)].copy()
    if resource_df.empty:
        raise ValueError("No resources with positive capacity were found.")

    entity_df[entity_col] = entity_df[entity_col].map(_normalize_cell_text)
    entity_df = entity_df[entity_df[entity_col] != ""].copy()
    if entity_df.empty:
        raise ValueError("No allocatable entities were found.")

    if demand_col and demand_col in entity_df.columns:
        entity_df[demand_col] = pd.to_numeric(entity_df[demand_col], errors="coerce").fillna(1)
    else:
        demand_col = None

    remaining = [int(max(0, round(float(value)))) for value in resource_df[capacity_col].tolist()]
    resource_records = resource_df.to_dict("records")
    resource_metadata_cols = [col for col in resource_df.columns if col != capacity_col]
    resource_output_cols = []
    rename_map: Dict[str, str] = {}
    for col in resource_metadata_cols:
        col_str = str(col)
        if col_str in entity_df.columns:
            rename_map[col_str] = f"{col_str} (Resource)"
            resource_output_cols.append(rename_map[col_str])
        else:
            resource_output_cols.append(col_str)

    output_rows: list[dict[str, Any]] = []
    assigned_count = 0
    unassigned_count = 0
    used_resource_values: set[str] = set()

    for _, row in entity_df.iterrows():
        demand_value = 1
        if demand_col:
            demand_value = int(max(1, round(float(row[demand_col]))))
        chosen_idx = None
        for idx, remaining_capacity in enumerate(remaining):
            if remaining_capacity >= demand_value:
                chosen_idx = idx
                break

        output_row = {str(column): row[column] for column in entity_df.columns}
        if chosen_idx is None:
            for col in resource_output_cols:
                output_row[col] = ""
            output_row["Allocation Status"] = "Unassigned"
            output_row["Allocated Quantity"] = demand_value
            unassigned_count += 1
        else:
            remaining[chosen_idx] -= demand_value
            resource_record = resource_records[chosen_idx]
            for col in resource_metadata_cols:
                output_col = rename_map.get(str(col), str(col))
                output_row[output_col] = resource_record[col]
            output_row["Allocation Status"] = "Assigned"
            output_row["Allocated Quantity"] = demand_value
            assigned_count += 1
            used_resource_values.add(_normalize_cell_text(resource_record[resource_col]))
        output_rows.append(output_row)

    output_df = pd.DataFrame(output_rows)
    detail_data = [output_df.columns.tolist()] + output_df.fillna("").values.tolist()
    return {
        "output_df": output_df,
        "detail_data": detail_data,
        "summary": {
            "Assigned Entities": int(assigned_count),
            "Unassigned Entities": int(unassigned_count),
            "Resources Used": int(len({value for value in used_resource_values if value})),
        },
        "metadata": {
            "entity_column": entity_col,
            "resource_column": resource_col,
            "capacity_column": capacity_col,
            "demand_column": demand_col or "",
        },
    }


def compute_ratio_column(
    df: pd.DataFrame,
    numerator_col: str,
    denominator_col: str,
    output_col: str = "ratio",
) -> Dict[str, Any]:
    """Add a ratio column: output_col = numerator_col / denominator_col.

    Both source columns are coerced to numeric. Division-by-zero rows become NaN.
    Does not load data, write output, or format — pure DataFrame transformation.
    """
    actual_num = _resolve_column_name(df.columns, numerator_col)
    actual_den = _resolve_column_name(df.columns, denominator_col)
    output_df = df.copy()
    num = pd.to_numeric(output_df[actual_num], errors="coerce")
    den = pd.to_numeric(output_df[actual_den], errors="coerce").replace(0, np.nan)
    output_df[output_col] = (num / den).round(4)
    return _tabular_result(
        output_df,
        metadata={
            "helper": "compute_ratio_column",
            "numerator_col": actual_num,
            "denominator_col": actual_den,
            "output_col": output_col,
            "formula": f"{actual_num} / {actual_den}",
        },
    )


def compute_weighted_score(
    df: pd.DataFrame,
    score_cols: List[str],
    weights: List[float] | None = None,
    output_col: str = "score",
) -> Dict[str, Any]:
    """Add a weighted composite score column.

    Weights are normalized to sum to 1. Missing values are treated as 0.
    Does not load data, write output, or format — pure DataFrame transformation.
    """
    output_df = df.copy()
    actual_score_cols = [_resolve_column_name(output_df.columns, col) for col in score_cols]
    if not weights:
        weights = [1.0 / len(actual_score_cols)] * len(actual_score_cols)
    total = sum(weights) or 1.0
    norm = [w / total for w in weights]
    score = sum(
        pd.to_numeric(output_df[col], errors="coerce").fillna(0.0) * w
        for col, w in zip(actual_score_cols, norm)
    )
    output_df[output_col] = score.round(4)
    return _tabular_result(
        output_df,
        metadata={
            "helper": "compute_weighted_score",
            "score_cols": actual_score_cols,
            "weights": norm,
            "output_col": output_col,
        },
    )


def compute_percentage_share(
    df: pd.DataFrame,
    value_col: str,
    output_col: str = "share_pct",
    group_col: str | None = None,
) -> Dict[str, Any]:
    """Add a percentage share column (value / total * 100).

    If group_col is given, share is computed within each group.
    Does not load data, write output, or format — pure DataFrame transformation.
    """
    output_df = df.copy()
    actual_value_col = _resolve_column_name(output_df.columns, value_col)
    actual_group_col = _resolve_column_name(output_df.columns, group_col) if group_col else None
    values = pd.to_numeric(output_df[actual_value_col], errors="coerce").fillna(0.0)
    if actual_group_col:
        totals = values.groupby(output_df[actual_group_col]).transform("sum").replace(0, np.nan)
    else:
        totals = values.sum() or np.nan
    output_df[output_col] = (values / totals * 100).round(2)
    return _tabular_result(
        output_df,
        metadata={
            "helper": "compute_percentage_share",
            "value_col": actual_value_col,
            "group_col": actual_group_col,
            "output_col": output_col,
        },
    )


def add_rank_column(
    df: pd.DataFrame,
    sort_col: str,
    ascending: bool = False,
    rank_col: str = "rank",
) -> Dict[str, Any]:
    """Add a 1-based integer rank column and sort the DataFrame by sort_col.

    Does not load data, write output, or format — pure DataFrame transformation.
    """
    actual_sort_col = _resolve_column_name(df.columns, sort_col)
    output_df = df.copy()
    numeric_vals = pd.to_numeric(output_df[actual_sort_col], errors="coerce")
    output_df[rank_col] = numeric_vals.rank(
        method="min", ascending=ascending, na_option="bottom"
    ).astype("Int64")
    output_df = output_df.sort_values(actual_sort_col, ascending=ascending).reset_index(drop=True)
    row_numbers = [idx + 2 for idx in range(len(output_df))]
    return _tabular_result(
        output_df,
        metadata={
            "helper": "add_rank_column",
            "sort_col": actual_sort_col,
            "ascending": ascending,
            "rank_col": rank_col,
            "row_number_offset": 2,
            "row_number_contract": "Excel row numbers assume output_df is written at A1 with a header row.",
        },
        output_row_numbers=row_numbers,
    )


def summarize_numeric_column(
    df: pd.DataFrame,
    value_col: str,
    round_digits: int = 2,
    summary_labels: Dict[str, str] | None = None,
) -> Dict[str, Any]:
    """Summarize a numeric column and compute explicit Output row numbers for extrema highlights."""
    def _infer_value_col() -> str:
        candidate_scores: list[tuple[int, str]] = []
        for candidate in df.columns:
            numeric_series = pd.to_numeric(df[candidate], errors="coerce")
            non_null_count = int(numeric_series.notna().sum())
            if non_null_count <= 0:
                continue
            candidate_scores.append((non_null_count, str(candidate)))
        if not candidate_scores:
            raise ValueError("Could not infer a numeric column for summary.")
        candidate_scores.sort(key=lambda item: (-item[0], item[1]))
        return candidate_scores[0][1]

    requested_value_col = str(value_col or "").strip()
    if requested_value_col in {"", "...", "value", "amount", "metric"}:
        actual_value_col = _infer_value_col()
    else:
        try:
            actual_value_col = _resolve_column_name(df.columns, requested_value_col)
        except ValueError:
            actual_value_col = _infer_value_col()
    # Reset index so output_row_numbers are always contiguous 0-based,
    # matching the row positions written by write_dataframe_to_sheet.
    df = df.reset_index(drop=True)
    numeric_series = pd.to_numeric(df[actual_value_col], errors="coerce")
    if numeric_series.dropna().empty:
        raise ValueError(f"Column `{actual_value_col}` has no numeric values.")

    total_value = round(float(numeric_series.sum()), round_digits)
    average_value = round(float(numeric_series.mean()), round_digits)
    max_raw = float(numeric_series.max())
    min_raw = float(numeric_series.min())
    max_value = round(max_raw, round_digits)
    min_value = round(min_raw, round_digits)
    max_indices = numeric_series[numeric_series == max_raw].index.tolist()
    min_indices = numeric_series[numeric_series == min_raw].index.tolist()
    row_number_offset = 2
    max_output_row_numbers = [int(idx) + row_number_offset for idx in max_indices]
    min_output_row_numbers = [int(idx) + row_number_offset for idx in min_indices]

    labels = {
        "total": "Total",
        "average": "Average",
        "max": "Max",
        "min": "Min",
    }
    if summary_labels:
        labels.update(summary_labels)

    summary = {
        labels["total"]: total_value,
        labels["average"]: average_value,
        labels["max"]: max_value,
    }
    return {
        "output_df": df,
        "detail_data": _detail_data_from_df(df),
        "value_col": actual_value_col,
        "total": total_value,
        "average": average_value,
        "min_value": min_value,
        "max_value": max_value,
        "max_indices": max_indices,
        "min_indices": min_indices,
        "output_row_numbers": max_output_row_numbers,
        "max_output_row_numbers": max_output_row_numbers,
        "min_output_row_numbers": min_output_row_numbers,
        "row_number_offset": row_number_offset,
        "stats": {
            "total": total_value,
            "average": average_value,
            "min": min_value,
            "max": max_value,
        },
        "highlight_rows": {
            "max": max_output_row_numbers,
            "min": min_output_row_numbers,
        },
        "metadata": {
            "helper": "summarize_numeric_column",
            "value_col": actual_value_col,
            "row_number_offset": row_number_offset,
            "row_number_contract": "Excel row numbers assume output_df is written at A1 with a header row.",
        },
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

    first_period_cell = _find_first_period_cell(raw_rows, is_period_value=_is_year_like)
    if first_period_cell is None:
        raise ValueError("Could not identify the first year row and the preceding region header row.")
    first_year_row_idx, year_col_idx = first_period_cell
    if first_year_row_idx == 0:
        raise ValueError("Could not identify the first year row and the preceding region header row.")

    header_row = raw_rows[first_year_row_idx - 1]
    region_columns = _select_contiguous_labeled_columns(
        header_row,
        start_col_idx=year_col_idx + 1,
        stop_markers=("in %",),
    )

    if not region_columns:
        raise ValueError("No region columns found in the row above the first year row.")

    records = _extract_period_records(
        raw_rows[first_year_row_idx:],
        period_col_idx=year_col_idx,
        labeled_columns=region_columns,
        is_period_value=_is_year_like,
        period_transform=lambda value: int(_normalize_cell_text(value)),
        period_key="Year",
    )
    for record in records:
        for _col_idx, region_name in region_columns:
            record[region_name] = pd.to_numeric(pd.Series([record[region_name]]), errors="coerce").iloc[0]

    if not records:
        raise ValueError("No yearly records were parsed from the region table.")

    wide_df = pd.DataFrame(records)
    chart_df = wide_df[(wide_df["Year"] >= start_year) & (wide_df["Year"] <= end_year)].reset_index(drop=True)
    if chart_df.empty:
        raise ValueError(f"No rows found for years {start_year}-{end_year}.")

    actual_years = sorted(int(value) for value in chart_df["Year"].dropna().tolist())
    actual_start_year = actual_years[0]
    actual_end_year = actual_years[-1]

    result_rows: list[dict[str, Any]] = []
    avg_col = f"Avg Penetration ({actual_start_year}-{actual_end_year})"
    growth_col = f"Growth ({actual_start_year}-{actual_end_year})"
    for _, region_name in region_columns:
        series = pd.to_numeric(chart_df[region_name], errors="coerce")
        if series.dropna().empty:
            continue
        start_value = float(series.iloc[0])
        end_value = float(series.iloc[-1])
        if start_value != 0:
            growth_value = round(((end_value - start_value) / start_value) * 100.0, 2)
        else:
            growth_value = round(end_value - start_value, 2)
        result_rows.append(
            {
                "Region": region_name,
                avg_col: round(float(series.mean()), 2),
                growth_col: growth_value,
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
        "fastest_growth_region": ", ".join(fastest_regions),
        "growth_column": growth_col,
        "average_column": avg_col,
        "fastest_growth_rows": fastest_growth_rows,
        "start_year": actual_start_year,
        "end_year": actual_end_year,
        "used_years": actual_years,
    }


def build_group_summary(
    df: pd.DataFrame,
    group_cols: Sequence[str],
    aggregations: Dict[str, tuple[str, str] | str],
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

    aggregate_label_prefixes = {
        "mean": "Average",
        "average": "Average",
        "avg": "Average",
        "sum": "Total",
        "total": "Total",
        "count": "Count of",
        "median": "Median",
        "min": "Minimum",
        "minimum": "Minimum",
        "max": "Maximum",
        "maximum": "Maximum",
    }
    named_aggs: Dict[str, tuple[str, str]] = {}
    for output_name, spec in aggregations.items():
        if isinstance(spec, str):
            source_col = str(output_name)
            agg_name = spec
            prefix = aggregate_label_prefixes.get(agg_name.strip().lower(), agg_name.title())
            output_name = f"{prefix} {source_col}"
        else:
            source_col, agg_name = spec
        named_aggs[str(output_name)] = (_resolve_column_name(df.columns, source_col), agg_name)

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
        "metadata": {
            "group_cols": actual_group_cols,
            "aggregations": named_aggs,
            "sort_by": sort_by or [],
        },
    }


def build_grouped_aggregation_ranking_report(
    world: SpreadsheetWorld,
    file_path: str | None = None,
    sheet_name: str | None = None,
    range_ref: str = "A1:Z200000",
    group_cols: Sequence[str] | str | None = None,
    value_col: str | None = None,
    aggregate: str = "mean",
    top_n: int | None = None,
    sort_desc: bool = True,
    round_digits: int = 4,
) -> Dict[str, Any]:
    """Build a grouped aggregation report from one or more tabular sources.

    This helper is intentionally abstract: it supports typical grouped report
    patterns such as average score by course, total spending by category, or
    count of records by department. When columns are not explicitly supplied it
    attempts a deterministic inference of the most plausible grouping and value
    columns from the available tables.
    """

    def _normalize_group_cols(value: Sequence[str] | str | None) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return [str(item).strip() for item in value if str(item).strip()]

    def _is_datetime_like(series: pd.Series, column_name: str) -> bool:
        header = _normalize_header_name(column_name)
        if not any(token in header for token in ("date", "time", "year", "month", "quarter", "day")):
            return False
        text_values = [value for value in series.map(_normalize_cell_text).tolist() if value][:20]
        if not text_values:
            return False
        if not any(any(ch.isdigit() for ch in value) and any(sep in value for sep in ("-", "/", ":")) for value in text_values):
            return False
        parsed = pd.to_datetime(series, errors="coerce")
        return int(parsed.notna().sum()) >= max(2, int(len(series) * 0.6))

    def _numeric_candidate_score(frame: pd.DataFrame, column: str) -> float:
        text_header = _normalize_header_name(column)
        if any(marker in text_header for marker in ("id", "code", "index", "year", "month", "quarter", "date", "time")):
            return float("-inf")
        numeric_series = frame[column].map(_parse_numeric_text)
        non_null = int(numeric_series.notna().sum())
        if non_null <= 0:
            return float("-inf")
        score = float(non_null * 10)
        if any(marker in text_header for marker in ("score", "grade", "rating", "amount", "spending", "expense", "cost", "price", "salary", "revenue", "sales", "hours", "count", "quantity", "capacity", "utilisation", "utilization")):
            score += 40.0
        unique_count = int(numeric_series.dropna().nunique())
        if unique_count >= 3:
            score += 10.0
        return score

    def _group_candidate_score(frame: pd.DataFrame, column: str) -> float:
        text_header = _normalize_header_name(column)
        if any(marker in text_header for marker in ("id", "code", "email", "phone", "note", "comment", "description", "address")):
            return float("-inf")
        series = frame[column]
        if _is_datetime_like(series, column):
            return float("-inf")
        text_series = series.map(_normalize_cell_text)
        non_empty = [value for value in text_series.tolist() if value]
        if len(non_empty) < 2:
            return float("-inf")
        unique_count = len(set(non_empty))
        if unique_count < 2:
            return float("-inf")
        unique_ratio = unique_count / max(len(non_empty), 1)
        score = float(len(non_empty) * 5)
        if 0.05 <= unique_ratio <= 0.6:
            score += 25.0
        elif unique_ratio < 0.85:
            score += 10.0
        if any(marker in text_header for marker in ("category", "group", "type", "department", "course", "subject", "program", "semester", "term", "class", "region", "room", "status", "level", "faculty", "professor", "instructor", "tutor")):
            score += 40.0
        return score

    def _choose_table_and_columns(tables: Sequence[Dict[str, Any]]) -> tuple[list[Dict[str, Any]], list[str], str]:
        requested_group_cols = _normalize_group_cols(group_cols)
        aggregate_name = (aggregate or "mean").strip().lower()
        best_match: tuple[float, int, list[str], str, Dict[str, Any]] | None = None

        for table in tables:
            df = table["df"].copy()
            if df.empty:
                continue
            try:
                actual_group_cols = (
                    [_resolve_column_name(df.columns, col) for col in requested_group_cols]
                    if requested_group_cols else []
                )
            except ValueError:
                continue

            if not actual_group_cols:
                scored_groups = [
                    (_group_candidate_score(df, str(column)), str(column))
                    for column in df.columns
                ]
                scored_groups = [item for item in scored_groups if item[0] != float("-inf")]
                if not scored_groups:
                    continue
                scored_groups.sort(key=lambda item: (-item[0], item[1]))
                actual_group_cols = [scored_groups[0][1]]

            if value_col:
                try:
                    actual_value_col = _resolve_column_name(df.columns, value_col)
                except ValueError:
                    continue
                value_score = _numeric_candidate_score(df, actual_value_col)
            else:
                scored_values = [
                    (_numeric_candidate_score(df, str(column)), str(column))
                    for column in df.columns
                    if str(column) not in actual_group_cols
                ]
                scored_values = [item for item in scored_values if item[0] != float("-inf")]
                if not scored_values:
                    continue
                scored_values.sort(key=lambda item: (-item[0], item[1]))
                value_score, actual_value_col = scored_values[0]

            group_score = sum(_group_candidate_score(df, column) for column in actual_group_cols)
            total_score = group_score + value_score
            if best_match is None or total_score > best_match[0]:
                best_match = (
                    total_score,
                    len(df),
                    list(actual_group_cols),
                    actual_value_col,
                    table,
                )

        if best_match is None:
            raise ValueError("Could not find a suitable grouped aggregation table and column combination.")

        _, _, actual_group_cols, actual_value_col, base_table = best_match
        base_signature = tuple(_normalize_header_name(col) for col in base_table["df"].columns.tolist())
        compatible_tables: list[Dict[str, Any]] = []
        for table in tables:
            df = table["df"].copy()
            signature = tuple(_normalize_header_name(col) for col in df.columns.tolist())
            if signature != base_signature:
                continue
            try:
                [_resolve_column_name(df.columns, col) for col in actual_group_cols]
                _resolve_column_name(df.columns, actual_value_col)
            except ValueError:
                continue
            compatible_tables.append(table)
        if not compatible_tables:
            compatible_tables = [base_table]
        return compatible_tables, actual_group_cols, actual_value_col

    requested_tables: list[Dict[str, Any]] = []
    if file_path:
        wb = get_workbook(world, file_path)
        target_sheet = sheet_name or wb.sheetnames[0]
        table = read_table_multi(
            world,
            file_path,
            target_sheet,
            range_ref,
            require_primary_key=False,
            stop_at_note_row=True,
        )
        header = table.get("header", [])
        if not header:
            raise ValueError(f"No usable table found in {os.path.basename(file_path)}.")
        requested_tables = [{
            "file_path": file_path,
            "file_name": os.path.basename(file_path),
            "sheet_name": target_sheet,
            "df": pd.DataFrame(table["rows"], columns=header),
        }]
    else:
        requested_tables = load_all_tables(
            world,
            range_ref=range_ref,
            require_primary_key=False,
            stop_at_note_row=True,
        )
    if not requested_tables:
        raise ValueError("No tables available for grouped aggregation.")

    compatible_tables, actual_group_cols, actual_value_col = _choose_table_and_columns(requested_tables)

    normalized_frames: list[pd.DataFrame] = []
    source_names: list[str] = []
    for table in compatible_tables:
        df = table["df"].copy()
        resolved_groups = [_resolve_column_name(df.columns, col) for col in actual_group_cols]
        resolved_value = _resolve_column_name(df.columns, actual_value_col)
        working = df[resolved_groups + [resolved_value]].copy()
        working[resolved_value] = working[resolved_value].map(_parse_numeric_text)
        working = working.dropna(subset=[resolved_value]).reset_index(drop=True)
        if working.empty:
            continue
        normalized_frames.append(working)
        source_names.append(table["file_name"])
    if not normalized_frames:
        raise ValueError("No valid rows remained after preparing grouped aggregation data.")

    combined = pd.concat(normalized_frames, ignore_index=True)
    aggregate_aliases = {
        "average": "mean",
        "avg": "mean",
        "mean": "mean",
        "sum": "sum",
        "total": "sum",
        "count": "count",
        "median": "median",
        "min": "min",
        "minimum": "min",
        "max": "max",
        "maximum": "max",
    }
    aggregate_func = aggregate_aliases.get((aggregate or "mean").strip().lower())
    if not aggregate_func:
        raise ValueError(f"Unsupported aggregate `{aggregate}`.")
    value_header_map = {
        "mean": f"Average {actual_value_col}",
        "sum": f"Total {actual_value_col}",
        "count": f"Count of {actual_value_col}",
        "median": f"Median {actual_value_col}",
        "min": f"Minimum {actual_value_col}",
        "max": f"Maximum {actual_value_col}",
    }
    report = build_group_summary(
        combined,
        group_cols=actual_group_cols,
        aggregations={value_header_map[aggregate_func]: (actual_value_col, aggregate_func)},
        sort_by=[value_header_map[aggregate_func]],
        ascending=not sort_desc,
        round_digits=round_digits,
    )
    output_df = report["output_df"].copy()
    if top_n is not None and int(top_n) > 0:
        output_df = output_df.head(int(top_n)).reset_index(drop=True)
    detail_data = [output_df.columns.tolist()] + output_df.fillna("").values.tolist()
    return {
        "output_df": output_df,
        "detail_data": detail_data,
        "summary": {
            "Source": ", ".join(sorted(set(source_names))),
            "Group Columns": ", ".join(actual_group_cols),
            "Value Column": actual_value_col,
            "Rows Used": int(len(combined)),
        },
        "metadata": {
            "group_cols": actual_group_cols,
            "value_col": actual_value_col,
            "aggregate": aggregate_func,
            "top_n": int(top_n) if top_n is not None else None,
        },
    }


def build_time_series_aggregation_report(
    world: SpreadsheetWorld,
    file_path: str | None = None,
    sheet_name: str | None = None,
    range_ref: str = "A1:Z200000",
    date_col: str = "Date",
    value_col: str | None = None,
    period: str = "month",
    aggregate: str = "mean",
    window_years: int | None = None,
    period_mode: str = "year_month",
    sort_desc: bool = True,
) -> Dict[str, Any]:
    """Aggregate one time series column over a requested temporal grain."""
    def _infer_date_column(frame: pd.DataFrame) -> str:
        candidate_scores: list[tuple[int, str]] = []
        for candidate in frame.columns:
            candidate_name = str(candidate)
            normalized = _normalize_header_name(candidate_name)
            score = 0
            if any(token in normalized for token in ("date", "year", "month", "quarter", "period", "time")):
                score += 10
            text_series = frame[candidate].map(_normalize_cell_text)
            year_like_count = int(text_series.str.fullmatch(r"\d{4}").fillna(False).sum())
            if year_like_count >= max(2, len(text_series) // 2):
                score += 8
            parsed_dates = pd.to_datetime(frame[candidate], errors="coerce")
            parsed_count = int(parsed_dates.notna().sum())
            score += parsed_count
            if score > 0:
                candidate_scores.append((score, candidate_name))
        if not candidate_scores:
            raise ValueError("Could not infer a date column for time-series aggregation.")
        candidate_scores.sort(key=lambda item: (-item[0], item[1]))
        return candidate_scores[0][1]

    def _infer_value_column(frame: pd.DataFrame, actual_date_col_name: str) -> str:
        candidate_scores: list[tuple[int, str]] = []
        for candidate in frame.columns:
            if str(candidate) == actual_date_col_name:
                continue
            numeric_series = frame[candidate].map(_parse_numeric_text)
            non_null_count = int(numeric_series.notna().sum())
            if non_null_count <= 0:
                continue
            candidate_scores.append((non_null_count, str(candidate)))
        if not candidate_scores:
            raise ValueError("Could not infer a numeric value column for time-series aggregation.")
        candidate_scores.sort(key=lambda item: (-item[0], item[1]))
        return candidate_scores[0][1]

    def _resolve_date_column(frame: pd.DataFrame) -> str:
        if date_col:
            try:
                return _resolve_column_name(frame.columns, date_col)
            except ValueError:
                return _infer_date_column(frame)
        return _infer_date_column(frame)

    def _resolve_value_column(frame: pd.DataFrame, actual_date_col_name: str) -> str:
        if value_col:
            try:
                return _resolve_column_name(frame.columns, value_col)
            except ValueError:
                inferred = _infer_value_column(frame, actual_date_col_name)
                return inferred
        return _infer_value_column(frame, actual_date_col_name)

    if file_path:
        wb = get_workbook(world, file_path)
        target_sheet = sheet_name or wb.sheetnames[0]
        table = read_table_multi(
            world,
            file_path,
            target_sheet,
            range_ref,
            require_primary_key=False,
            stop_at_note_row=True,
        )
        header = table.get("header", [])
        if not header:
            raise ValueError(f"No usable table found in {os.path.basename(file_path)}.")
        source_frames = [(os.path.basename(file_path), pd.DataFrame(table["rows"], columns=header))]
    else:
        tables = load_all_tables(
            world,
            range_ref=range_ref,
            require_primary_key=False,
            stop_at_note_row=True,
        )
        if not tables:
            raise ValueError("No tables available for time-series aggregation.")
        source_frames = [(table["file_name"], table["df"].copy()) for table in tables]

    normalized_frames: list[pd.DataFrame] = []
    source_names: list[str] = []
    actual_date_col = None
    actual_value_col = None
    for source_name, df in source_frames:
        if df.empty:
            continue
        try:
            frame_date_col = _resolve_date_column(df)
        except ValueError:
            continue
        frame_value_col = _resolve_value_column(df, frame_date_col)
        working_frame = df[[frame_date_col, frame_value_col]].copy()
        date_text = working_frame[frame_date_col].map(_normalize_cell_text)
        year_mask = date_text.str.fullmatch(r"\d{4}")
        if year_mask.fillna(False).sum() >= max(2, len(date_text) // 2):
            working_frame[frame_date_col] = pd.to_datetime(
                date_text,
                format="%Y",
                errors="coerce",
            )
        else:
            working_frame[frame_date_col] = pd.to_datetime(working_frame[frame_date_col], errors="coerce")
        working_frame[frame_value_col] = working_frame[frame_value_col].map(_parse_numeric_text)
        working_frame = working_frame.dropna(subset=[frame_date_col, frame_value_col]).reset_index(drop=True)
        if working_frame.empty:
            continue
        working_frame.columns = ["_date", "_value"]
        normalized_frames.append(working_frame)
        source_names.append(source_name)
        if actual_date_col is None:
            actual_date_col = frame_date_col
        if actual_value_col is None:
            actual_value_col = frame_value_col

    if not normalized_frames:
        raise ValueError("No valid rows remained after parsing the requested time-series columns.")

    working = pd.concat(normalized_frames, ignore_index=True)
    working.columns = [actual_date_col or date_col, actual_value_col or (value_col or "Value")]
    if working.empty:
        raise ValueError(
            f"No valid rows remained after parsing `{actual_date_col}` and `{actual_value_col}`."
        )

    latest_date = working[actual_date_col].max()
    if window_years is not None and window_years > 0:
        cutoff = latest_date - pd.DateOffset(years=int(window_years))
        working = working.loc[working[actual_date_col] >= cutoff].reset_index(drop=True)
        if working.empty:
            raise ValueError("No rows remained after applying the requested time window.")

    aggregate_name = (aggregate or "mean").strip().lower()
    aggregate_aliases = {
        "average": "mean",
        "avg": "mean",
        "mean": "mean",
        "sum": "sum",
        "total": "sum",
        "count": "count",
        "median": "median",
        "min": "min",
        "minimum": "min",
        "max": "max",
        "maximum": "max",
    }
    aggregate_func = aggregate_aliases.get(aggregate_name)
    if not aggregate_func:
        raise ValueError(f"Unsupported aggregate `{aggregate}`.")

    period_name = (period or "month").strip().lower()
    period_mode_name = (period_mode or "year_month").strip().lower()
    if period_name == "month":
        if period_mode_name == "month_of_year":
            working["_period_sort"] = working[actual_date_col].dt.month
            working["_period_label"] = working[actual_date_col].dt.strftime("%B")
        else:
            period_values = working[actual_date_col].dt.to_period("M")
            working["_period_sort"] = period_values.astype(str)
            working["_period_label"] = period_values.astype(str)
    elif period_name == "quarter":
        if period_mode_name == "quarter_of_year":
            working["_period_sort"] = working[actual_date_col].dt.quarter
            working["_period_label"] = "Q" + working[actual_date_col].dt.quarter.astype(str)
        else:
            period_values = working[actual_date_col].dt.to_period("Q")
            working["_period_sort"] = period_values.astype(str)
            working["_period_label"] = period_values.astype(str)
    elif period_name == "year":
        working["_period_sort"] = working[actual_date_col].dt.year
        working["_period_label"] = working["_period_sort"].astype(str)
    else:
        raise ValueError(f"Unsupported period `{period}`.")

    grouped = (
        working.groupby(["_period_sort", "_period_label"], dropna=False)[actual_value_col]
        .agg(aggregate_func)
        .reset_index()
    )
    sort_col = "_period_sort"
    label_col = "Period"
    value_header_map = {
        "mean": f"Average {actual_value_col}",
        "sum": f"Total {actual_value_col}",
        "count": f"Count of {actual_value_col}",
        "median": f"Median {actual_value_col}",
        "min": f"Minimum {actual_value_col}",
        "max": f"Maximum {actual_value_col}",
    }
    value_col_name = value_header_map[aggregate_func]
    grouped.columns = [sort_col, label_col, value_col_name]
    if sort_desc:
        grouped = grouped.sort_values(by=value_col_name, ascending=False, kind="stable").reset_index(drop=True)
    else:
        grouped = grouped.sort_values(by=sort_col, ascending=True, kind="stable").reset_index(drop=True)
    grouped[value_col_name] = grouped[value_col_name].round(4)
    output_df = grouped[[label_col, value_col_name]]
    detail_data = [output_df.columns.tolist()] + output_df.fillna("").values.tolist()
    window_label = f"latest {int(window_years)} years" if window_years else "full available period"
    return {
        "output_df": output_df,
        "detail_data": detail_data,
        "summary": {
            "Source": ", ".join(source_names),
            "Window": window_label,
            "Latest Date": str(latest_date.date()),
            "Rows Used": int(len(working)),
        },
        "metadata": {
            "date_col": actual_date_col,
            "value_col": actual_value_col,
            "period": period_name,
            "period_mode": period_mode_name,
            "aggregate": aggregate_func,
        },
    }


def _parse_numeric_text(value: Any) -> float:
    text = _normalize_cell_text(value)
    if not text:
        return float("nan")
    cleaned = text.replace(",", "").replace("$", "").replace("%", "").strip()
    if cleaned == "":
        return float("nan")
    try:
        return float(cleaned)
    except ValueError:
        return float("nan")


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
    exceed_label = "Exceeding Target (lower is better)" if lower_is_better else "Exceeding Target"
    if "gross profit" in lower and "margin" not in lower:
        return "On Target" if relative_gap < 0.02 else exceed_label
    if "margin" in lower:
        return "On Target" if relative_gap < 0.05 else exceed_label
    if "cac" in lower:
        return "On Target" if relative_gap < 0.03 else exceed_label
    if "ratio" in lower:
        return "On Target" if relative_gap < 0.05 else exceed_label
    return "On Target" if relative_gap < 0.05 else exceed_label


def _round_dashboard_numeric(metric_name: str, value: float) -> float:
    lower = metric_name.lower()
    if "margin" in lower:
        return round(float(value), 4)
    if "cac" in lower or "ratio" in lower:
        return round(float(value), 2)
    return round(float(value), 0)


def build_weighted_share_value_report(
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
                brand_columns = _select_contiguous_labeled_columns(
                    header_row,
                    start_col_idx=quarter_col_idx + 1,
                    stop_markers=("in %",),
                )
                records = _extract_period_records(
                    norm_rows[header_idx + 1:],
                    period_col_idx=quarter_col_idx,
                    labeled_columns=brand_columns,
                    is_period_value=lambda value: bool(quarter_pattern.match(_normalize_cell_text(value))),
                    period_transform=_normalize_cell_text,
                    period_key="Time",
                )
                for record in records:
                    for _col_idx, label in brand_columns:
                        numeric = pd.to_numeric(pd.Series([str(record[label]).replace("%", "")]), errors="coerce").iloc[0]
                        record[label] = 0.0 if pd.isna(numeric) else float(numeric)
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
        raise ValueError("Could not identify both share-matrix and total-value tables from the loaded workbooks.")

    try:
        overlap_df = _merge_on_shared_period(market_share_df, shipment_df, period_col="Time")
    except ValueError as exc:
        raise ValueError("No overlapping quarter period was found between the share and total-value tables.") from exc

    brand_columns = [col for col in market_share_df.columns if col != "Time"]
    output_df = _build_weighted_period_output(
        overlap_df,
        period_col="Time",
        value_columns=brand_columns,
        weight_col="Shipment",
        output_period_col="Year",
        output_label_template="{name} (Unit shipment)",
    )

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
    """Compute operating cash flow efficiency and free cash flow by year."""
    workbook_paths = list_all_workbooks(world)
    target_path = file_path or (workbook_paths[0] if workbook_paths else None)
    if not target_path:
        raise ValueError("No workbook available for cash-flow analysis.")

    tables = load_all_tables(
        world,
        require_primary_key=False,
        stop_at_note_row=False,
    )
    structured_table = None
    try:
        structured_table = find_table_by_headers(
            tables,
            required_headers=["Year"],
            preferred_headers=[
                "NetIncome_M_USD",
                "Net Income",
                "OperatingCashFlow_M_USD",
                "Operating Cash Flow",
                "CapEx_M_USD",
                "Capital Expenditures",
            ],
        )
    except Exception:
        structured_table = None

    if structured_table is not None:
        df = structured_table["df"].copy()
        year_col = _resolve_column_name(df.columns, "Year", "Fiscal Year", "FY")
        net_income_col = _resolve_column_name(df.columns, "NetIncome_M_USD", "Net Income", "NetIncome")
        ocf_col = _resolve_column_name(
            df.columns,
            "OperatingCashFlow_M_USD",
            "Operating Cash Flow",
            "OperatingCashFlow",
            "OCF",
        )
        capex_col = _resolve_column_name(
            df.columns,
            "CapEx_M_USD",
            "Capital Expenditures",
            "CapitalExpenditures_M_USD",
            "CapEx",
        )

        working = df[[year_col, net_income_col, ocf_col, capex_col]].copy()
        working.columns = ["Year", "Net Income", "Operating Cash Flow", "Capital Expenditures"]
        for column_name in ["Net Income", "Operating Cash Flow", "Capital Expenditures"]:
            working[column_name] = pd.to_numeric(working[column_name], errors="coerce")
        working = working.dropna(subset=["Year", "Net Income", "Operating Cash Flow", "Capital Expenditures"]).reset_index(drop=True)
        if working.empty:
            raise ValueError("Structured cash-flow table did not contain usable numeric values.")

        working["OCF/Net Income"] = (
            working["Operating Cash Flow"] / working["Net Income"]
        ).replace([np.inf, -np.inf], np.nan).round(2)
        working["Free Cash Flow"] = (
            working["Operating Cash Flow"] - working["Capital Expenditures"]
        ).round(0)
        working["Anomaly Note"] = working["Net Income"].apply(
            lambda value: "Negative net income year" if float(value) < 0 else ""
        )

        totals_row = {
            "Year": "Total",
            "Net Income": round(float(working["Net Income"].sum()), 0),
            "Operating Cash Flow": round(float(working["Operating Cash Flow"].sum()), 0),
            "Capital Expenditures": round(float(working["Capital Expenditures"].sum()), 0),
            "OCF/Net Income": round(
                float(working["Operating Cash Flow"].sum()) / float(working["Net Income"].sum()),
                2,
            ) if float(working["Net Income"].sum()) else np.nan,
            "Free Cash Flow": round(float(working["Free Cash Flow"].sum()), 0),
            "Anomaly Note": "",
        }
        output_df = pd.concat([working, pd.DataFrame([totals_row])], ignore_index=True)
        detail_data = [output_df.columns.tolist()] + output_df.fillna("").values.tolist()
        return {
            "output_df": output_df,
            "formatted_df": output_df.copy(),
            "detail_data": detail_data,
            "row_count": int(len(output_df)),
            "column_count": int(len(output_df.columns)),
        }

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


def build_region_share_cost_report(
    world: SpreadsheetWorld,
    range_ref: str = "A1:Z200",
) -> Dict[str, Any]:
    """Build a regional population-share and expenditure-per-person summary."""
    tables = load_all_tables(
        world,
        range_ref=range_ref,
        require_primary_key=False,
        stop_at_note_row=False,
    )
    population_df = None
    expenditure_df = None
    for table in tables:
        df = table["df"].copy()
        if df.empty:
            continue
        try:
            region_col = _resolve_column_name(df.columns, "Region")
        except ValueError:
            continue

        value_candidates: list[tuple[str, str]] = []
        for column in df.columns:
            if str(column) == str(region_col):
                continue
            normalized = _normalize_header_name(column)
            if normalized:
                value_candidates.append((str(column), normalized))

        if population_df is None:
            population_col = next(
                (
                    column
                    for column, normalized in value_candidates
                    if "population" in normalized
                    and any(token in normalized for token in ("million", "people", "persons"))
                ),
                None,
            )
            if population_col is not None:
                working = df[[region_col, population_col]].copy()
                working.columns = ["Region", "Population (millions)"]
                working["Population (millions)"] = pd.to_numeric(
                    working["Population (millions)"], errors="coerce"
                )
                working = working.dropna(subset=["Region", "Population (millions)"]).reset_index(drop=True)
                if not working.empty:
                    population_df = working

        if expenditure_df is None:
            expenditure_col = next(
                (
                    column
                    for column, normalized in value_candidates
                    if any(token in normalized for token in ("expenditure", "spending", "spend", "cost"))
                    and any(token in normalized for token in ("billion", "usd", "dollar"))
                ),
                None,
            )
            if expenditure_col is not None:
                working = df[[region_col, expenditure_col]].copy()
                working.columns = ["Region", "Expenditure (billion USD)"]
                working["Expenditure (billion USD)"] = pd.to_numeric(
                    working["Expenditure (billion USD)"], errors="coerce"
                )
                working = working.dropna(subset=["Region", "Expenditure (billion USD)"]).reset_index(drop=True)
                if not working.empty:
                    expenditure_df = working

    if population_df is None or expenditure_df is None:
        raise ValueError("Could not identify both region-population and region-expenditure tables.")

    output_df = population_df.merge(expenditure_df, on="Region", how="inner")
    total_population = float(output_df["Population (millions)"].sum())
    output_df["Share of Global (%)"] = output_df["Population (millions)"] / total_population * 100.0
    output_df["Avg Expenditure per Person (USD)"] = (
        output_df["Expenditure (billion USD)"] * 1000.0 / output_df["Population (millions)"]
    )
    output_df = output_df[
        [
            "Region",
            "Population (millions)",
            "Expenditure (billion USD)",
            "Share of Global (%)",
            "Avg Expenditure per Person (USD)",
        ]
    ]
    output_df = output_df.sort_values(
        by="Population (millions)", ascending=False, kind="stable"
    ).reset_index(drop=True)
    normalized_output_df = pd.DataFrame(
        {
            "Region": output_df["Region"],
            "Obese_Pop_millions": output_df["Population (millions)"].round(1),
            "Global_Share_pct": output_df["Share of Global (%)"].round(2),
            "Expenditure_BillionUSD": output_df["Expenditure (billion USD)"].round(1),
            "Avg_Exp_per_Person_USD": output_df["Avg Expenditure per Person (USD)"].round(0).astype(int),
        }
    )
    detail_data = [normalized_output_df.columns.tolist()] + normalized_output_df.where(
        pd.notna(normalized_output_df), None
    ).values.tolist()
    detail_data.append([None, None, None, None, None])
    detail_data.append(["Total", round(total_population, 1), "100.00", None, None])
    return {
        "output_df": normalized_output_df,
        "detail_data": detail_data,
        "summary": {
            "Total": round(total_population, 1),
        },
        "row_count": int(len(normalized_output_df)),
        "column_count": int(len(normalized_output_df.columns)),
    }


def build_two_dimension_mean_count_summary_report(
    world: SpreadsheetWorld,
    range_ref: str = "A1:Y50000",
) -> Dict[str, Any]:
    """Group reviews by country and type/brand with average rating and count."""
    tables = load_all_tables(
        world,
        range_ref=range_ref,
        require_primary_key=False,
        stop_at_note_row=False,
    )
    review_table = find_table_by_headers(
        tables,
        required_headers=["country", "rating"],
        preferred_headers=["brand", "category", "type"],
    )
    df = review_table["df"].copy()
    country_col = _resolve_column_name(df.columns, "country")
    try:
        secondary_group_col = _resolve_column_name(df.columns, "brand", "category", "type")
    except ValueError:
        secondary_group_col = next(
            (
                str(column)
                for column in df.columns
                if str(column) != str(country_col)
                and any(
                    token in _normalize_header_name(column)
                    for token in ("brand", "category", "type", "segment", "group")
                )
            ),
            None,
        )
        if secondary_group_col is None:
            raise ValueError(f"Could not identify a secondary grouping column from {list(df.columns)}")
    rating_col = _resolve_column_name(df.columns, "rating")

    df[rating_col] = pd.to_numeric(df[rating_col], errors="coerce")
    working = df.dropna(subset=[country_col, secondary_group_col, rating_col]).copy()
    grouped = (
        working.groupby([country_col, secondary_group_col], dropna=False)
        .agg(
            avg_rating=(rating_col, "mean"),
            num_reviews=(rating_col, "count"),
        )
        .reset_index()
        .sort_values(by=[country_col, secondary_group_col], kind="stable")
        .reset_index(drop=True)
    )
    grouped.columns = ["Country", "HotelType", "avg_rating", "num_reviews"]
    detail_data = [grouped.columns.tolist()] + grouped.fillna("").values.tolist()
    return {
        "output_df": grouped,
        "detail_data": detail_data,
        "row_count": int(len(grouped)),
        "column_count": int(len(grouped.columns)),
    }


def build_multi_source_group_comparison_report(
    world: SpreadsheetWorld,
    range_ref: str = "A1:Z100000",
) -> Dict[str, Any]:
    """Merge related operational tables and build grouped summary comparison sheets."""
    tables = load_all_tables(
        world,
        range_ref=range_ref,
        require_primary_key=False,
        stop_at_note_row=False,
    )
    features_table = find_table_by_headers(
        tables,
        required_headers=["IsHoliday"],
        preferred_headers=["Store", "StoreID", "WeeklySales_USD", "Weekly_Sales", "Temperature", "Temperature_F", "Fuel_Price", "FuelPrice_USD"],
    )
    try:
        stores_table = find_table_by_headers(
            tables,
            required_headers=["Store", "Type", "Size"],
        )
    except ValueError:
        stores_table = find_table_by_headers(
            tables,
            required_headers=["StoreID", "StoreType", "Size_sqft"],
        )

    features_df = features_table["df"].copy()
    stores_df = stores_table["df"].copy()
    store_col = _resolve_column_name(features_df.columns, "Store", "StoreID")
    stores_store_col = _resolve_column_name(stores_df.columns, "Store", "StoreID")
    features_df[store_col] = pd.to_numeric(features_df[store_col], errors="coerce")
    stores_df[stores_store_col] = pd.to_numeric(stores_df[stores_store_col], errors="coerce")

    merged = features_df.merge(
        stores_df,
        left_on=store_col,
        right_on=stores_store_col,
        how="inner",
    )

    type_col = _resolve_column_name(merged.columns, "Type", "StoreType")
    isholiday_col = _resolve_column_name(merged.columns, "IsHoliday")
    metric_specs = [
        ("WeeklySales_USD", ("WeeklySales_USD", "Weekly_Sales", "Sales")),
        ("Temperature_F", ("Temperature", "Temperature_F")),
        ("FuelPrice_USD", ("Fuel_Price", "FuelPrice_USD")),
    ]
    resolved_metrics: list[tuple[str, str]] = []
    for output_name, candidate_names in metric_specs:
        try:
            actual = _resolve_column_name(merged.columns, *candidate_names)
        except ValueError:
            continue
        merged[actual] = pd.to_numeric(merged[actual], errors="coerce")
        resolved_metrics.append((output_name, actual))

    merged[isholiday_col] = merged[isholiday_col].apply(
        lambda value: bool(value) if isinstance(value, bool) else str(value).strip().lower() in {"true", "1", "yes"}
    )

    avg_by_type = (
        merged.groupby(type_col, dropna=False)[[actual for _output, actual in resolved_metrics]]
        .mean()
        .reset_index()
    )
    avg_by_type.columns = ["StoreType"] + [output_name for output_name, _actual in resolved_metrics]

    holiday_rows: list[list[Any]] = [["Feature", "Holiday Average", "Non-Holiday Average", "Difference"]]
    holiday_mask = merged[isholiday_col] == True
    non_holiday_mask = merged[isholiday_col] == False
    for feature, actual in resolved_metrics:
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
        "sheet_names": ["AvgByGroupType", "ConditionalComparison"],
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
            try:
                target_table = target_table or _extract_structured_table_from_workbook(
                    world,
                    file_path,
                    required_headers=["Metric", "Target"],
                    range_ref=range_ref,
                )
            except Exception:
                continue

    if pnl_table is None or sales_table is None or target_table is None:
        tables = load_all_tables(
            world,
            range_ref=range_ref,
            require_primary_key=False,
            stop_at_note_row=False,
        )
        if pnl_table is None:
            for required_headers in (
                ["Month", "Revenue", "Cost of Goods Sold", "Operating Expenses", "Interest Paid"],
                ["Month", "Revenue_USD", "COGS_USD", "OperatingExpenses_USD", "InterestPaid_USD"],
            ):
                try:
                    pnl_table = find_table_by_headers(tables, required_headers=required_headers)
                    break
                except Exception:
                    continue
        if sales_table is None:
            for required_headers in (
                ["Month", "New Customers", "Marketing Spend"],
                ["Month", "NewCustomers", "MarketingSpend_USD"],
            ):
                try:
                    sales_table = find_table_by_headers(tables, required_headers=required_headers)
                    break
                except Exception:
                    continue
        if target_table is None:
            for required_headers in (
                ["KPI", "Q1 Target"],
                ["Metric", "Target"],
            ):
                try:
                    target_table = find_table_by_headers(tables, required_headers=required_headers)
                    break
                except Exception:
                    continue

    if pnl_table is None or sales_table is None or target_table is None:
        raise ValueError("Could not identify the P&L, sales/marketing, and KPI target tables.")

    pnl_df = pnl_table["df"].copy()
    sales_df = sales_table["df"].copy()
    target_df = target_table["df"].copy()

    def _resolve_first_column(columns, candidates: Sequence[str]) -> str:
        for candidate in candidates:
            try:
                return _resolve_column_name(columns, candidate)
            except Exception:
                continue
        raise ValueError(f"Could not resolve any of the candidate columns: {candidates}")

    month_col = _resolve_column_name(pnl_df.columns, "Month")
    revenue_col = _resolve_first_column(pnl_df.columns, ("Revenue", "Revenue_USD"))
    cogs_col = _resolve_first_column(pnl_df.columns, ("Cost of Goods Sold", "COGS_USD"))
    opex_col = _resolve_first_column(pnl_df.columns, ("Operating Expenses", "OperatingExpenses_USD"))
    interest_col = _resolve_first_column(pnl_df.columns, ("Interest Paid", "InterestPaid_USD"))
    sales_month_col = _resolve_column_name(sales_df.columns, "Month")
    customers_col = _resolve_first_column(sales_df.columns, ("New Customers", "NewCustomers"))
    marketing_col = _resolve_first_column(sales_df.columns, ("Marketing Spend", "MarketingSpend_USD"))
    kpi_col = _resolve_first_column(target_df.columns, ("KPI", "Metric"))
    target_col = _resolve_first_column(target_df.columns, ("Q1 Target", "Target"))

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
    merged["Gross Profit Margin"] = merged["Gross Profit"] / merged[revenue_col]
    merged["Net Profit Margin"] = merged["Net Profit"] / merged[revenue_col]
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
        "Gross Profit Margin": (total_gross_profit / total_revenue),
        "Net Profit Margin": (total_net_profit / total_revenue),
        "Customer Acquisition Cost (CAC)": total_marketing / total_customers,
        "Marketing Efficiency Ratio": total_revenue / total_marketing,
    }

    target_lookup = {
        _normalize_header_name(metric): _parse_numeric_text(value)
        for metric, value in zip(target_df[kpi_col], target_df[target_col])
        if _normalize_cell_text(metric)
    }

    quarter_numbers: list[int] = []
    for value in merged[month_col].tolist():
        text = _normalize_cell_text(value).lower()
        if not text:
            continue
        month_map = {
            "jan": 1, "january": 1,
            "feb": 2, "february": 2,
            "mar": 3, "march": 3,
            "apr": 4, "april": 4,
            "may": 5,
            "jun": 6, "june": 6,
            "jul": 7, "july": 7,
            "aug": 8, "august": 8,
            "sep": 9, "sept": 9, "september": 9,
            "oct": 10, "october": 10,
            "nov": 11, "november": 11,
            "dec": 12, "december": 12,
        }
        month_number = month_map.get(text)
        if month_number is None:
            for token, candidate_number in month_map.items():
                if token in text:
                    month_number = candidate_number
                    break
        if month_number is not None:
            quarter_numbers.append(((month_number - 1) // 3) + 1)
    quarter_label = f"Q{min(quarter_numbers)}" if quarter_numbers else "Quarter"

    dashboard_records: list[dict[str, Any]] = []
    metric_aliases = {
        _normalize_header_name("Gross Profit"): ("Gross Profit", "Gross_Profit"),
        _normalize_header_name("Net Profit"): ("Net Profit", "Net_Profit"),
        _normalize_header_name("Gross Profit Margin"): ("Gross Profit Margin", "Gross_Profit_Margin"),
        _normalize_header_name("Net Profit Margin"): ("Net Profit Margin", "Net_Profit_Margin"),
        _normalize_header_name("Customer Acquisition Cost (CAC)"): ("Customer Acquisition Cost (CAC)", "CAC", "Customer Acquisition Cost"),
        _normalize_header_name("Marketing Efficiency Ratio"): ("Marketing Efficiency Ratio", "MER"),
    }
    for metric_name, actual in dashboard_metrics.items():
        lookup_key = _normalize_header_name(metric_name)
        candidate_keys = [
            _normalize_header_name(candidate)
            for candidate in metric_aliases.get(lookup_key, (metric_name,))
        ]
        matched_key = next((candidate for candidate in candidate_keys if candidate in target_lookup), None)
        if matched_key is None:
            raise ValueError(f"Target missing for KPI `{metric_name}`.")
        target_value = float(target_lookup[matched_key])
        variance = actual - target_value
        normalized_metric_name = {
            "Gross Profit": "Gross_Profit",
            "Net Profit": "Net_Profit",
            "Gross Profit Margin": "Gross_Profit_Margin",
            "Net Profit Margin": "Net_Profit_Margin",
            "Customer Acquisition Cost (CAC)": "CAC",
            "Marketing Efficiency Ratio": "Marketing_Efficiency_Ratio",
        }.get(metric_name, metric_name.replace(" ", "_"))
        dashboard_records.append(
            {
                "Metric": normalized_metric_name,
                f"{quarter_label}_Actual": _round_dashboard_numeric(metric_name, actual),
                "Target": _round_dashboard_numeric(metric_name, target_value),
                "Variance": _round_dashboard_numeric(metric_name, variance),
                "Assessment": _dashboard_assessment(metric_name, actual, target_value),
            }
        )

    output_df = pd.DataFrame(
        dashboard_records,
        columns=["Metric", f"{quarter_label}_Actual", "Target", "Variance", "Assessment"],
    )
    detail_data = [output_df.columns.tolist()] + output_df.where(pd.notna(output_df), None).values.tolist()
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

    def _require_param(*aliases: str) -> float:
        for alias in aliases:
            key = _normalize_header_name(alias)
            if key in param_lookup and param_lookup[key] is not None:
                return float(param_lookup[key])
        raise KeyError(_normalize_header_name(aliases[0]))

    demand = _require_param("Annual Demand (D)", "Annual_Demand_units", "Annual Demand")
    ordering_cost = _require_param("Ordering Cost (S)", "Order_Cost_USD", "Order Cost")
    holding_cost = _require_param("Holding Cost (H)", "Holding_Cost_per_unit_USD", "Holding Cost Per Unit")
    unit_cost = _require_param("Unit Cost (C)", "Unit_Cost_USD", "Unit Cost")
    lead_time_days = _require_param("Lead Time (L)", "Lead_Time_days", "Lead Time")
    working_days = _require_param("Working Days per Year", "Working_Days_per_year")

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


def build_multi_source_utilisation_summary_report(
    world: SpreadsheetWorld,
    range_ref: str = "A1:Z10000",
) -> Dict[str, Any]:
    """Aggregate multiple operational tables into one utilisation report."""
    tables = load_all_tables(
        world,
        range_ref=range_ref,
        require_primary_key=True,
        stop_at_note_row=True,
    )
    if len(tables) < 3:
        raise ValueError("Utilisation workflow expects at least three related operational tables.")

    normalized_headers = [
        {_normalize_header_name(col) for col in table.get("header", [])}
        for table in tables
    ]
    school_required = {
        _normalize_header_name("Department"),
        _normalize_header_name("VisitsPerMonth"),
        _normalize_header_name("MaxCapacity_per_month"),
    }
    has_department_capacity_schema = any(
        school_required.issubset(header)
        for header in normalized_headers
    )
    if has_department_capacity_schema:
        staff_table = find_table_by_headers(
            tables,
            required_headers=["StaffID", "Department", "ContractHours_per_week"],
        )
        schedule_table = find_table_by_headers(
            tables,
            required_headers=["StaffID", "Week", "ActualHours"],
        )
        service_table = find_table_by_headers(
            tables,
            required_headers=["Department", "VisitsPerMonth", "MaxCapacity_per_month"],
        )

        staff_df = staff_table["df"].copy()
        schedule_df = schedule_table["df"].copy()
        service_df = service_table["df"].copy()

        staff_id_col = _resolve_column_name(staff_df.columns, "StaffID")
        dept_col = _resolve_column_name(staff_df.columns, "Department")
        contract_col = _resolve_column_name(staff_df.columns, "ContractHours_per_week")
        schedule_staff_id_col = _resolve_column_name(schedule_df.columns, "StaffID")
        actual_col = _resolve_column_name(schedule_df.columns, "ActualHours")
        service_dept_col = _resolve_column_name(service_df.columns, "Department")
        visits_col = _resolve_column_name(service_df.columns, "VisitsPerMonth")
        capacity_col = _resolve_column_name(service_df.columns, "MaxCapacity_per_month")

        staff_df[contract_col] = pd.to_numeric(staff_df[contract_col], errors="coerce")
        schedule_df[actual_col] = pd.to_numeric(schedule_df[actual_col], errors="coerce")
        service_df[visits_col] = pd.to_numeric(service_df[visits_col], errors="coerce")
        service_df[capacity_col] = pd.to_numeric(service_df[capacity_col], errors="coerce")

        staff_usage = schedule_df.groupby(schedule_staff_id_col, dropna=False)[actual_col].sum().reset_index()
        staff_usage = staff_usage.merge(
            staff_df[[staff_id_col, dept_col, contract_col]],
            left_on=schedule_staff_id_col,
            right_on=staff_id_col,
            how="left",
        )
        dept_staff = (
            staff_usage.groupby(dept_col, dropna=False)
            .agg(total_actual=(actual_col, "sum"), total_contract=(contract_col, "sum"))
            .reset_index()
        )
        dept_staff["Staff Utilisation (%)"] = (
            dept_staff["total_actual"] / dept_staff["total_contract"] * 100.0
        )

        service_df["Service Utilisation (%)"] = service_df[visits_col] / service_df[capacity_col] * 100.0
        output_df = service_df[[service_dept_col, "Service Utilisation (%)"]].merge(
            dept_staff[[dept_col, "Staff Utilisation (%)"]],
            left_on=service_dept_col,
            right_on=dept_col,
            how="left",
        )
        output_df = output_df.rename(columns={service_dept_col: "Department"})
        output_df = output_df[["Department", "Service Utilisation (%)", "Staff Utilisation (%)"]]
        output_df = output_df.sort_values(by="Department", kind="stable").reset_index(drop=True)
        highlight_rows = [
            index + 2
            for index, row in output_df.iterrows()
            if float(row["Service Utilisation (%)"]) > 90.0 or float(row["Staff Utilisation (%)"]) > 90.0
        ]
        detail_data = [output_df.columns.tolist()] + output_df.fillna("").values.tolist()
        return {
            "output_df": output_df,
            "detail_data": detail_data,
            "highlight_rows": highlight_rows,
        }

    has_university_utilisation_schema = (
        any(
            {
                _normalize_header_name("SectionID"),
                _normalize_header_name("CourseID"),
                _normalize_header_name("Instructor"),
                _normalize_header_name("RoomID"),
                _normalize_header_name("Capacity"),
            }.issubset(header)
            for header in normalized_headers
        )
        and any(
            {
                _normalize_header_name("StudentID"),
                _normalize_header_name("SectionID"),
                _normalize_header_name("EnrollStatus"),
            }.issubset(header)
            for header in normalized_headers
        )
        and any(
            {
                _normalize_header_name("RoomID"),
                _normalize_header_name("Building"),
            }.issubset(header)
            for header in normalized_headers
        )
    )
    if has_university_utilisation_schema:
        section_table = find_table_by_headers(
            tables,
            required_headers=["SectionID", "CourseID", "Instructor", "RoomID", "Capacity"],
        )
        enrollment_table = find_table_by_headers(
            tables,
            required_headers=["StudentID", "SectionID", "EnrollStatus"],
        )
        room_table = find_table_by_headers(
            tables,
            required_headers=["RoomID", "Building"],
        )

        section_df = section_table["df"].copy()
        enrollment_df = enrollment_table["df"].copy()
        room_df = room_table["df"].copy()

        section_id_col = _resolve_column_name(section_df.columns, "SectionID")
        course_id_col = _resolve_column_name(section_df.columns, "CourseID")
        instructor_col = _resolve_column_name(section_df.columns, "Instructor")
        room_id_col = _resolve_column_name(section_df.columns, "RoomID")
        section_capacity_col = _resolve_column_name(section_df.columns, "Capacity")
        scheduled_hours_col = _resolve_column_name(section_df.columns, "ScheduledHours")
        enrollment_section_col = _resolve_column_name(enrollment_df.columns, "SectionID")
        enroll_status_col = _resolve_column_name(enrollment_df.columns, "EnrollStatus")
        room_room_id_col = _resolve_column_name(room_df.columns, "RoomID")
        building_col = _resolve_column_name(room_df.columns, "Building")

        section_df[section_capacity_col] = pd.to_numeric(section_df[section_capacity_col], errors="coerce")
        section_df[scheduled_hours_col] = pd.to_numeric(section_df[scheduled_hours_col], errors="coerce")
        enrollment_df[enroll_status_col] = enrollment_df[enroll_status_col].map(_normalize_cell_text)

        def _count_status(series: pd.Series, accepted: tuple[str, ...]) -> int:
            normalized = series.fillna("").map(_normalize_cell_text).str.lower()
            return int(normalized.isin([item.lower() for item in accepted]).sum())

        enrollment_summary = (
            enrollment_df.groupby(enrollment_section_col, dropna=False)
            .agg(
                Enrolled_Count=(enroll_status_col, lambda s: _count_status(s, ("Registered", "Enrolled"))),
                Waitlisted_Count=(enroll_status_col, lambda s: _count_status(s, ("Waitlisted", "Waitlist"))),
            )
            .reset_index()
        )

        section_output = section_df[
            [section_id_col, course_id_col, instructor_col, room_id_col, section_capacity_col, scheduled_hours_col]
        ].merge(
            enrollment_summary,
            left_on=section_id_col,
            right_on=enrollment_section_col,
            how="left",
        )
        section_output = section_output.merge(
            room_df[[room_room_id_col, building_col]],
            left_on=room_id_col,
            right_on=room_room_id_col,
            how="left",
        )
        section_output["Enrolled_Count"] = pd.to_numeric(section_output["Enrolled_Count"], errors="coerce").fillna(0).astype(int)
        section_output["Waitlisted_Count"] = pd.to_numeric(section_output["Waitlisted_Count"], errors="coerce").fillna(0).astype(int)
        section_output["Fill_Rate"] = np.where(
            section_output[section_capacity_col].fillna(0) > 0,
            section_output["Enrolled_Count"] / section_output[section_capacity_col] * 100.0,
            0.0,
        )
        section_output["Waitlist_Rate"] = np.where(
            section_output[section_capacity_col].fillna(0) > 0,
            section_output["Waitlisted_Count"] / section_output[section_capacity_col] * 100.0,
            0.0,
        )
        section_output = section_output.rename(
            columns={
                section_id_col: "SectionID",
                course_id_col: "CourseID",
                instructor_col: "Instructor",
                room_id_col: "RoomID",
                section_capacity_col: "Capacity",
                scheduled_hours_col: "Scheduled_Hours",
                building_col: "Building",
            }
        )
        section_output = section_output[
            [
                "SectionID",
                "CourseID",
                "Instructor",
                "RoomID",
                "Building",
                "Capacity",
                "Enrolled_Count",
                "Waitlisted_Count",
                "Fill_Rate",
                "Waitlist_Rate",
                "Scheduled_Hours",
            ]
        ].sort_values(by=["SectionID"], kind="stable").reset_index(drop=True)

        instructor_output = (
            section_output.groupby("Instructor", dropna=False)
            .agg(
                Section_Count=("SectionID", "count"),
                Total_Enrolled=("Enrolled_Count", "sum"),
                Scheduled_Hours=("Scheduled_Hours", "sum"),
            )
            .reset_index()
            .sort_values(by=["Instructor"], kind="stable")
            .reset_index(drop=True)
        )

        room_output = (
            section_output.groupby("Building", dropna=False)
            .agg(Average_Fill_Rate=("Fill_Rate", "mean"))
            .reset_index()
            .sort_values(by=["Building"], kind="stable")
            .reset_index(drop=True)
        )

        highlight_rows = [
            index + 2
            for index, row in section_output.iterrows()
            if float(row["Fill_Rate"]) > 90.0 or float(row["Waitlist_Rate"]) > 20.0
        ]
        return {
            "output_df": section_output,
            "detail_data": [section_output.columns.tolist()] + section_output.fillna("").values.tolist(),
            "highlight_rows": highlight_rows,
            "sheet_outputs": {
                "Section_Utilisation": section_output,
                "Instructor_Load": instructor_output,
                "Room_Utilisation": room_output,
            },
        }

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
    resolved_target = _resolve_column_name(df.columns, target_col)
    filtered_feature_cols: list[str] = []
    seen_features: set[str] = set()
    for feature_col in feature_cols:
        resolved_feature = _resolve_column_name(df.columns, feature_col)
        if resolved_feature == resolved_target:
            continue
        if resolved_feature in seen_features:
            continue
        seen_features.add(resolved_feature)
        filtered_feature_cols.append(resolved_feature)
    if not filtered_feature_cols:
        raise ValueError("feature_cols must include at least one non-target feature column.")
    working, actual_target_col, actual_feature_cols = _prepare_numeric_feature_frame(
        df,
        filtered_feature_cols,
        target_col=resolved_target,
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
    numeric_columns: Sequence[str] | None = None,
    filter_column: str | None = None,
    filter_value: Any | None = None,
    round_digits: int = 2,
) -> Dict[str, Any]:
    """Build a labeled correlation matrix table for selected numeric columns."""
    working_df = df.copy()
    if numeric_columns is None:
        numeric_columns = working_df.select_dtypes(include="number").columns.tolist()
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
    output_df = matrix_df.reset_index().rename(columns={"index": "Variable"})
    detail_data = [["Variable"] + actual_numeric_cols]
    for column in actual_numeric_cols:
        row_values = matrix_df.loc[column].tolist() if column in matrix_df.index else [np.nan] * len(actual_numeric_cols)
        detail_data.append([column] + row_values)
    return {
        "matrix_df": matrix_df,
        "output_df": output_df,
        "detail_data": detail_data,
        "row_count": int(len(output_df)),
        "column_count": int(len(output_df.columns)),
        "numeric_columns": actual_numeric_cols,
        "metadata": {
            "helper": "build_correlation_matrix_table",
            "numeric_columns": actual_numeric_cols,
        },
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
    tables: Sequence[Dict[str, Any]] | pd.DataFrame,
    from_col: str = "Node From",
    to_col: str = "Node To",
) -> Dict[str, Any]:
    """Detect cycles for a sequence of directed-graph adjacency-list tables."""
    if isinstance(tables, pd.DataFrame):
        normalized_tables: list[Dict[str, Any]] = [
            {
                "df": tables.copy(),
                "file_name": None,
            }
        ]
    else:
        normalized_tables = list(tables or [])

    if not normalized_tables:
        raise ValueError("No tables available for cycle detection.")

    rows: List[List[Any]] = [["GraphID", "Contains_Cycle (True / False)"]]
    result_records: List[Dict[str, Any]] = []

    for index, table in enumerate(normalized_tables, start=1):
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
                "GraphID": graph_id,
                "Contains_Cycle (True / False)": bool(contains_cycle),
                "file_name": table.get("file_name"),
            }
        )

    output_df = pd.DataFrame(result_records)[["GraphID", "Contains_Cycle (True / False)"]]
    return {
        "output_df": output_df,
        "detail_data": rows,
        "row_count": int(len(output_df)),
        "column_count": int(len(output_df.columns)),
        "contains_cycle": bool(result_records[0]["Contains_Cycle (True / False)"]) if len(result_records) == 1 else None,
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
    "select_contiguous_labeled_columns",
    "find_first_period_cell",
    "extract_period_records",
    "merge_on_shared_period",
    "build_grouped_assignment_join",
    "build_weighted_period_output",
    "load_all_tables",
    "find_table_by_headers",
    "infer_common_key",
    "infer_common_keys",
    "concat_tables_with_same_headers",
    "build_relational_join_enrichment_report",
    "build_multi_key_relational_join_report",
    "merge_tables_on_key",
    "merge_tables_on_keys",
    "fill_missing_from_reference",
    "build_missing_data_report",
    "build_room_format_report",
    "build_capacity_constrained_allocation_report",
    "build_relational_assignment_schedule_report",
    "summarize_numeric_column",
    "build_group_summary",
    "build_grouped_aggregation_ranking_report",
    "build_time_series_aggregation_report",
    "compute_feature_correlations",
    "build_correlation_matrix_table",
    "fit_linear_regression_weights",
    "build_region_growth_analysis",
    "build_weighted_share_value_report",
    "build_cash_flow_efficiency_report",
    "build_region_share_cost_report",
    "build_two_dimension_mean_count_summary_report",
    "build_multi_source_group_comparison_report",
    "build_ecommerce_merge_report",
    "build_financial_dashboard_report",
    "build_candidate_screening_report",
    "build_inventory_eoq_report",
    "build_multi_source_utilisation_summary_report",
    "build_dependency_schedule",
    "build_cycle_detection_report",
]
