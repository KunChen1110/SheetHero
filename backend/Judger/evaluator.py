"""
evaluator.py — main entry point for the SheetHero evaluator.

Usage:
  python evaluator.py "Test 1"
  python evaluator.py output.xlsx reference.xlsx
  python evaluator.py "Test 1" [--dataset path/to/dataset.json] [--logger path/to/logger.md] [--save]
"""

import json
import os
import pandas as pd
from openai import OpenAI

from loader import load_task_from_dataset, extract_output_from_logger, find_latest_logger, find_dataset
from normalizer import find_file, excel_to_markdown, detect_structure, normalize_dataframe, get_structural_normalization, apply_structural_normalization
from scorer import compare_and_score, score_text, decide_weights

API_KEY = ""   # replace with your key


def evaluate(
        output_excel: str,
        reference_excel: str,
        output_text: str = "",
        reference_text: str = "",
        save_normalized: bool = False,
) -> dict:
    """
    Evaluate output vs reference Excel. Optionally scores text too.
    Returns result dict with total_score (0-100) and full breakdown.
    """
    client = OpenAI(api_key=API_KEY)

    output_path = find_file(output_excel)
    reference_path = find_file(reference_excel)

    print(f"\nEvaluating:")
    print(f"  Output:    {output_path}")
    print(f"  Reference: {reference_path}")

    print("\n[1] Loading Excel files...")
    df_output = pd.read_excel(output_path)
    df_reference = pd.read_excel(reference_path)
    print(f"   Output shape:    {df_output.shape}")
    print(f"   Reference shape: {df_reference.shape}")

    print("[2] Detecting table structure...")
    structure_type = detect_structure(df_output)
    print(f"   Structure type: {structure_type}")

    print("[3] Converting to Markdown...")
    output_md = excel_to_markdown(output_path)
    reference_md = excel_to_markdown(reference_path)

    print("[4] Deciding table vs text weights...")
    weights = decide_weights(client, reference_md, reference_text)
    table_weight = weights["table_weight"]
    text_weight = weights["text_weight"]
    print(f"   Table weight: {table_weight:.0%}  |  Text weight: {text_weight:.0%}")
    print(f"   Reason: {weights['reasoning']}")

    print("[5] Applying cell-level normalization...")
    df_normalized = normalize_dataframe(df_output)

    print("[6] Getting structural normalization from LLM...")
    instructions = get_structural_normalization(client, output_md, reference_md)
    print(f"   Instructions: {json.dumps(instructions, indent=2)}")
    df_normalized = apply_structural_normalization(df_normalized, instructions)

    if save_normalized:
        output_dir = os.path.dirname(output_path) or "."
        normalized_path = os.path.join(output_dir, "normalized_" + os.path.basename(output_excel))
        df_normalized.to_excel(normalized_path, index=False)
        print(f"   Saved normalized: {normalized_path}")

    normalized_md = df_normalized.fillna("").to_markdown(index=False)

    print("[7] Scoring table...")
    table_raw, table_feedback = compare_and_score(client, normalized_md, reference_md, structure_type)
    table_score = round(table_raw * table_weight, 2)

    text_raw, text_feedback = 0.0, "No text provided."
    text_score = 0.0
    if output_text.strip() and reference_text.strip():
        print("[8] Scoring text...")
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
    print(f"   Text feedback: {text_feedback}")

    return result


def evaluate_task(
        task_id: str,
        logger_path: str,
        dataset_path: str = "dataset.json",
        output_excel: str = "",
        save_normalized: bool = False,
) -> dict:
    """Evaluate a task automatically using dataset.json + logger file."""
    print(f"\nLoading task '{task_id}' from dataset...")
    task = load_task_from_dataset(task_id, dataset_path)

    reference_text = task.get("answer", "")
    reference_excel = (task.get("expected_output_file") or [""])[0]

    print(f"   Reference text:  {repr(reference_text[:80])}")
    print(f"   Reference Excel: {reference_excel}")

    print(f"\nParsing logger: {logger_path}")
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

    return evaluate(output_excel, reference_excel, output_text, reference_text, save_normalized)


if __name__ == "__main__":
    import sys

    args = sys.argv[1:]
    save_flag = "--save" in args

    if len(args) >= 1 and not args[0].endswith(".xlsx"):
        task_id = args[0]
        dataset_path = args[args.index("--dataset") + 1] if "--dataset" in args else find_dataset()
        logger_path = args[args.index("--logger") + 1] if "--logger" in args else find_latest_logger(task_id)
        print(f"   Using logger:  {os.path.basename(logger_path)}")
        print(f"   Using dataset: {dataset_path}")
        result = evaluate_task(task_id, logger_path, dataset_path=dataset_path, save_normalized=save_flag)

    elif len(args) >= 2:
        result = evaluate(args[0], args[1], save_normalized=save_flag)

    else:
        print("Usage:")
        print('  Simple:  python evaluator.py "Test 1"')
        print("  Manual:  python evaluator.py output.xlsx reference.xlsx")
        print("  Options: [--dataset path/to/dataset.json] [--logger path/to/logger.md] [--save]")