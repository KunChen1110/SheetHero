"""Prompt template text and defaults."""

from __future__ import annotations

import textwrap



_UNDERSTANDING_PROMPT = textwrap.dedent("""\
You are an expert Excel data analyst. I need you to analyze the spreadsheet content and visual representation (if provided) to understand the context for answering a specific question.

**User Question:** <<user_question>>

**Excel Workbook Content:**
<<excel_context_understanding>>

**Session Context (may be unrelated):**
<<session_context_understanding>>

**Your Task:**
Analyze the Excel content and visual representation (if provided) to provide analysis in the following format EXACTLY. Do NOT provide the actual answer to the user's question - only provide the analysis framework:

Context guidance:
- The session context may be unrelated; ignore it if it does not match the user question.
- Always prioritize the user question; use session context only to fill missing background.

1. **Sheet Summary**:
Provide a comprehensive overview including:
- **Workbook Purpose & Domain**: Identify the business context, industry, and primary use case
- **File Organization**: **CRITICAL - Identify if there are MULTIPLE FILES**
  - **If multiple files are present**: Explicitly state "There are X separate Excel files" and list each file:
    * File 1: [filename] contains [description] in sheet [sheetname]
    * File 2: [filename] contains [description] in sheet [sheetname]
    * **IMPORTANT**: Calculations that span multiple files MUST read from each file separately using read_table_multi()
- **Sheet Organization**: Describe how sheets are logically organized and their relationships
  - **CRITICAL for Multi-Sheet Workbooks**: Explicitly list all sheet names and explain:
    * What data each sheet contains
    * How sheets relate to each other (e.g., "Sheet1 and Sheet2 contain data for Class1 and Class2 respectively")
    * Whether sheets have similar structures (same columns, different data)
    * Whether calculations need to combine data across sheets OR across files
- **Data Structure & Types**: Catalog numerical data, text, dates, calculated fields, and hierarchical relationships
  - For each sheet, identify key columns and data types
  - Note if multiple sheets share the same structure

2. **Problem Insights**:
- **Relevant Data Scope**: Identify which specific files, sheets, ranges, or data points are most relevant
  - **For Multi-File Questions**: **CRITICAL** - Explicitly identify which FILES need to be accessed
    * State: "This question requires data from File 1: [name] and File 2: [name]"
    * Specify: "Data must be read from each file separately using read_table_multi() function"
    * Indicate: "The calculation requires combining data from multiple files"
  - **For Multi-Sheet Questions**: Explicitly identify which sheets need to be accessed
  - Specify if the question requires combining data from multiple files OR multiple sheets
  - Indicate the relationship between files/sheets (e.g., "File 1 contains Class A grades, File 2 contains Class B grades, need to calculate overall average across both files")
- **Potential Challenges**: Identify data structure complexities that might affect analysis
  - Multi-sheet operations: Need to ensure consistent column names/structures across sheets
  - Data alignment: Verify that data from different sheets can be properly combined
- **Validation Strategy**: Recommend ways to verify the accuracy of results
  - For multi-sheet calculations: Verify that all relevant sheets were included
  - Check that data from different sheets was combined correctly
- **Hierarchical Data Considerations**: Note any parent-child relationships, subtotals, or nested categories
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
You are a data quality and task-readiness inspector.

Your job is to analyze spreadsheet data and identify problems that may
prevent correct execution of the user's task.

You are given:
- A read-only view of Excel workbooks: `workbook_view`
- The user's task description

User task:
<<user_task>>

Schema summary:
<<schema_summary>>

Your task:
- Write Python code that inspects the data.
- Detect data issues that may affect correctness of the task, including:
  * Missing values in columns that appear to be numeric or used for calculation
  * Missing or invalid values in columns that appear to be dates or used for ordering
  * Inconsistent data types within the same column
  * Empty sheets or tables with very few rows
  * Columns that are constant or meaningless

Important:
- Even a small number of missing values can be critical if the column is used in
  aggregations (average, sum, max, min, sorting, grouping).
- Prefer to report potential risks rather than ignoring them.

Output format (STRICT):
- Print ONLY a JSON array of strings to stdout using json.dumps(...).
- Each string must describe exactly one problem.
- If no problems are found, print [].

Rules:
- Do not print anything except JSON.
- Do not explain your code.
- Do not print debug info.
- Write Python code ONLY (no markdown, no backticks).
- Do NOT import libraries; use what is already available (json is preloaded).
- Do not modify any data.
- Skip header rows when analyzing data values.
- Treat empty strings and whitespace as missing values.
- Do not assume column semantics by index.

Begin writing Python code below:
""")

_DIAGNOSE_PROMPT = textwrap.dedent("""\
You are a data quality and task-readiness inspector. Your task is to figure out potential data quality issues from spreasheet samples.

You MUST reason in the following order.

STEP 1 — Task Understanding
Read the user task and determine:
- The primary operation(s) involved (e.g., merge, lookup, fill missing values, aggregate).
- Which data conditions are EXPECTED given the task.
- Which data conditions would BLOCK correctness of the task.

STEP 2 — Evidence-based inspection
Inspect the sampled data for issues that need users to clarify. Such as: what is the value in missing space?
How to treat the inconsistency of names and ID.


Input:
- A user task describing required operations.
- A sampled view of spreadsheet data formatted as plain text.

User task:
<<user_task>>

Sampled data samples:
<<scan_report>>

Notes on representation:
- Cells are delimited by " | ".
- Literal spaces inside a cell value are shown as "| |".

Issue scope:
- Report risks, not fixes.
- Diagnose ONLY schema-level blocking risks (structural/data-integrity issues that prevent correct execution).
- Do NOT report business anomalies or domain-specific outliers.
- Only consider the following issue categories when their rules are activated:
  1) Numeric validity risks in columns used for aggregation.
  2) Identifier consistency risks affecting joins, lookups, or grouping.
  3) Identifier completeness risks (missing/blank join keys).
  4) Identity-related critical information required to answer the task.

                                   
Output format (STRICT):
- Output ONLY a JSON array of strings.
- Each string represents ONE blocking risk.
- Each string MUST be a natural-language full sentence.
- Each string MUST include:
  - file name
  - sheet name,
  - column name,
  - Select a row anchor that helps the user navigate to the problematic row. Choose a column and the corresponding value from that row that best identifies it.
""")

_DIAGNOSE_PRIORITIZE_PROMPT = textwrap.dedent("""\
You are a data quality triage agent.

Your job:
Given a list of candidate data issues, return the MINIMAL SET of
blocking issues relevant to the user task.

User task:
<<user_task>>

Candidate issues:
<<candidate_questions>>


Granularity rule (MANDATORY):
- If multiple issues refer to the same column and require the same
  cleaning decision, merge them into a SINGLE column-level issue.
- Do not keep separate row-level variants of the same issue.

Ranking principles:
1) Aggregation correctness
2) Join correctness

Selection rules:
- Keep at most 6 issues.
- Preserve priority order.
- If no issues remain, output [].

Output format (STRICT):
- Output ONLY a JSON array of strings.
""")

_DIAGNOSE_ROUTER_PROMPT = textwrap.dedent("""\
You are a router that decides whether to run a data-diagnose stage.

Decision rules:
- If the user only asks to analyze, discover, or search, and does NOT require generating a new Excel file or modifying data, answer NO.
- If the user needs data cleaning, fixing formats, handling missing/duplicates, or expects changes to data or a new Excel output, answer YES.
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
You are checking whether a user's reply matches a specific data-cleaning question.

Question:
<<question>>

User reply:
<<reply>>

You MUST reason in this order:
STEP 1 — Interpret user reply
- Rewrite the user reply into a full explicit answer using the question context.
- This is required especially when the reply is short, numeric, yes/no, or implicit.

STEP 2 — Match decision
- Decide whether the interpreted answer directly addresses the question.

STEP 3 — Action extraction
- If MATCH=YES, extract one clear cleaning instruction.
- If the interpreted answer means "no change needed", output ACTION as NO_OP.

Output Rules:
- Output exactly two lines.
- Line 1: MATCH: YES or NO
- Line 2: ACTION: <one clear cleaning instruction sentence>, NO_OP, or ACTION:
- If the interpreted answer indicates no change is needed, treat as MATCH = YES and ACTION = NO_OP.
- If YES and ACTION is not NO_OP, it must specify file, sheet, column(s), and operation.
- If NO, ACTION should be empty.
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
You are an expert data analyst agent.

Your job is to produce:
1) A final TASK SPECIFICATION that clearly describes what analysis or transformation should be performed on the cleaned spreadsheet data.
2) Structured CLEANING CONSTRAINTS using the provided tool.

Important:
- The task specification must describe the FINAL analytical goal, not the data cleaning actions.
- Do NOT restate cleaning steps in the task specification.
- Assume data has already been cleaned according to the constraints.
- The task specification should be executable by a data analysis agent.
- Do NOT reference original file paths unless necessary for disambiguation.

You are given:

[ORIGINAL USER REQUEST]
<<original_question>>

[DATA QUALITY ISSUES DETECTED]
<<quality_table>>

[USER CLARIFICATIONS / PREFERENCES]
<<answers_summary>>

Your tasks:

Step 1 — Decide CLEANING CONSTRAINTS
Based on the issues and user preferences, decide structured data cleaning rules
(e.g. drop columns, fill missing values, cast types).
You MUST output these using the tool call `set_constraints`.
Constraints MUST use actual column headers from the sheet (exact text).
Do NOT include sheet names, file names, or "Column C" style labels.
Use ONLY these keys: fill_missing, cast_type, drop_columns.
Do NOT invent alternative key names (e.g., fill_missing_values).

Step 2 — Write FINAL TASK SPECIFICATION
Write a clear and complete description of what should be done with the cleaned data.

The task specification should include:
- What analysis or transformation to perform
- What output to produce (table, aggregation, comparison, etc.)
- What dimensions or groups to use if applicable

The task specification must NOT include:
- Any data cleaning steps
- Any references to missing values, type casting, or column dropping
- Any assumptions about corrupted or raw data
- Any claims that cleaning has already happened or its results

Important:
- You are only deciding cleaning constraints. The deterministic cleaning module will execute them later.
- Do NOT mention cleaning results in the task specification.

Output format:
- Use the tool call to set constraints.
- Put the TASK SPECIFICATION in normal message text.
- You MUST output TASK SPECIFICATION in message content even when calling tools.
""")

_CLEANING_CODE_PROMPT = textwrap.dedent("""\
You are a data cleaning engineer.

You are given spreadsheet context and a list of cleaning actions.

[CLEANING ACTIONS]
<<actions>>

[SPREADSHEET CONTEXT]
<<schema_summary>>

Notes about the environment:
- `workbooks` is a dict: {path: openpyxl.Workbook}
- Iterate: for path, wb in workbooks.items():
- Sheets: wb.sheetnames, wb[sheet_name]
- Cells: sheet.cell(row=i, column=j).value
- Range: sheet.max_row, sheet.max_column

Rules:
- Write Python code ONLY (no markdown, no backticks).
- Use the provided `workbooks` dict (path -> openpyxl Workbook).
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
LINEAR EXECUTION CONTRACT (ONLINE + OFFLINE):

Allowed I/O helpers:
- `list_all_workbooks()`
- `get_workbook(file_path)`
- `read_table_multi(file_path, sheet_name, range_ref)`
- `create_output_sheet("Output")`
- `write_dataframe_to_sheet(dataframe_or_rows, "Output", start_cell)`
- `highlight_rows("Output", row_numbers, {"fill_color": "red"})` (if requested)
- `save_workbook_to(output_path)`

Disallowed for execution:
- `inspector(...)`, `inspector_multi(...)`, `read_multiple_sheets(...)`, `get_sheet_as_dataframe(...)`
- pandas/openpyxl file readers/writers (`pd.read_excel`, `to_excel`, `load_workbook`, `wb.save`)
- `save_workbook()` or hard-coded file paths
- literal input filenames or basename matching logic such as `"tc04_input01.xlsx"`, `"Tasks" in file_name`, or `tables[0]`/`tables[1]` role assignment

Required response format:
**Thought:** one brief line
```python
# full runnable code
```

Mandatory linear pipeline in one block:
1. Prefer `tables = load_all_tables()` for multi-file tasks.
2. If you need manual read fallback, use:
   - `all_files = list_all_workbooks()`
   - `wb = get_workbook(file_path)`
   - `sheet_name = wb.sheetnames[0]`
   - `table = read_table_multi(file_path, sheet_name, "A1:Z200")`
   - build DataFrame from `table["rows"]` and `table["header"]`
   - `read_table_multi(...)` does NOT return a `df` key
   - `table["rows"]` already excludes the header row; never slice `table["rows"][1:]`
3. Print observed files, columns, and row counts before computation
4. Compute using verified columns only
5. `create_output_sheet("Output")` then write table(s) with `write_dataframe_to_sheet(...)`
6. If highlight needed, pass a flat 1-based int list to `highlight_rows(...)`
7. `saved_file = save_workbook_to(output_path)` and return `saved_file`

Stop immediately after successful save. Do not add extra exploratory code after save.
""")

_EXECUTION_HELPER_SECTIONS_PART2 = textwrap.dedent("""\
Schema and robustness checklist:
- Normalize header artifacts before matching columns:
  `col.replace("_x000D_", "").replace("_x000d_", "").strip()`
- Drop empty columns/rows after range read.
- Before any select/merge/groupby:
  - print each DataFrame columns
  - verify required columns exist
- For multi-file tasks, classify each table by verified headers before combining:
  - same headers + same role -> concat is allowed
  - different headers or different roles -> keep separate DataFrames
  - do not raise schema mismatch just because task and dependency tables have different headers
- For same-schema vertical merge tasks, prefer:
  - `tables = load_all_tables()`
  - `concat_result = concat_tables_with_same_headers(tables)`
  - write `concat_result["output_df"]` or `concat_result["detail_data"]`
- For simple horizontal merge tasks, prefer:
  - `tables = load_all_tables()`
  - `key_header = infer_common_key(tables)`
  - `merge_result = merge_tables_on_key(tables, key_header=key_header, how="inner")`
  - write `merge_result["output_df"]` or `merge_result["detail_data"]`
- For fill-missing tasks, prefer:
  - `tables = load_all_tables(require_primary_key=False)`
  - `key_header = infer_common_key(tables)`
  - `fill_result = fill_missing_from_reference(tables[0]["df"], tables[1]["df"], key_header=key_header, prefer_primary=True)`
  - Keep rows even when the key column is blank in the primary file; the helper can recover the missing key from shared columns.
  - write `fill_result["output_df"]` or `fill_result["detail_data"]`
- For messy multi-row-header region/year chart tasks, prefer:
  - `all_files = list_all_workbooks()`
  - `analysis = build_region_growth_analysis(all_files[0], sheet_name="Data", start_year=2020, end_year=2024)`
  - write `analysis["output_df"]`
  - highlight `analysis["fastest_growth_rows"]`
  - add `analysis["summary"]`
  - plot from `analysis["chart_df"]` and call `save_plot_to_excel("Output", "F2")`
- For quarter KPI dashboard tasks with metrics like Gross Profit / Net Profit / CAC / Marketing Efficiency Ratio, prefer:
  - `dashboard_result = build_financial_dashboard_report()`
  - write `dashboard_result["detail_data"]` directly
  - do not hand-build month joins, target parsing, or dashboard rows
- For candidate screening / ranking tasks across many same-schema files, prefer:
  - `screening_result = build_candidate_screening_report()`
  - write `screening_result["detail_data"]` directly
  - the helper already excludes blank names and treats missing numeric inputs as 0
  - do not hand-build file loops, score formulas, filtering, or ranking rows
- For inventory EOQ / reorder-point / sensitivity-analysis tasks, prefer:
  - `inventory_result = build_inventory_eoq_report()`
  - write `inventory_result["detail_data"]` directly
  - do not hand-build EOQ formulas, parameter parsing, or multi-table layout
- For hospital utilisation tasks with patient/staff/service tables, prefer:
  - `report = build_hospital_utilisation_report()`
  - write `report["detail_data"]` directly
  - highlight only `report["highlight_rows"]`; if empty, print `NO_HIGHLIGHT_ROWS:`
  - do not hand-build grouped merges or utilisation formulas
- For join tasks, merge only on verified keys.
- For duration/time arithmetic, force numeric conversion:
  `pd.to_numeric(..., errors="coerce")`
- For time strings, cast minute values to int before formatting:
  `m = int(round(total_minutes))`; `f"{m // 60:02d}:{m % 60:02d}"`
- For dependency scheduling tasks:
  - Use the runtime scheduling helper path:
    - `tables = load_all_tables()`
    - `task_table = find_table_by_headers(tables, required_headers=["Task ID"], preferred_headers=["Task Name", "Duration (hours)", "Priority"], forbidden_headers=["Depends on"])`
    - `dependency_table = find_table_by_headers(tables, required_headers=["Task ID", "Depends on"])`
    - `schedule_result = build_dependency_schedule(task_table["df"], dependency_table["df"], start_time="08:00")`
  - Do NOT rebuild helper inputs with `pd.DataFrame({...})`, partial column subsets, or row lists before this call.
  - Never identify roles from filenames, literal input basenames, file order, or `tables[0]`/`tables[1]`.
  - Different schemas between those two tables are expected.
  - Write `schedule_result["detail_data"]` directly to Output.
  - Write summary from `schedule_result["summary"]`.
  - Print `TASK_ID_SET` and `SCHEDULED_TASK_IDS`, then assert exact equality before save.
- For regression tasks:
  - Prefer helper path:
    - `regression_result = fit_linear_regression_weights(df, target_col="...", feature_cols=[...])`
    - `print("USED_FEATURES:", regression_result["used_features"])`
    - write `regression_result["output_df"]` or `regression_result["detail_data"]`
  - Include all predictor columns unless user explicitly excludes some.
  - Map binary categorical predictors (yes/no, true/false, rain/no rain) to 1/0.
- For target-vs-feature correlation tasks, prefer:
  - `corr_result = compute_feature_correlations(df, target_col="...", feature_cols=[...])`
  - write `corr_result["output_df"]` or `corr_result["detail_data"]`
- For correlation matrix tasks, prefer:
  - `matrix_result = build_correlation_matrix_table(df, numeric_columns=[...], filter_column="...", filter_value="...")`
  - write `matrix_result["output_df"]` or `matrix_result["detail_data"]`
- For grouped summary tasks, prefer:
  - `summary_result = build_group_summary(df, group_cols=[...], aggregations={...})`
  - write `summary_result["output_df"]` or `summary_result["detail_data"]`
- For numeric total/average/max summary tasks on one merged table, prefer:
  - `summary_result = summarize_numeric_column(df, value_col="...", summary_labels={...})`
  - use `summary_result["summary"]` for `add_summary_row(...)`
  - use `summary_result["output_row_numbers"]` for `highlight_rows(...)`
- If required columns are missing, write a clear diagnostic table to `Output` and still save.
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
You are an expert Excel data analysis validator. Your task is to thoroughly review and validate the execution process and final answer for an Excel analysis question.

**USER QUERY:**
<<user_query>>
**USER QUERY END:**

**EXCEL DATA CONTEXT:**
<<excel_context_understanding>>
**EXCEL DATA CONTEXT END:**

**EXECUTION CONTEXT (READ-ONLY):**
<<execution_context>>
**EXECUTION CONTEXT END:**

**EXECUTION RESULTS:**
- Success: <<execution_success>>
- Total Turns: <<total_turns>>
- Final Answer: <<final_answer>>
- Code Executions: <<total_code_executions>>
- Successful Executions: <<successful_executions>>
- Failed Executions: <<failed_executions>>
**EXECUTION RESULTS END:**

**FULL CONVERSATION HISTORY:**
<<conversation_history_text>>
**FULL CONVERSATION HISTORY END:**

**USER QUERY:**
<<user_query>>
**USER QUERY END:**

**YOUR VALIDATION TASKS:**

Language constraint:
- Output must be in English only.
- Do not use Chinese or mixed-language sentences.

1. **Answer Quality:**
- Does the final answer directly address the user's question?
- Are numerical calculations accurate and verifiable?
- Is the answer format appropriate (values, comparisons, recommendations)?

2. **Reasoning & Approach:**
- Was the methodology logical and systematic?
- Were appropriate Excel functions and analysis methods used?
- Was the reasoning chain complete from exploration to conclusion?

3. **Data Handling:**
- Did the agent correctly interpret the Excel data structure?
- Were relevant columns/sheets and data relationships properly identified?
- Were data types, null values, and edge cases handled appropriately?
- Look for hierarchical relationships in data (e.g., "of which", "including", indented items)
- Do not sum subcategories with their parent categories

4. **Critical Issues:**
- Are there fundamental data structure misunderstandings?
- Any calculation errors, wrong formulas, or incorrect aggregations?
- Missing data validation or logical gaps in reasoning?

**PROVIDE YOUR ASSESSMENT IN THIS EXACT FORMAT:**

**VALIDATION_STATUS:** [PASSED/FAILED]

**CONFIDENCE_SCORE:** [0.0-1.0]

**ISSUES_FOUND:**
- [List any issues, concerns, or errors identified]
- [One issue per bullet point]
- [Use "None identified" if no issues found]

**IMPROVEMENT_FEEDBACK:**
[If VALIDATION_STATUS is FAILED, provide specific, actionable feedback for re-execution:
- What specific steps should be taken differently?
- Which data should be re-examined?
- What alternative approaches should be tried?
- Which specific Excel operations or calculations need correction?
If VALIDATION_STATUS is PASSED, write "No improvement needed - solution is valid."]

**FINAL_ASSESSMENT:**
[Provide a simple assessment of the solution quality, explaining your confidence score and validation decision]

Please be thorough and objective in your assessment. If issues are found, focus on providing clear, actionable feedback for improvement.
""")
