"""
normalizer.py — table structure detection and normalization.
"""

import re
import json
import pandas as pd
from openai import OpenAI


def find_file(filename: str) -> str:
    """Search common locations for an Excel file."""
    import os
    if os.path.exists(filename):
        return filename
    script_dir = os.path.dirname(os.path.abspath(__file__))
    search_paths = [
        os.path.join(script_dir, "../../artifacts/tests/Task01_output"),
        os.path.join(script_dir, "../../artifacts/tests/Task02_output"),
        os.path.join(script_dir, "../../artifacts/tests"),
        os.path.join(script_dir, "../../dataset/Task01"),
        os.path.join(script_dir, "../../dataset/Task02"),
        os.path.join(script_dir, "../../dataset"),
    ]
    for path in search_paths:
        full_path = os.path.join(path, filename)
        if os.path.exists(full_path):
            return full_path
    return filename


def excel_to_markdown(path: str) -> str:
    """Convert an Excel file to a markdown table string."""
    df = pd.read_excel(path)
    df = df.fillna("")
    lines = []
    headers = df.columns.tolist()
    lines.append("| " + " | ".join(str(h) for h in headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for _, row in df.iterrows():
        cells = [str(v) for v in row.values]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def detect_structure(df: pd.DataFrame) -> str:
    """
    Detect table structure type.
    Returns: 'flat', 'data_with_metrics', or 'multi_section'
    """
    str_vals = df.astype(str).values.flatten()
    has_metric_keyword = any("Metric" in str(v) for v in str_vals)
    metric_count = sum(1 for v in str_vals if str(v).strip() == "Metric")

    if metric_count >= 2:
        return "multi_section"
    elif has_metric_keyword:
        return "data_with_metrics"
    else:
        return "flat"


def normalize_cell_value(val: str) -> str:
    """
    Normalize a single cell value to remove known formatting differences:
    - Date timestamps: '2025-11-08 00:00:00' -> '2025-11-08'
    - Spaces in short codes: 'I 23' -> 'I23'
    """
    val = str(val).strip()

    # Normalize dates: 'YYYY-MM-DD HH:MM:SS' -> 'YYYY-MM-DD'
    date_match = re.match(r"(\d{4}-\d{2}-\d{2})( 00:00:00)?$", val)
    if date_match:
        return date_match.group(1)

    # Normalize internal spaces in short strings like 'I 23' -> 'I23'
    if len(val) <= 6 and " " in val:
        return val.replace(" ", "")

    return val


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Apply cell-level normalization to an entire dataframe."""
    df = df.copy().fillna("")
    for col in df.columns:
        df[col] = df[col].apply(lambda v: normalize_cell_value(str(v)))
    return df


def sort_dataframe_like_reference(df: pd.DataFrame, df_reference: pd.DataFrame) -> pd.DataFrame:
    """
    Reorder output rows to match reference row order, for flat tables only.
    Skips multi-section tables (those with blank separator rows).
    """
    ref_has_blanks = df_reference.isnull().all(axis=1).any()
    out_has_blanks = df.isnull().all(axis=1).any() or (df == "").all(axis=1).any()
    if ref_has_blanks or out_has_blanks:
        return df

    sort_col = None
    for col in df_reference.columns:
        if col not in df.columns:
            continue
        ref_vals = df_reference[col].dropna().astype(str).str.strip()
        if ref_vals.nunique() == len(df_reference) and (ref_vals != "").all():
            sort_col = col
            break

    if sort_col is None:
        return df

    ref_order = {str(v).strip(): i for i, v in enumerate(df_reference[sort_col])}

    def sort_key(val):
        return ref_order.get(str(val).strip(), 999)

    try:
        df_sorted = df.copy()
        df_sorted = df_sorted.iloc[
            df_sorted[sort_col].apply(sort_key).argsort()
        ].reset_index(drop=True)
        return df_sorted
    except Exception:
        return df


def get_structural_normalization(client: OpenAI, output_md: str, reference_md: str) -> dict:
    """
    Ask the LLM to identify column name/order differences and return rename+reorder instructions.
    Does not change any data values.
    """
    prompt = f"""You are comparing two Excel table outputs.

**REFERENCE (target structure):**
{reference_md}

**OUTPUT (to normalize):**
{output_md}

Identify ONLY structural differences (column names, column order).
Do NOT change any data values.

Return JSON:
{{
    "column_mapping": {{}},
    "column_order": ["col1", "col2", ...]
}}

- column_mapping: rename output columns to match reference (empty if already matching)
- column_order: correct column order matching reference

Return ONLY the JSON object."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)


def apply_structural_normalization(df: pd.DataFrame, instructions: dict) -> pd.DataFrame:
    """Apply column renaming and reordering from LLM instructions."""
    df = df.copy()

    mapping = instructions.get("column_mapping", {})
    if mapping:
        df = df.rename(columns=mapping)

    order = instructions.get("column_order", [])
    if order:
        existing = [c for c in order if c in df.columns]
        extra = [c for c in df.columns if c not in order]
        df = df[existing + extra]

    return df