"""Offline/local prompt texts.

Prompt definitions dedicated to offline / locally deployed LLMs.

Design:
- Online/default prompt building blocks live in `prompt_texts_online.py`.
- This module focuses on composing stricter, verification‑heavy variants for offline models.
- The goal is to provide a separate prompt surface for local LLMs without changing online behavior.
"""

from __future__ import annotations

import textwrap

from .prompt_texts_online import (
    _UNDERSTANDING_PROMPT,
    _EXECUTION_SYSTEM_INTRO,
    _EXECUTION_HELPER_SECTIONS_PART1,
    _EXECUTION_HELPER_SECTIONS_PART2,
    _EXECUTION_USER_PROMPT,
    _VALIDATION_PROMPT,
)


# ========== Offline-only building blocks ==========

# Offline-only: short suffix to encourage verify-before-infer (minimal).
_UNDERSTANDING_VERIFY_BEFORE_INFER_OFFLINE = (
    "\n\n**Note:** Base analysis on observed data (column values, ranges, keys)—"
    "do not infer meaning from filenames or file order."
)

# Offline/local only: strict code-only format, bounded generation (no free-form reasoning).
_EXECUTION_RESPONSE_FORMAT_OFFLINE = textwrap.dedent("""
**RESPONSE FORMAT - MANDATORY (CODE-ONLY, BOUNDED OUTPUT):**

Reply with **ONLY** the following format and NOTHING ELSE. No natural language reasoning, no extra markdown, no explanations before or after the code block.

```python
# Your Python code here
```

REQUIREMENTS FOR THE CODE:
- MUST:
  - Read the necessary Excel workbook(s) using ONLY the provided helper functions (e.g., list_all_workbooks(), inspector(), inspector_multi(), etc.).
  - Perform all required analysis/calculations in Python.
  - Write BOTH:
    * a detailed data table (all relevant rows) starting at A1 of an Output sheet, and
    * a summary statistics block below the detailed table (with at least 2 blank rows of separation).
  - Save the workbook using `save_workbook_to(output_path)`.
  - Make the **last expression** in the code evaluate to the saved file path, for example:
    ```python
    saved_file = save_workbook_to(output_path)
    saved_file
    ```
- MUST NOT:
  - Return only a textual final answer (e.g., "Final Answer: £72.28").
  - Use hardcoded absolute paths to the Excel input files; always discover them via `list_all_workbooks()` or other provided context variables.
  - Include any additional markdown, comments, or prose outside the single Python code block.
""")

# Offline-only: detailed guardrails + mandatory execution checklist to reduce hallucination.
_EXECUTION_GUARDRAILS_OFFLINE = textwrap.dedent("""
**GUARDRAILS (MANDATORY for local execution):**

1. **Verify before infer:** Before using any semantic assumptions (e.g., grouping by date/month/category, file meaning), inspect the relevant column(s) and confirm actual values/ranges present. State facts based on observed data, not on filenames or file order.

2. **Tool-first, no invented resources:** Always obtain workbook paths via `list_all_workbooks()`; never hardcode or invent filenames/paths. Prefer `inspector()` / `inspector_multi()` and other provided helpers for I/O. Do not use pandas with invented paths; only real paths from `list_all_workbooks()`.

3. **Minimal patch error-fixing (high level):** When execution fails (traceback), fix only the smallest necessary part (variable/column name/type conversion/range). Do not introduce new helper functions, new filenames, or generic example datasets. Keep the next response short and directly targeted to the reported error.

---

**OFFLINE EXECUTION 6-STEP CHECKLIST (MANDATORY – CODE MUST IMPLEMENT THESE STEPS WITH PRINTS):**

(1) **Workbook inventory (must run first)**
- Call `list_all_workbooks()` and **print** the returned list of file paths.
- For each workbook, list and **print** its sheet names (inventory of files + sheets).

(2) **Table boundary detection**
- For each relevant file/sheet, call `inspector_multi(file_path, "A1:Z30", sheet_name)` (or an appropriate small window) to inspect the header area.
- Explicitly determine and document (in comments or prints):
  - Which row is the header row.
  - The approximate data region (start/end rows and columns).
- Do **not** assume header position or range without inspecting real data.

(3) **Schema resolution (Column Resolution – MANDATORY)**
- Build DataFrames from the inspected ranges and **print** `df.columns` for each table.
- Normalize column names for matching:
  - Lowercase.
  - Strip leading/trailing spaces.
  - Remove punctuation such as `£`, `()`, `_`, `-`, and spaces.
- Resolve required logical columns via alias candidates:
  - Date: `["date", "day", "transactiondate", "spenddate"]`
  - Category: `["category", "type", "class", "group"]`
  - Amount: `["dailyspending", "spending", "amount", "cost", "expense", "value"]`
  - Notes: `["notes", "memo", "remark", "comment", "description"]`
- If any **required** logical column (Date / Amount) cannot be resolved from actual `df.columns`:
  - **Print** the full `df.columns` and a small header preview.
  - **STOP** – do not continue calculations or invent column names.

(4) **Type & sanity checks**
- For date-like columns:
  - Use `pd.to_datetime(..., errors="coerce")` and assign back to the DataFrame.
- For numeric measure columns (e.g., spending/amount):
  - Use `pd.to_numeric(..., errors="coerce")`.
- For each key column used in later logic:
  - **Print** NA count and NA ratio.
  - **Print** min/max for:
    - Date columns (overall date range).
    - Numeric amount columns (value range).

(5) **Merge / concat coverage proof**
- Before any `pd.concat` or `pd.merge`, **print** for each input DataFrame:
  - `len(df_i)` (row count) and the resolved key columns.
- After combining:
  - **Print** `len(combined)` and `len(df1) + len(df2)` (or the appropriate sum across all inputs).
  - For time-series tasks (e.g., daily spending):
    - For the final combined DataFrame, after parsing Date:
      - **Print** `combined["date"].min()`, `combined["date"].max()`.
      - **Print** `combined["date"].nunique()` and total row count.
      - **Print** duplicate-date count via `combined["date"].duplicated().sum()`.
      - If `(max_date - min_date).days + 1 != nunique_dates`, **print a warning** and (if feasible) list or summarize missing dates.

(6) **Output writing (must follow unified pattern)**
- The Output sheet **must**:
  - First contain the **detailed data table** (all merged rows) starting at `A1`.
  - Then, after at least 2 blank rows, contain the **summary statistics** block.
- Use only:
  - `create_output_sheet()` to create/clear the output sheet.
  - `write_dataframe_to_sheet()` for writing 2D list data.
  - `save_workbook_to(output_path)` to save; **do not** use other save methods.
- Ensure that any important intermediate coverage/validation prints remain in the code (do not remove them after debugging).

---

**Missing Value Policy (MANDATORY for numeric fields)**

- For key numeric fields used in aggregation (e.g., spending/amount columns):
  1. **Print** NA count and NA ratio **before** any cleaning.
  2. **Default policy:** exclude NA for that metric when computing sums/means
     (e.g., use `dropna` or `skipna=True` on that metric only),
     **unless** the user question explicitly states “treat missing as 0”.
  3. If dropping NA rows for the metric changes the number of rows in the working DataFrame:
     - **Print** row counts before and after filtering.
- For text/comment/notes-like fields:
  - Keep NA as empty string or `None` when writing output; do not try to fill with invented text.

---

**Date coverage & ordering checks (MANDATORY for time-series style tasks)**

- After converting the resolved Date column to datetime:
  - **Print**:
    - `min_date`, `max_date`.
    - `nunique_dates` (number of unique dates).
    - total row count.
    - number of duplicated dates.
  - For daily-series questions (e.g., “整个 11 月的每日消费统计”):
    - Compute `expected_days = (max_date - min_date).days + 1`.
    - If `expected_days != nunique_dates`, **print** that coverage is incomplete and
      list or summarize missing days (at least print the fact, do not silently ignore).
  - Always `sort_values` by Date (and additional keys if necessary) before final aggregation/output.

---

**Allowed Fixes After Traceback (ONLY these – strict minimal patch policy)**

After any error/traceback, you may only apply fixes in these categories, and you **must** reuse the previously printed diagnostics (columns, dtypes, NA stats, inventory, etc.) instead of guessing:

1. **KeyError / missing column**
   - Print available `df.columns`.
   - Resolve to the correct column using the alias mapping in the **Schema resolution** step.
   - Do **not** invent new column names or silently change logic.

2. **TypeError / ValueError (type conversion / parsing)**
   - Apply coercion using `to_numeric(..., errors="coerce")` or `to_datetime(..., errors="coerce")`.
   - Print NA counts before/after coercion for the affected columns.

3. **Wrong range / header position**
   - Expand or adjust the `inspector` / `inspector_multi` range.
   - Re-detect header row and rebuild the DataFrame accordingly.
   - Re-print the new header preview and `df.columns`.

4. **NaN-related issues (aggregation / operations)**
   - Apply the **Missing Value Policy** above.
   - Print before/after row counts and NA stats for the affected metric columns.

5. **Multi-file / multi-sheet misread**
   - Re-run the workbook inventory (`list_all_workbooks()` + sheet listing).
   - Use `inspector_multi` with explicit file path + sheet name to re-read.
   - Re-print row counts per file/sheet and perform coverage checks again.

Any fix outside these categories (e.g., large refactors, new helper abstractions, invented filenames/paths, or mock data generation) is **prohibited**. Keep every fix as a minimal, local adjustment guided by actual printed diagnostics.
""")


def _replace_online_response_format_block(part1_text: str) -> str:
    """Swap the online response-format block with the stricter offline block.

    This is intentionally marker-based (not exact full-block matching),
    so minor online prompt edits won't silently break offline replacement.
    """
    start_markers = (
        "**RESPONSE FORMATS - MANDATORY COMPLIANCE:**",
        "**RESPONSE FORMAT - MANDATORY (CODE-ONLY):**",
    )
    end_marker = "**IMPORTANT GUIDELINES:**"

    start_idx = -1
    for marker in start_markers:
        idx = part1_text.find(marker)
        if idx != -1:
            start_idx = idx
            break

    if start_idx == -1:
        return _EXECUTION_RESPONSE_FORMAT_OFFLINE.strip() + "\n\n" + part1_text

    end_idx = part1_text.find(end_marker, start_idx)
    if end_idx == -1:
        return part1_text[:start_idx] + _EXECUTION_RESPONSE_FORMAT_OFFLINE.strip()

    return (
        part1_text[:start_idx]
        + _EXECUTION_RESPONSE_FORMAT_OFFLINE.strip()
        + "\n\n"
        + part1_text[end_idx:]
    )


_EXECUTION_HELPER_SECTIONS_PART1_OFFLINE = (
    _replace_online_response_format_block(_EXECUTION_HELPER_SECTIONS_PART1).strip()
    + "\n\n"
    + _EXECUTION_GUARDRAILS_OFFLINE.strip()
)

_OFFLINE_MERGE_PLAYBOOK = textwrap.dedent("""
### Offline Merge / Concat Playbook (MANDATORY)

1. **Decide relationship type (concat vs merge)**
- If input tables share the same normalized schema and represent different time ranges / batches of the **same kind of records**, you should use `pd.concat`.
- If input tables share one or more key columns but have **complementary** fields (e.g., student base info and scores), you should use `pd.merge`.
- You **must** explicitly state in comments/prints which relationship you chose and why.

2. **Checklist before `pd.concat`**
- After schema normalization (see Column Resolution in guardrails), **assert** that:
  - The normalized column sets for all input DataFrames are identical.
  - If not identical, **print** the difference for each side and decide whether:
    - To align columns explicitly (e.g., add missing columns with NA), or
    - To stop and report schema mismatch instead of concatenating blindly.
- After concatenation:
  - `combined = pd.concat([...], ignore_index=True)` (usually with `ignore_index=True`).
  - Immediately **sort** by the main key(s) (e.g., Date or ID) and **print**:
    - Row counts of each input.
    - Row count of the combined DataFrame.

3. **Checklist before `pd.merge`**
- Clearly identify join key column(s) from **actual** `df.columns` (after alias resolution) – never invent key names.
- For each input DataFrame:
  - **Print** key column name(s).
  - **Print** duplicate ratio via `df[key].duplicated().mean()` or a similar metric.
- Choose join type (`how="inner"`, `"left"`, `"right"`, `"outer"`) and briefly justify:
  - Example: `"inner"` to keep only matching IDs; `"left"` to keep all records from the main table.
- After merge:
  - **Print** the input row counts, merged row count, and (where applicable) the number of unmatched keys on each side (for left/right/outer joins).

4. **Post-merge / post-concat coverage proof**
- For the final combined DataFrame:
  - Re-run key coverage checks appropriate to the task:
    - For ID-like keys: unique key count, duplicated key count.
    - For Date-based tasks: use the **Date coverage & ordering checks** from the guardrails.
  - Re-check NA statistics on key metric columns (e.g., spending/amount) and apply the **Missing Value Policy** if new NA values appear after the join.

All merge/concat operations in offline mode **must** follow this playbook, with minimal `print` statements that show the decisions and coverage checks.
""")


# ========== Understanding stage ==========

# Offline understanding prompt:
# extend the base understanding prompt with a "verify before infer" suffix,
# to constrain smaller local models (7B/14B, etc.) and reduce hallucinations.
UNDERSTANDING_PROMPT_OFFLINE: str = (
    _UNDERSTANDING_PROMPT + _UNDERSTANDING_VERIFY_BEFORE_INFER_OFFLINE
)


# ========== Execution stage ==========

# Offline system-level prompt:
# - Reuse the original environment intro `_EXECUTION_SYSTEM_INTRO`.
# - Swap in the offline-specific helper + guardrail section `_EXECUTION_HELPER_SECTIONS_PART1_OFFLINE`.
# - Append the existing multi-file/multi-sheet guidelines `_EXECUTION_HELPER_SECTIONS_PART2`.
EXECUTION_SYSTEM_PROMPT_OFFLINE: str = (
    _EXECUTION_SYSTEM_INTRO
    + "\n\n"
    + _EXECUTION_HELPER_SECTIONS_PART1_OFFLINE
    + "\n\n"
    + _EXECUTION_HELPER_SECTIONS_PART2
    + "\n\n"
    + _OFFLINE_MERGE_PLAYBOOK
)

# User-facing execution prompt: keep the same structure as online mode,
# but pair it with the stricter offline system prompt defined above.
EXECUTION_USER_PROMPT_OFFLINE: str = _EXECUTION_USER_PROMPT


# ========== Validation stage ==========

# Validation prompt is shared between online and offline;
# different models can call it with the same template.
VALIDATION_PROMPT_OFFLINE: str = _VALIDATION_PROMPT
