"""
scorer.py — LLM-based scoring for tables and text.
"""

import json
from openai import OpenAI

MODEL = "gpt-4o-mini"


def compare_and_score(client: OpenAI, normalized_md: str, reference_md: str, structure_type: str) -> tuple:
    """
    Semantically compare output vs reference table and return (score 0-100, feedback).
    The LLM judges whether each cell expresses the SAME INFORMATION as the reference,
    regardless of formatting differences.
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


def score_text(client: OpenAI, output_text: str, reference_text: str) -> tuple:
    """
    Semantically score the natural language output against the reference (0-100, feedback).
    Only meaning matters, not exact wording.
    """
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


def decide_weights(client: OpenAI, reference_md: str, reference_text: str) -> dict:
    """
    Dynamically decide table vs text weight (must sum to 1.0).
    If only one part exists, it gets 100%.
    """
    has_table = bool(reference_md.strip())
    has_text = bool(reference_text.strip())

    if has_table and not has_text:
        return {"table_weight": 1.0, "text_weight": 0.0, "reasoning": "No text output — table is 100% of score."}
    if has_text and not has_table:
        return {"table_weight": 0.0, "text_weight": 1.0, "reasoning": "No table output — text is 100% of score."}

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