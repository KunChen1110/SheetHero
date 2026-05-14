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

    prompt = f"""You are a lenient but fair table evaluator. Your job is to judge whether each cell in the OUTPUT conveys the same information as the corresponding cell in the REFERENCE.

{structure_hint}

**REFERENCE:**
{reference_md}

**OUTPUT:**
{normalized_md}

## Scoring philosophy — be generous, not pedantic:
You are checking if the OUTPUT *means the same thing* as the REFERENCE, not whether it looks identical.
When in doubt, lean toward giving credit.

**Full credit (1.0):**
- Same value, any formatting difference: dates, spacing, capitalisation, trailing zeros ✅
- Numbers that are close or rounded differently: "69.78" vs "69.784" ✅
- Equivalent booleans: "True" / "TRUE" / "1" / "Yes" ✅
- Empty cell where reference is "0", "0.0", or blank ✅
- Synonymous text or categories: "N/A" vs "None", "entertainment" vs "Entertainment" ✅
- Extra detail or extra words that don't change the core meaning ✅

**Partial credit (0.5):**
- Number is in the right ballpark but off by more than rounding (e.g. "68" vs "69.78") 〰️
- Correct concept but worded differently enough to be ambiguous 〰️
- Missing value where reference has a non-zero number, but surrounding context is otherwise correct 〰️

**No credit (0.0):**
- Clearly wrong number (different order of magnitude, or sign flip) ❌
- Wrong date (different day) ❌
- Wrong category or name with no relation to reference ❌
- Completely missing row/section with no equivalent ❌

## Instructions:
1. Go through each data cell (skip header rows)
2. Assign each cell a score: 1.0, 0.5, or 0.0
3. Sum the cell scores and divide by total cells, then multiply by 100
4. Score = (sum of cell scores / total_cells) * 100

Return JSON only:
{{
  "score": <float 0-100>,
  "correct": <int>,
  "partial": <int>,
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

    prompt = f"""You are a lenient but fair answer evaluator. Judge whether the OUTPUT conveys the same core meaning as the REFERENCE. Wording, phrasing, and style are irrelevant — only whether the key facts and conclusions match.

REFERENCE:
{reference_text}

OUTPUT:
{output_text}

## Scoring philosophy — be generous:
- Different phrasing of the same fact → full credit
- Same numbers expressed differently ("2 missing" vs "two missing entries") → full credit
- Correct facts with extra detail or context → full credit
- Approximately correct facts (right concept, slightly imprecise) → mostly full credit
- A key fact is missing but everything else is right → small deduction only
- A fact is wrong but it's minor or peripheral → small deduction only
- Reserve heavy penalties for cases where a central conclusion is outright wrong

Start from 100 and make only small, justified deductions.

Return JSON only:
{{"score": <float 0-100>, "feedback": "<brief explanation — what was correct, what (if anything) was missing or wrong>"}}"""

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