"""
Universal Table Evaluator

Usage:
  # Recommended: evaluate by task ID, reads everything automatically
  result = evaluate_task("Test 1", "artifacts/logger/sheethero_tc01_xxx.md", dataset_path="dataset.json")

  # Manual: pass everything explicitly
  result = evaluate("test1_output.xlsx", "tc01_output01.xlsx", output_text="...", reference_text="...")
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
# Dataset + logger loaders
# ──────────────────────────────────────────────

def load_task_from_dataset(task_id: str, dataset_path: str) -> dict:
    """Load a task entry from dataset.json by task_id e.g. 'Test 1'."""
    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)
    for entry in dataset:
        if entry.get("task_id", "").strip().lower() == task_id.strip().lower():
            return entry
    raise ValueError(f"Task '{task_id}' not found in {dataset_path}")


def extract_output_from_logger(logger_path: str) -> dict:
    """
    Parse a SheetHero logger .md file and extract:
      - output_text:  Short Answer (new format) or last meaningful Final Answer (old format)
      - output_excel: the saved output .xlsx path

    New format has: 'Short Answer: <summary>'
    Old format has: 'Final Answer: <text or file path>'
    """
    output_text = ""
    output_excel = ""

    with open(logger_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for line in lines:
        stripped = line.strip()

        # New format: Short Answer is always the human-readable summary
        if stripped.startswith("Short Answer:"):
            output_text = stripped.split(":", 1)[1].strip()

        # Both formats: grab Excel file path from Final Answer line
        if stripped.startswith("Final Answer:"):
            value = stripped.split(":", 1)[1].strip()
            if value.lower().endswith(".xlsx") or value.lower().endswith(".xls"):
                output_excel = value
            elif not output_text and not os.path.splitext(value)[1]:
                # Old format fallback: use as text if it is not a file path
                output_text = value

    return {"output_text": output_text, "output_excel": output_excel}


def evaluate_task(
        task_id: str,
        logger_path: str,
        dataset_path: str = "dataset.json",
        output_excel: str = "",
        save_normalized: bool = False,
) -> dict:
    """
    Evaluate a SheetHero task automatically from the logger and dataset.json.

    Args:
        task_id:         e.g. "Test 1", "Test 22"
        logger_path:     path to the SheetHero logger .md file
        dataset_path:    path to dataset.json (default: "dataset.json")
        output_excel:    override the output Excel path (optional)
        save_normalized: save the normalized Excel for inspection

    Returns: result dict with total_score, table_score, text_score, feedback etc.
    """
    print(f"\n Loading task '{task_id}' from dataset...")
    task = load_task_from_dataset(task_id, dataset_path)

    reference_text = task.get("answer", "")
    reference_excel_list = task.get("expected_output_file", [])
    reference_excel = reference_excel_list[0] if reference_excel_list else ""

    print(f"   Reference text:  {repr(reference_text[:80])}")
    print(f"   Reference Excel: {reference_excel}")

    print(f"\n Parsing logger: {logger_path}")
    parsed = extract_output_from_logger(logger_path)
    output_text = parsed["output_text"]
    if not output_excel:
        output_excel = parsed["output_excel"]

    print(f"   Output text:  {repr(output_text[:80])}")
    print(f"   Output Excel: {output_excel}")

    if not reference_excel:
        raise ValueError(f"No expected_output_file in dataset for task '{task_id}'")
    if not output_excel:
        raise ValueError(f"Could not find output Excel path in logger: {logger_path}")

    return evaluate(
        output_excel=output_excel,
        reference_excel=reference_excel,
        output_text=output_text,
        reference_text=reference_text,
        save_normalized=save_normalized,
    )


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
    Semantically compare output vs reference and return a raw score 0-100.
    The LLM judges whether each cell expresses the SAME INFORMATION as the reference,
    regardless of formatting differences. Weighting is applied externally.
    """

    structure_hint = {
        "flat": "This is a flat table.",
        "data_with_metrics": "This table has a data section and a metrics/summary section at the bottom.",
        "multi_section": "This table has multiple sections, each with their own headers and data.",
    }.get(structure_type, "")

    prompt = f"""You are an intelligent table evaluator. Your job is to judge whether each cell in the OUTPUT expresses the SAME INFORMATION as the corresponding cell in the REFERENCE — regardless of formatting.

{structure_hint}

**REFERENCE:**
{reference_md}

**OUTPUT:**
{normalized_md}

## Your evaluation philosophy:
You are checking if the OUTPUT *means the same thing* as the REFERENCE, not whether it looks identical.

These should be treated as CORRECT (full credit):
- Same date in different formats: "2025-11-08" vs "2025-11-08 00:00:00" ✅
- Same number rounded differently: "69.78" vs "69.784483" ✅
- Same text with different spacing: "I23" vs "I 23" ✅
- Same boolean: "True" vs "TRUE" vs "1" ✅
- Same category with different capitalisation: "entertainment" vs "Entertainment" ✅
- Empty cell vs "0" or "0.0" when context implies zero ✅

These should be treated as WRONG (no credit):
- Genuinely different numbers: "72.28" vs "69.78" ❌
- Different dates that are not the same day ❌
- Different names or categories ❌
- Missing value when reference has a real value (and context does not imply zero) ❌

## Instructions:
1. Go through each data cell (skip header rows)
2. For each cell, judge: does the OUTPUT cell express the same information as the REFERENCE cell?
3. Count: correct (same meaning) vs wrong (genuinely different or missing)
4. Score = (correct / total_cells) * 100

Return JSON only:
{{
  "score": <float 0-100>,
  "correct": <int>,
  "wrong": <int>,
  "total_cells": <int>,
  "feedback": "<brief list of the main genuine errors found, if any>"
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

    prompt = f"""You are an intelligent answer evaluator. Judge whether the OUTPUT conveys the same information as the REFERENCE — wording and phrasing do not matter, only meaning.

REFERENCE:
{reference_text}

OUTPUT:
{output_text}

Your evaluation philosophy:
- Different phrasing of the same fact = full credit
- Same numbers expressed differently (e.g. "2 missing" vs "two missing entries") = full credit
- Correct facts with extra detail = full credit
- Missing key facts = lose points
- Wrong facts = lose points

Score out of 100 based on how much of the reference meaning is correctly captured.

Return JSON only:
{{"score": <float 0-100>, "feedback": "<brief explanation of what was correct or missing>"}}"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        response_format={"type": "json_object"}
    )
    result = json.loads(response.choices[0].message.content)
    return float(result["score"]), result.get("feedback", "")


# ──────────────────────────────────────────────
# Step 5: Decide weights dynamically
# ──────────────────────────────────────────────

def decide_weights(client, reference_md: str, reference_text: str) -> dict:
    """
    Dynamically decide how much weight to give table vs text (must sum to 1.0).
    Based on how much meaningful information each part contains.
    """
    has_table = bool(reference_md.strip())
    has_text = bool(reference_text.strip())

    if has_table and not has_text:
        return {"table_weight": 1.0, "text_weight": 0.0, "reasoning": "No text output - table is 100% of score."}
    if has_text and not has_table:
        return {"table_weight": 0.0, "text_weight": 1.0, "reasoning": "No table output - text is 100% of score."}

    prompt = (
            "You are deciding how to split 100 scoring points between two parts of an answer.\n\n"
            "**Reference TABLE:**\n" + reference_md + "\n\n"
                "**Reference TEXT:**\n" + reference_text + "\n\n"
                    "Decide the weight for each part (must sum to 1.0) based on:\n"
                    "- How much meaningful information each part contains\n"
                    "- Which part is the main deliverable\n"
                    "- If text is just a short confirmation or file path -> low weight (0.1)\n"
                    "- If table is large and detailed -> high weight (0.8-0.9)\n"
                    "- If text has unique insights not in table -> higher text weight\n"
                    "Minimum weight for either part: 0.1\n\n"
                    'Return JSON only: {"table_weight": <float>, "text_weight": <float>, "reasoning": "<one sentence>"}'
    )

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        response_format={"type": "json_object"}
    )
    result = json.loads(response.choices[0].message.content)
    tw = max(0.1, float(result.get("table_weight", 0.7)))
    xw = max(0.1, float(result.get("text_weight", 0.3)))
    total = tw + xw
    return {
        "table_weight": round(tw / total, 3),
        "text_weight": round(xw / total, 3),
        "reasoning": result.get("reasoning", "")
    }


# ──────────────────────────────────────────────
# Main evaluate()
# ──────────────────────────────────────────────

def evaluate(
        output_excel: str,
        reference_excel: str,
        output_text: str = "",
        reference_text: str = "",
        save_normalized: bool = False,
) -> dict:
    """
    Universal evaluation function. Works for any table structure.
    Weights between table and text are decided dynamically based on content importance.
    Returns dict with total_score (0-100) and full breakdown.
    """
    client = OpenAI(api_key=API_KEY)

    output_path = find_file(output_excel)
    reference_path = find_file(reference_excel)

    print(f"\nEvaluating:")
    print(f"  Output:    {output_path}")
    print(f"  Reference: {reference_path}")

    # Load
    print("\n[1] Loading Excel files...")
    df_output = pd.read_excel(output_path)
    df_reference = pd.read_excel(reference_path)
    print(f"   Output shape:    {df_output.shape}")
    print(f"   Reference shape: {df_reference.shape}")

    # Detect structure
    print("[2] Detecting table structure...")
    structure_type = detect_structure(df_output)
    print(f"   Structure type: {structure_type}")

    # Convert to markdown
    print("[3] Converting to Markdown...")
    output_md = excel_to_markdown(output_path)
    reference_md = excel_to_markdown(reference_path)

    # Decide weights dynamically
    print("[4] Deciding table vs text weights...")
    weights = decide_weights(client, reference_md, reference_text)
    table_weight = weights["table_weight"]
    text_weight = weights["text_weight"]
    print(f"   Table weight: {table_weight:.0%}  |  Text weight: {text_weight:.0%}")
    print(f"   Reason: {weights['reasoning']}")

    # Cell-level normalization
    print("[5] Applying cell-level normalization...")
    df_normalized = normalize_dataframe(df_output)

    # Structural normalization via LLM
    print("[6] Getting structural normalization from LLM...")
    instructions = get_structural_normalization(client, output_md, reference_md)
    print(f"   Instructions: {json.dumps(instructions, indent=2)}")
    df_normalized = apply_structural_normalization(df_normalized, instructions)

    # Save normalized if requested
    if save_normalized:
        output_dir = os.path.dirname(output_path) or "."
        normalized_path = os.path.join(output_dir, "normalized_" + os.path.basename(output_excel))
        df_normalized.to_excel(normalized_path, index=False)
        print(f"   Saved normalized: {normalized_path}")

    normalized_md = df_normalized.fillna("").to_markdown(index=False)

    # Table scoring: raw score out of 100, then apply weight
    print("[7] Comparing and scoring table...")
    table_raw, table_feedback = compare_and_score(client, normalized_md, reference_md, structure_type)
    table_score = round(table_raw * table_weight, 2)

    # Text scoring: raw score out of 100, then apply weight
    text_raw, text_feedback = 0.0, "No text provided."
    text_score = 0.0
    if output_text.strip() and reference_text.strip():
        print("[8] Scoring natural language output...")
        text_raw, text_feedback = score_text(client, output_text, reference_text)
        text_score = round(text_raw * text_weight, 2)

    total_score = round(table_score + text_score, 2)

    result = {
        "total_score": total_score,
        "table_score": table_score,
        "text_score": text_score,
        "table_raw": round(table_raw, 2),
        "text_raw": round(text_raw, 2),
        "table_weight": table_weight,
        "text_weight": text_weight,
        "weight_reasoning": weights["reasoning"],
        "structure_type": structure_type,
        "table_feedback": table_feedback,
        "text_feedback": text_feedback,
    }

    print(f"\n📊 RESULTS:")
    print(f"   Structure:    {structure_type}")
    print(f"   Table weight: {table_weight:.0%}  |  Text weight: {text_weight:.0%}")
    print(f"   Table:  {table_raw:.1f}/100 raw  ->  {table_score:.1f} weighted pts")
    print(f"   Text:   {text_raw:.1f}/100 raw  ->  {text_score:.1f} weighted pts")
    print(f"   TOTAL:  {total_score:.1f} / 100")
    print(f"   Table feedback: {table_feedback}")

    return result




# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def find_latest_logger(task_id: str) -> str:
    """
    Find the most recent logger .md file for a given task.
    Searches common logger directories for files containing the task input name.
    e.g. task_id "Test 1" -> looks for files containing "tc01"
    """
    # Map task number to input file prefix e.g. "Test 1" -> "tc01"
    match = re.search(r"\d+", task_id)
    if match:
        num = int(match.group())
        prefix = f"tc{num:02d}"
    else:
        prefix = ""

    script_dir = os.path.dirname(os.path.abspath(__file__))
    search_dirs = [
        os.path.join(script_dir, "../../artifacts/loggers"),
        os.path.join(script_dir, "../../artifacts/logger"),
        os.path.join(script_dir, "../../artifacts/logs"),
        os.path.join(script_dir, "artifacts/loggers"),
        os.path.join(script_dir, "artifacts/logger"),
        os.path.join(script_dir, "artifacts/logs"),
        "artifacts/loggers",
        "artifacts/logger",
        "artifacts/logs",
    ]

    candidates = []
    for d in search_dirs:
        if not os.path.isdir(d):
            continue
        for fname in os.listdir(d):
            if fname.endswith(".md") and (not prefix or prefix in fname.lower()):
                candidates.append(os.path.join(d, fname))

    if not candidates:
        raise FileNotFoundError(
            f"No logger file found for task '{task_id}' (looked for files containing '{prefix}' in logger dirs)"
        )

    # Return the most recently modified one
    return max(candidates, key=os.path.getmtime)


def find_dataset(start_dir: str = ".") -> str:
    """Search upward for dataset.json."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    search_paths = [
        os.path.join(script_dir, "dataset.json"),
        os.path.join(script_dir, "../../dataset/dataset.json"),
        os.path.join(script_dir, "../dataset/dataset.json"),
        "dataset.json",
    ]
    for p in search_paths:
        if os.path.exists(p):
            return p
    raise FileNotFoundError("dataset.json not found. Pass --dataset <path> to specify it.")


if __name__ == "__main__":
    import sys

    args = sys.argv[1:]
    save_flag = "--save" in args

    # Simple usage: python evaluator_universal.py "Test 1"
    # Finds the latest logger and dataset.json automatically
    if len(args) >= 1 and not args[0].endswith(".xlsx"):
        task_id = args[0]

        # Allow optional --dataset override
        dataset_path = None
        if "--dataset" in args:
            dataset_path = args[args.index("--dataset") + 1]
        else:
            dataset_path = find_dataset()

        # Allow optional explicit logger path
        logger_path = None
        if "--logger" in args:
            logger_path = args[args.index("--logger") + 1]
        else:
            logger_path = find_latest_logger(task_id)
            print(f"   Using logger: {os.path.basename(logger_path)}")

        result = evaluate_task(task_id, logger_path, dataset_path=dataset_path, save_normalized=save_flag)

    # Manual mode: python evaluator_universal.py output.xlsx reference.xlsx
    elif len(args) >= 2:
        result = evaluate(args[0], args[1], save_normalized=save_flag)

    else:
        print("Usage:")
        print("  Simple:  python evaluator_universal.py \"Test 1\"")
        print("  Manual:  python evaluator_universal.py output.xlsx reference.xlsx")
        print("  Options: [--dataset path/to/dataset.json] [--logger path/to/logger.md] [--save]")