"""Iterators for workbook diagnosis."""

from typing import Iterable, Tuple

import pandas as pd


def iter_string_columns(workbook_view) -> Iterable[Tuple[str, str, pd.Series]]:
    """Yield (sheet_key, column_name, series) for string-like columns."""
    if not isinstance(workbook_view, dict):
        return

    for sheet_key, df in workbook_view.items():
        if df is None or not hasattr(df, "columns"):
            continue

        for col in df.columns:
            try:
                series = df[col]
            except Exception:
                continue

            # Keep columns with any non-empty values.
            non_empty = series.dropna()
            if non_empty.empty:
                continue

            # Treat as string-like if most non-empty values are strings.
            str_count = 0
            total_count = 0
            for value in non_empty:
                total_count += 1
                if isinstance(value, str) and value.strip() != "":
                    str_count += 1

            if total_count == 0:
                continue

            if str_count / total_count >= 0.6:
                yield sheet_key, str(col), series
