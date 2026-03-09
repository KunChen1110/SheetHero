"""
Universal Table Evaluator
Works for any table structure:
  - Simple flat tables (test4, test5, test6, test7, test10, test12, test13)
  - Tables with a metrics section at the bottom (test1, test9)
  - Wide/transposed tables (test3, test8)
  - Multi-section tables (test11)
  - Tables with formatting inconsistencies (test2 room spacing)
  - Row-order differences (test25) — rows sorted before comparing

Scoring: table = 70pts, text = 30pts (text optional)
"""

import pandas as pd
import json
import os
import re
from typing import Tuple, Dict
from openai import OpenAI

API_KEY = ""
MODEL = "gpt-4o-mini"


# ──────────────────────────────────────────────
# File utilities
# ──────────────────────────────────────────────

def find_file(filename: str) -> str:
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
    """Convert Excel to markdown. Handles NaN gracefully."""
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


# ──────────────────────────────────────────────
# Step 1: Detect table structure type
# ──────────────────────────────────────────────

def detect_structure(df: pd.DataFrame) -> str:
    """
    Detect what kind of table structure this is.
    Returns one of: 'flat', 'data_with_metrics', 'multi_section'
    """
    str_vals = df.astype(str).values.flatten()

    # Check for 'Metric' keyword anywhere in the table
    has_metric_keyword = any("Metric" in str(v) for v in str_vals)

    # Check if 'Metric' appears more than once (multisection)
    metric_count = sum(1 for v in str_vals if str(v).strip() == "Metric")

    if metric_count >= 2:
        return "multi_section"
    elif has_metric_keyword:
        return "data_with_metrics"
    else:
        return "flat"


# ──────────────────────────────────────────────
# Step 2: Normalize the output to match reference structure
# ──────────────────────────────────────────────

def normalize_cell_value(val: str) -> str:
    """
    Normalize a single cell value:
    - Strip whitespace inside strings (e.g. 'I 23' → 'I23')
    - Normalize date formats (e.g. '2025-11-08 00:00:00' → '2025-11-08')
    - Normalize floats (e.g. '1.0' → '1', '0.0' → '0')
    """
    val = str(val).strip()

    # Normalize dates: 'YYYY-MM-DD HH:MM:SS' → 'YYYY-MM-DD'
    date_match = re.match(r"(\d{4}-\d{2}-\d{2})( 00:00:00)?$", val)
    if date_match:
        return date_match.group(1)

    # Normalize internal spaces in short strings like 'I 23' → 'I23'
    if len(val) <= 6 and " " in val:
        return val.replace(" ", "")

    return val


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Apply cell-level normalization to entire dataframe."""
    df = df.copy().fillna("")
    for col in df.columns:
        df[col] = df[col].apply(lambda v: normalize_cell_value(str(v)))
    return df


def sort_dataframe_like_reference(df: pd.DataFrame, df_reference: pd.DataFrame) -> pd.DataFrame:
    """
    If the output rows are in a different order than the reference, sort them to match.
    Only applies to flat tables — skips if the table has a metrics/multi-section structure
    (detected by presence of blank separator rows).

    Strategy: find the first column that exists in both dataframes and has no blank rows
    in the reference, then sort output by that column to match reference order.
    """
    # Don't sort if there are blank separator rows — it's a structured multi-section table
    ref_has_blanks = df_reference.isnull().all(axis=1).any()
    out_has_blanks = df.isnull().all(axis=1).any() or (df == "").all(axis=1).any()
    if ref_has_blanks or out_has_blanks:
        return df

    # Find a good sort column — first col in reference that has all unique, non-empty values
    sort_col = None
    for col in df_reference.columns:
        if col not in df.columns:
            continue
        ref_vals = df_reference[col].dropna().astype(str).str.strip()
        if ref_vals.nunique() == len(df_reference) and (ref_vals != "").all():
            sort_col = col
            break

    if sort_col is None:
        return df  # Can't find a reliable sort column, leave as-is

    # Build a sort order map from reference
    ref_order = {str(v).strip(): i for i, v in enumerate(df_reference[sort_col])}

    def sort_key(val):
        return ref_order.get(str(val).strip(), 999)

    try:
        df_sorted = df.copy()
        df_sorted = df_sorted.iloc[df_sorted[sort_col].apply(sort_key).argsort()].reset_index(drop=True)
        return df_sorted
    except Exception:
        return df  # If sorting fails for any reason, return original


def get_structural_normalization(client: OpenAI, output_md: str, reference_md: str) -> Dict:
    """
    Ask LLM to identify any structural differences (column renaming, reordering).
    Works for any table type — no assumptions about structure.
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
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)


def apply_structural_normalization(df: pd.DataFrame, instructions: Dict) -> pd.DataFrame:
    """Apply column renaming and reordering."""
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


# ──────────────────────────────────────────────
# Step 3: Score the table
# ──────────────────────────────────────────────

def compare_and_score(client: OpenAI, normalized_md: str, reference_md: str, structure_type: str) -> Tuple[float, str]:
    """
    Compare normalized output vs reference and score out of 70.
    Prompt adapts based on structure type.
    """

    structure_hint = {
        "flat": "This is a flat table. Compare all cells directly.",
        "data_with_metrics": "This table has a data section and a metrics/summary section at the bottom.",
        "multi_section": "This table has multiple sections. Each section may have its own headers and data.",
    }.get(structure_type, "")

    prompt = f"""Compare these two tables cell-by-cell and calculate a score out of 70 points.

{structure_hint}

**Normalized OUTPUT:**
{normalized_md}

**REFERENCE:**
{reference_md}

Scoring rules (per cell, excluding header rows):
- Exact string match → 1.0 (full credit)
- Same number, minor rounding difference (e.g. 69.78 vs 69.784) → 0.9
- Same date, different time component (e.g. "2025-11-08" vs "2025-11-08 00:00:00") → 0.8
- Same meaning, different format or spacing (e.g. "I23" vs "I 23", "True" vs "TRUE") → 0.8
- Wrong value or missing → 0.0

Count:
- total_cells: all non-header cells
- exact: exact matches
- rounding: numeric rounding only
- semantic: same meaning different format
- wrong: wrong or missing

Score = (exact*1.0 + rounding*0.9 + semantic*0.8) / total_cells * 70

Return JSON only:
{{
  "score": <float 0-70>,
  "exact": <int>,
  "rounding": <int>,
  "semantic": <int>,
  "wrong": <int>,
  "total_cells": <int>,
  "feedback": "<brief summary of main differences>"
}}"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        response_format={"type": "json_object"}
    )
    result = json.loads(response.choices[0].message.content)
    return float(result["score"]), result.get("feedback", "")


# ──────────────────────────────────────────────
# Step 4: Score natural language text (optional, 0-30)
# ──────────────────────────────────────────────

def score_text(client: OpenAI, output_text: str, reference_text: str) -> Tuple[float, str]:
    """Score natural language output semantically (0-30)."""
    if not output_text.strip() or not reference_text.strip():
        return 0.0, "No text provided."

    prompt = f"""Compare the OUTPUT answer to the REFERENCE answer semantically.

REFERENCE:
{reference_text}

OUTPUT:
{output_text}

Score the OUTPUT out of 30 points:
- Correct key facts → full credit
- Same meaning, different wording → full credit
- Missing or wrong facts → lose points

Return JSON only:
{{"score": <float 0-30>, "feedback": "<brief explanation>"}}"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        response_format={"type": "json_object"}
    )
    result = json.loads(response.choices[0].message.content)
    return float(result["score"]), result.get("feedback", "")


# ──────────────────────────────────────────────
# Main evaluate()
# ──────────────────────────────────────────────

def evaluate(
        output_excel: str,
        reference_excel: str,
        output_text: str = "",
        reference_text: str = "",
        save_normalized: bool = False,
) -> Dict:
    """
    Universal evaluation function. Works for any table structure.
    Returns dict with total_score (0-100), table_score (0-70), text_score (0-30).
    """
    client = OpenAI(api_key=API_KEY)

    output_path = find_file(output_excel)
    reference_path = find_file(reference_excel)

    print(f"\nEvaluating:")
    print(f"  Output:    {output_path}")
    print(f"  Reference: {reference_path}")

    # ── Load ──
    print("\n[1] Loading Excel files...")
    df_output = pd.read_excel(output_path)
    df_reference = pd.read_excel(reference_path)
    print(f"   Output shape:    {df_output.shape}")
    print(f"   Reference shape: {df_reference.shape}")

    # ── Detect structure ──
    print("[2] Detecting table structure...")
    structure_type = detect_structure(df_output)
    print(f"   Structure type: {structure_type}")

    # ── Convert to markdown ──
    print("[3] Converting to Markdown...")
    output_md = excel_to_markdown(output_path)
    reference_md = excel_to_markdown(reference_path)

    # ── Cell-level normalization (spaces, dates, etc.) ──
    print("[4] Applying cell-level normalization...")
    df_normalized = normalize_dataframe(df_output)

    # ── Structural normalization (column names/order) via LLM ──
    print("[5] Getting structural normalization from LLM...")
    instructions = get_structural_normalization(client, output_md, reference_md)
    print(f"   Instructions: {json.dumps(instructions, indent=2)}")
    df_normalized = apply_structural_normalization(df_normalized, instructions)

    # ── Row ordering fix ──
    print("[6] Aligning row order to reference...")
    df_ref_normalized = normalize_dataframe(df_reference)
    df_normalized = sort_dataframe_like_reference(df_normalized, df_ref_normalized)

    # ── Save normalized if requested ──
    if save_normalized:
        output_dir = os.path.dirname(output_path) or "."
        normalized_path = os.path.join(output_dir, "normalized_" + os.path.basename(output_excel))
        df_normalized.to_excel(normalized_path, index=False)
        print(f"   Saved normalized: {normalized_path}")

    normalized_md = df_normalized.fillna("").to_markdown(index=False)

    # ── Table scoring ──
    print("[7] Comparing and scoring table...")
    table_score, table_feedback = compare_and_score(client, normalized_md, reference_md, structure_type)

    # ── Text scoring ──
    text_score, text_feedback = 0.0, "No text provided."
    if output_text.strip() and reference_text.strip():
        print("[8] Scoring natural language output...")
        text_score, text_feedback = score_text(client, output_text, reference_text)

    total_score = table_score + text_score

    result = {
        "total_score": round(total_score, 2),
        "table_score": round(table_score, 2),
        "text_score": round(text_score, 2),
        "structure_type": structure_type,
        "table_feedback": table_feedback,
        "text_feedback": text_feedback,
        "instructions": instructions,
    }

    print(f"\n📊 RESULTS:")
    print(f"   Structure:   {structure_type}")
    print(f"   Table Score: {table_score:.1f} / 70")
    print(f"   Text Score:  {text_score:.1f} / 30")
    print(f"   TOTAL:       {total_score:.1f} / 100")
    print(f"   Feedback:    {table_feedback}")

    return result


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 3:
        output_file = sys.argv[1]
        reference_file = sys.argv[2]
        save_flag = "--save" in sys.argv
        result = evaluate(output_file, reference_file, save_normalized=save_flag)
    else:
        print("Usage: python evaluator_universal.py <output.xlsx> <reference.xlsx> [--save]")
        print("Example: python evaluator_universal.py test1_output.xlsx tc01_output01.xlsx --save")