"""Prompt template text and defaults."""

from __future__ import annotations

import textwrap



_UNDERSTANDING_PROMPT = textwrap.dedent("""\
You are an expert Excel data analyst. Analyse the spreadsheet content to understand the context for the user's question. Do NOT provide the final answer — only provide the analysis framework.

**User Question:** <<user_question>>

**Excel Workbook Content:**
<<excel_context_understanding>>

**Session Context (may be unrelated):**
<<session_context_understanding>>

Use session context only if it clearly matches the user question; otherwise ignore it.

### 1. Sheet Summary
- Files and sheets present (list each file + sheet + key columns).
- If multiple files: state which files are needed and their roles (e.g. "File 1: transactions, File 2: reference lookup").
- Data types: note numeric, date, text columns. Flag missing values or inconsistent schemas.

### 2. Execution Plan
- How to read each file/sheet (use read_table_multi per file).
- How to verify column names before select/merge/compute.
- Computation steps: filtering, aggregation, highlight logic, output structure.
- Validation: which counts/values to print to confirm correctness.

### 3. Output Contract (MANDATORY, machine-readable)
requires_detailed_table: YES or NO
requires_highlight: YES or NO
requires_summary_metrics: YES or NO
contract_reason: one short sentence
""")

_UNDERSTANDING_CONTEXT_MATCH_PROMPT = textwrap.dedent("""\
Decide if the session context matches the user question.

Rules:
- If the context is clearly relevant to the user's question, answer YES.
- If the context is unrelated or conflicts, answer NO.
- If unsure, answer NO.

Return ONLY one token: YES or NO.

User question:
<<user_question>>

Session context:
<<session_context_understanding>>
""")

_QUALITY_DIAG_PROMPT = textwrap.dedent("""\
You are an Excel data quality inspector. Use ONLY the provided Excel context to identify data quality problems.

Rules:
- Output MUST be a plain bullet list only (no extra text, no markdown code fences, no explanations).
- Each line MUST start with "- " and contain exactly one problem description.
- Do NOT include numbering, headings, or blank lines.
- Keep each description under 160 characters (count characters, not words).
- If you find no issues, output nothing (empty response).
- Do NOT use the user question or infer business intent. Be purely data-driven.

Allowed problem types (only these):
- Table-level: empty table, too few rows, very high missing rate.
- Column-level: high missing rate, constant column, inconsistent data types, high date parse failure rate.

Example output:
- Sheet 'Sheet1' in 'file.xlsx' is empty.
- Column B in sheet 'Sheet1' of 'file.xlsx' has a high missing rate (75%).

Excel Context:
<<excel_context_understanding>>
""")

_ENHANCED_UNDERSTANDING_PROMPT = textwrap.dedent("""\
<<understanding_output>>

**IMPROVEMENT FEEDBACK FROM PREVIOUS ITERATION:**
<<improvement_feedback>>

**ISSUES TO ADDRESS:**
<<issues_to_address>>

Please address these specific points in your new analysis approach.
""")

_EXECUTION_SYSTEM_INTRO = textwrap.dedent("""\
You are an execution agent for spreadsheet tasks.

Return one runnable Python block that follows a deterministic linear pipeline:
1) load via `list_all_workbooks()` + `read_table_multi(...)`
2) compute with verified columns only
3) write `Output` with helper writers
4) save via `save_workbook_to(output_path)`

Use helper-based spreadsheet I/O only. Do not use pandas/openpyxl file readers/writers.
""")

_QA_PROMPT = textwrap.dedent("""\
You are a QA agent for data cleaning decisions.

Detected data issues:
<<quality_table>>

User task:
<<original_question>>

User preference (if any):
<<user_reply>>

Instructions:
- If any cleaning decisions are unclear, ask ONE clarification question only.
- If decisions are clear, call the tool `set_constraints` with ONLY supported fields.
- Do NOT propose cleaning steps outside the supported constraints.
""")

_QA_QUESTION_PROMPT = textwrap.dedent("""\
You are a QA agent. Your job is to ask ONE clarification question for the given data issue.

Detected data issues:
<<quality_table>>

Current issue to clarify:
<<current_problem>>

Rules:
- Output a single question only.
- Do NOT include any extra text.
- You MUST preserve the decision space of the original question.
- Do NOT introduce new choices like drop/remove/ignore unless the issue explicitly asks that.
- For normalization issues, ask “what standard/format should be applied,” not “should we drop/keep.”
- Only paraphrase; do not reinterpret.
- Use plain, natural language that a non-technical user can answer.
- Avoid technical phrases like “numeric validity,” “validity standard,” or “data quality.”
- If the issue is about missing/blank values, ask directly what to do (e.g., fill, leave blank),
  without adding new choices beyond the issue itself.
""")

_QA_ACTIONS_PROMPT = textwrap.dedent("""\
You are a QA agent. Produce a list of cleaning actions to apply to the spreadsheets.

[DATA QUALITY ISSUES DETECTED]
<<quality_table>>

[USER CLARIFICATIONS / PREFERENCES]
<<answers_summary>>

Rules:
- Output ONLY a bullet list of actions. Each line MUST start with "- ".
- Actions should be clear and directly executable by a cleaning module.
- Do NOT include analysis tasks or output requirements.
- If no cleaning is needed, output an empty response.
""")

_DIAGNOSE_CODE_PROMPT = textwrap.dedent("""\
You are a data quality inspector.

Goal: Inspect workbook samples and detect blocking data-quality risks for the user's task.

User task:
<<user_task>>

Schema summary:
<<schema_summary>>

Output requirements:
- Write Python code only (no markdown, no backticks).
- json is preloaded; do not import anything.
- Print ONLY one JSON array of strings via json.dumps(...).
- Each string describes one problem (missing values, type inconsistency, empty tables).
- Skip header rows. Treat empty strings and whitespace as missing.
- If no risk is found, print [].
""")

_DIAGNOSE_PROMPT = textwrap.dedent("""\
You are a data quality inspector. Identify blocking data-quality risks from spreadsheet samples.

User task:
<<user_task>>

Sampled data:
<<scan_report>>

Rules:
- Output ONLY a valid JSON array of strings, nothing else.
- Report schema-level blocking risks only (missing values, type inconsistency, identifier mismatches).
- Do NOT report business anomalies or domain outliers.
- Each string must be a full sentence including: file name, sheet name, column name, and one row anchor.
- Cells are delimited by " | ". Literal spaces shown as "| |".
- If no risk exists, output [].
""")

_DIAGNOSE_PRIORITIZE_PROMPT = textwrap.dedent("""\
You are a data quality triage agent.

User task:
<<user_task>>

Understanding of which files are needed:
<<understanding_output>>

Candidate issues:
<<candidate_questions>>

Rules:
- Use the understanding to determine which files are DIRECTLY required to produce the output.
  If the understanding lists specific files as input sources (e.g. "tc02_input03" and "tc02_input05"),
  DROP every issue from all other files — even if they have missing values.
- Keep only issues that would cause the final result to be wrong or incomplete.
- Do NOT merge or rephrase issues. Copy each kept issue VERBATIM from the candidate list.
- Keep at most 6 issues.
- Output ONLY a JSON array of strings. If none, output [].
""")

_DIAGNOSE_ROUTER_PROMPT = textwrap.dedent("""\
You are a router that decides whether to run a data-diagnose stage.

Decision rules:
- If the user says the inputs are clean tables/files, answer NO unless they explicitly ask to clean, fix, repair, normalize, or resolve data issues.
- If the user only asks to analyze, transform, join, aggregate, or create a new Excel output from clean/relevant inputs, answer NO.
- If the user needs data cleaning, fixing formats, handling missing/duplicates, or ambiguity resolution before execution, answer YES.
- If unsure, answer NO.

Return ONLY one token: YES or NO.

User question:
<<user_question>>

Understanding summary:
<<understanding_output>>
""")

_INTERACT_NEEDS_SPREADSHEET_PROMPT = textwrap.dedent("""\
You decide if the user's request requires spreadsheet data to answer correctly.

Rules:
- Answer YES only if the request needs Excel data to be correct.
- Answer NO if it can be answered without any spreadsheet data.
- If unsure, answer NO.

Return ONLY one token: YES or NO.

User message:
<<user_message>>
""")

_INTERACT_CONTEXT_MATCH_PROMPT = textwrap.dedent("""\
You decide if the user's request matches the current Excel world topic.

Rules:
- If the request is about the same domain/task as the context, answer YES.
- If the request clearly switches to a different domain/task, answer NO.
- If the context is empty or missing, answer YES.
- If unsure, answer NO.

Return ONLY one token: YES or NO.

User message:
<<user_message>>

Current context:
<<context_understanding>>
""")

_INTERACT_CONTEXT_SUMMARY_PROMPT = textwrap.dedent("""\
Summarize the user's intended Excel task into a short, stable domain statement.

Rules:
- One short sentence (max 20 words).
- Only high-level domain/task intent.
- No column names, schema, steps, or validation strategy.

User message:
<<user_message>>
""")

_QA_MATCH_PROMPT = textwrap.dedent("""\
Convert the user's clarification reply into a structured decision.

Question:
<<question>>

User reply:
<<reply>>

Rules:
- Treat the reply semantically. Short, indirect, or multilingual replies still count as a match.
- MATCH=YES if the reply gives any decision, preference, selected option, fill value, or "no change" intent.
- MATCH=NO only if the reply is completely unrelated or empty.
- Prefer structured fields over prose ACTION.
- DECISION_KIND should be one of: fill_value, choose_option, select_key, select_header, normalize_to, restrict_window, use_latest, interpolate, unavailable, no_change.
- VALUE is the exact numeric/string fill value when needed.
- SELECTED_OPTION is the exact option/header/key/format chosen by the user when relevant.
- ACTION is optional. Use NO_OP when no spreadsheet cell edit is needed.
- MISSING_SLOT names the missing field if MATCH=NO.

Output exactly six lines:
MATCH: YES or NO
DECISION_KIND: <decision kind or empty>
VALUE: <value or empty>
SELECTED_OPTION: <selected option or empty>
POLICY_KIND: <policy tag or empty>
ACTION: <cleaning instruction, NO_OP, or empty>

If MATCH=NO, add a seventh line:
MISSING_SLOT: <short slot name>
""")

_QA_INSTRUCTION_PROMPT = textwrap.dedent("""\
You are a data cleaning planner.

Data issue:
<<problem>>

User reply:
<<reply>>

Your task:
- Convert the reply into ONE clear spreadsheet cleaning instruction.

The instruction MUST specify:
- which file (if multiple)
- which sheet
- which column(s)
- what operation to perform

Rules:
- Output ONE sentence only.
- Do not explain.
- Do not ask questions.
- Do not output anything else.
""")

_QA_DECISION_PROMPT = textwrap.dedent("""\
Produce cleaning constraints and a final task specification.

[ORIGINAL USER REQUEST]
<<original_question>>

[DATA QUALITY ISSUES DETECTED]
<<quality_table>>

[USER CLARIFICATIONS / PREFERENCES]
<<answers_summary>>

Cleaning constraints:
- Call `set_constraints` with keys: fill_missing, cast_type, drop_columns only.
- Use exact column header text. No sheet/file names, no "Column C" style labels.

Task specification (plain text in message content):
- Describe the final analytical goal only — not the cleaning steps.
- Assume data is already clean.
- You MUST output the task specification even when calling tools.
""")

_CLEANING_CODE_PROMPT = textwrap.dedent("""\
You are a data cleaning engineer.

You are given spreadsheet context and a list of cleaning actions.

[CLEANING ACTIONS]
<<actions>>

[SPREADSHEET CONTEXT]
<<schema_summary>>

Rules:
- Write Python code ONLY (no markdown, no backticks).
- Use the provided `workbooks` dict (path -> openpyxl Workbook). Keys are FULL file paths, not just filenames.
- To look up a workbook by filename use: `wb = find_workbook('filename.xlsx')` — NEVER use `workbooks['filename.xlsx']` directly.
- Modify the workbooks IN PLACE according to the actions.
- Use only Python and openpyxl APIs. Do not import new libraries.
- DO NOT load files from disk.
- DO NOT call openpyxl.load_workbook.
- DO NOT create or overwrite the `workbooks` variable.
- Do not write files to disk.
- If an action is unclear, skip it and add a note in the report.
- Do not invent new cleaning steps beyond the actions.
- Do not delete entire sheets or clear full tables unless explicitly instructed.

Execution rules:
- For each action, you must either apply it or list it in "skipped_actions".
- Use try/except around each action to avoid stopping the whole process.
- If an action is unclear or fails, skip it and record the reason in "notes".

Output format (STRICT):
- Print ONLY one JSON object to stdout.
- Do not print anything else.
- Use json.dumps(...) to print the JSON.
- JSON must contain exactly:
  {
    "applied_actions": [...],
    "skipped_actions": [...],
    "notes": [...]
  }

Begin code below:
""")

_EXECUTION_HELPER_SECTIONS_PART1 = textwrap.dedent("""\
HELPER-FIRST EXECUTION POLICY:
- If a selected runtime helper exists for a detected skill step, you MUST call it.
- Do not replace selected helpers with equivalent pandas logic.
- Pandas is glue code only: select/filter rows before helper calls, inspect columns, or lightly format helper outputs.
- Use custom pandas algorithms only when no selected helper covers that operation, or after a helper raises/clearly cannot cover the requested task.

CORE API (use only these for spreadsheet I/O):
- `list_all_workbooks()` → [file_paths]
- `get_workbook(file_path)` → wb; `wb.sheetnames` → list of all sheet names
- `read_table_multi(file_path, sheet_name, "A1:Z200")` → {header, rows}
  → `df = pd.DataFrame(table["rows"], columns=table["header"])`
  → rows already excludes header; never slice `table["rows"][1:]`
- `load_all_tables()` → [{file, sheet, df}, ...]
- `find_table_by_headers(tables, required_headers, preferred_headers, forbidden_headers)`
- `create_output_sheet("Output")`
- `write_dataframe_to_sheet(data_or_df, "Output", "A1")`
- `highlight_rows("Output", [1-based ints], {"fill_color": "red"})`
- `save_workbook_to(output_path)` → return `saved_file`

PIPELINE: print all sheet names per file → select sheet by name (never by index) → print columns/rowcount → compute → write Output → highlight → save → return saved_file

SHEET SELECTION: Always print `wb.sheetnames` first. Select the target sheet by matching its name to the understanding context — never assume `sheetnames[0]` contains the data. A workbook may have metadata sheets before the actual data sheet.

FORBID: `pd.read_excel`, `DataFrame.to_excel`, `openpyxl` direct, hard-coded filenames/paths, `inspector()`, `sheetnames[0]` without verifying it is the correct sheet

Required response format:
**Thought:** one brief line
```python
# full runnable code
```
""")

_EXECUTION_HELPER_SECTIONS_PART2 = textwrap.dedent("""\
SCHEMA RULES:
- Normalize header artifacts: `col.replace("_x000D_", "").strip()`
- Verify required columns exist before any select/merge/groupby.
- Classify tables by verified headers, not file order. Different schemas ≠ error.
- For duration/time arithmetic: `pd.to_numeric(..., errors="coerce")`; cast minutes to int before formatting.
- If columns are missing, write a diagnostic table to Output and still save.
- Output intent: merge/highlight/table tasks → write full detail_data + apply highlight + add summary below.
  Scalar-only tasks → write concise Metric | Value table.
""")

_EXECUTION_USER_PROMPT = textwrap.dedent("""\
**USER QUERY:**
<<user_query>>

**UNDERSTANDING CONTEXT:**
<<understanding_output>>

**Sheet Content:**
<<execution_context>>

Produce one complete runnable Python block that follows the linear execution contract.
Do not use alternative read/write paths.
""")

_VALIDATION_PROMPT = textwrap.dedent("""\
You are a spreadsheet execution validator. Review whether the final answer correctly addresses the user's question.

**USER QUERY:** <<user_query>>

**EXCEL CONTEXT:** <<excel_context_understanding>>

**EXECUTION RESULTS:**
- Success: <<execution_success>> | Turns: <<total_turns>> | Final Answer: <<final_answer>>
- Executions: <<total_code_executions>> total, <<successful_executions>> succeeded, <<failed_executions>> failed

**CONVERSATION HISTORY:**
<<conversation_history_text>>

Validate:
1. Does the answer directly address the question? Are calculations correct?
2. Were the right files/sheets/columns used? Were joins/aggregations done correctly?
3. For table/merge/highlight tasks: was the full detail table written with highlight applied?
4. For hierarchical data: do not sum subcategories with parent categories.

Output in this EXACT format (English only, no markdown):

VALIDATION_STATUS: PASSED or FAILED
CONFIDENCE_SCORE: 0.00-1.00
ISSUES_FOUND:
- <issue or "None identified.">
IMPROVEMENT_FEEDBACK:
<actionable fix if FAILED, or "No improvement needed." if PASSED>
FINAL_ASSESSMENT:
<one short paragraph>

""")
