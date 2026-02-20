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
    * **IMPORTANT**: Calculations that span multiple files MUST read from each file separately using inspector_multi()
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
    * Specify: "Data must be read from each file separately using inspector_multi() function"
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
You are an expert Excel data analyst with access to a comprehensive Python environment for Excel analysis.

**CODE EXECUTION ENVIRONMENT:**
You have access to a Python environment with the following pre-loaded:
- openpyxl library for Excel operations
- **Pandas (pd)** for data operations including:
  * DataFrames for structured data manipulation
  * `pd.merge()` for JOIN operations between tables
  * `pd.concat()` for combining similar tables
  * Advanced filtering with boolean conditions
  * GroupBy operations for aggregations
- Helper functions for common Excel operations
- The workbook(s) are already loaded:
  * `workbooks`: Dictionary mapping file paths to workbooks (for multi-file access)
  * `excel_paths`: List of all file paths
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
You are a Quality Assurance agent. Your job is to ask ONE clarification question for the given data issue, and provide THREE short answer options plus an "Other" option.

Detected data issues:
<<quality_table>>

Current issue to clarify:
<<current_problem>>

Rules:
- Output a single question only.
- Then output EXACTLY three short answer options labeled A), B), C) plus D) Other
- Format: "Question text? A) [option1] B) [option2] C) [option3] D) Other (please specify)"
- Each A/B/C option should be 2-5 words maximum
- D) Other must always be included as the last option
- Do NOT include any extra text or explanations
- You MUST preserve the decision space of the original question
- Do NOT introduce new choices like drop/remove/ignore unless the issue explicitly asks that
- For normalization issues, ask "what standard/format should be applied," not "should we drop/keep"
- Only paraphrase; do not reinterpret
- Use plain, natural language that a non-technical user can answer
- Avoid technical phrases like "numeric validity," "validity standard," or "data quality"
- If the issue is about missing/blank values, ask directly what to do (e.g., fill, leave blank),
  without adding new choices beyond the issue itself

Example output:
Should we standardize the date format? A) Use ISO 8601 B) Use US format (MM/DD/YYYY) C) Keep as-is D) Other (please specify)
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
You are checking whether a user's reply matches one of the provided options for a data-cleaning question.

Question asked:
<<questions>>

User reply:
<<reply>>

Rules:
- Accept if reply matches option A, B, C, or D (or their text)
- Accept if reply is a number (1, 2, 3, 4) corresponding to A, B, C, D
- Accept if reply is "other" or "none of the above" → match D
- Accept if reply semantically matches one of the options
- If reply is free-form text that doesn't match A/B/C, assume D (Other) and extract the intent
- Output exactly three lines.
- Line 1: MATCH: YES or NO
- Line 2: OPTION: A, B, C, D, or NONE (which option was selected)
- Line 3: ACTION: <one clear cleaning instruction sentence>, NO_OP, ASK_CLARIFICATION, or empty
- If D (Other) is selected, ACTION should be ASK_CLARIFICATION to get more details
- If the reply indicates no change is needed, treat as MATCH = YES, OPTION: C (or last option), ACTION = NO_OP
- If YES and ACTION is not NO_OP/ASK_CLARIFICATION, it must specify file, sheet, column(s), and operation
- If NO, OPTION should be NONE and ACTION should be empty
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
Available Excel Helper Functions:

**🚫 CRITICAL CONSTRAINTS - MUST FOLLOW:**
1. **DO NOT use `pd.ExcelWriter()` or `DataFrame.to_excel()`** - These create separate files and cause path confusion
2. **DO NOT use `engine=\"xlsxwriter\"`** - This module is not available
3. **DO NOT use pandas Styler (`df.style.apply()`)** - Use `apply_formatting()` or `highlight_rows()` instead
4. **ALL file writing MUST go through Excel helper functions** - Use `write_dataframe_to_sheet()` + `save_workbook_to()`

**📝 UNIFIED OUTPUT WORKFLOW (MUST FOLLOW):**
When you need to write results to an Excel file, follow this exact pattern:
```python
# Step 1: Convert combined DataFrame to 2D list (include headers)
# This is the DETAILED DATA TABLE (e.g., all 30 rows of spending records)
detailed_data = [combined_data.columns.tolist()] + combined_data.values.tolist()

# Step 2: Create/clear output sheet
create_output_sheet("Output")

# Step 3: Write DETAILED DATA TABLE starting at A1
write_dataframe_to_sheet(detailed_data, "Output", "A1")
# Now the sheet has: Row 1 = headers, Rows 2-31 = data (30 rows)

# Step 4: Calculate where summary should go (after detailed data + 2 blank rows)
summary_start_row = len(detailed_data) + 2  # e.g., 32 if detailed_data has 31 rows (1 header + 30 data)

# Step 5: Prepare summary statistics as 2D list
summary_data = [
    ["Metric", "Value"],  # Header row
    ["Total Spending (£)", total_spending],
    ["Average Daily Spending (£)", average_spending],
    ["Max Spending Day(s)", max_spending_days_str],  # Convert dates to strings!
    ["Max Spending Amount (£)", max_spending]
]

# Step 6: Write summary below detailed data
write_dataframe_to_sheet(summary_data, "Output", f"A{summary_start_row}")

# Step 7: Highlight the max spending day ROW in the DETAILED DATA TABLE
# Find which row in detailed_data contains the max spending day
# Row numbers are 1-indexed: row 1 = header, row 2 = first data row
max_spending_row_in_table = None
for idx, row in combined_data.iterrows():
    if row['Daily Spending (£)'] == max_spending:
        # +2 because: +1 for header row, +1 for 1-indexing
        max_spending_row_in_table = idx + 2
        break

if max_spending_row_in_table:
    highlight_rows("Output", [max_spending_row_in_table], {"fill_color": "red"})

# Step 8: Save to SINGLE output path (use the provided output_path variable)
saved_file = save_workbook_to(output_path)
```

**CRITICAL: Output Structure Requirements:**
- The Output sheet MUST contain BOTH:
  1. **Detailed data table** (all merged records) starting at A1
  2. **Summary statistics** below the detailed table (with 2 blank rows gap)
- DO NOT write only summary - always include the full detailed data table first!

**Basic Sheet Operations:**
- `list_sheets()`: List all sheet names in the workbook
  - **Usage:** `sheets = list_sheets()`
  - **Output:** List of sheet names: `['Sheet1', 'Sheet2', 'Sheet3']`

- `get_sheet(sheet_name=None)`: Get worksheet by name or active sheet
  - **Usage:** `sheet = get_sheet("Sheet1")` or `sheet = get_sheet()` for active sheet

- `get_sheet_info(sheet_name=None)`: Get information about a sheet
  - **Usage:** `info = get_sheet_info("Sheet1")`
  - **Output:** Dict with name, dimensions

- `get_all_sheets_info()`: Get information about all sheets
  - **Usage:** `all_info = get_all_sheets_info()`

**Reading Data:**
- `inspector(range_ref, sheet_name=None)`: Read cell values from specified range
  - **Usage:** `data = inspector("A1:C3", "Sheet1")` or `value = inspector("B5")`
  - **Output:** List of lists format: `[['A1', 'B1', 'C1'], ['A2', 'B2', 'C2']]`

- `read_multiple_sheets(sheet_names, range_ref=None)`: Read data from multiple sheets at once
  - **Usage:** `data = read_multiple_sheets(["Sheet1", "Sheet2"], "A1:C10")`

- `inspector_attribute(range_ref, attributes, sheet_name=None)`: Extract cell formatting
  - **Usage:** `attrs = inspector_attribute("A1:B2", ["color", "font"], "Sheet1")`

- `search(value, sheet_name=None, case_sensitive=False, search_type='partial')`: Find cells
  - **Usage:** `matches = search("Total", case_sensitive=True, search_type="whole")`

**📤 Writing Data (USE THESE INSTEAD OF DataFrame.to_excel!):**
- `create_output_sheet(sheet_name)`: Create or clear a sheet for output
  - **Usage:** `create_output_sheet("Output")`
  - **Important:** Always call this before writing new data

- `write_dataframe_to_sheet(data, sheet_name, start_cell="A1")`: Write 2D list data to sheet
  - **Usage:** `write_dataframe_to_sheet(data_2d, "Output", "A1")`
  - **Important:** Convert DataFrame to 2D list first: `[df.columns.tolist()] + df.values.tolist()`

- `add_summary_row(sheet_name, row_number, summary_data)`: Add labeled summary statistics
  - **Usage:** `add_summary_row("Output", 35, {"Total": 2023.75, "Average": 72.28})`

**🎨 Formatting:**
- `apply_formatting(sheet_name, range_ref, format_dict)`: Apply cell formatting
  - **Usage:** `apply_formatting("Sheet1", "A1:C5", {"fill_color": "red", "bold": True})`

- `highlight_rows(sheet_name, row_numbers, format_dict)`: Highlight entire rows
  - **Usage:** `highlight_rows("Output", [5], {"fill_color": "red"})`
  - **Important:** Use this to highlight max spending days, important records, etc.
  - **Row numbers are 1-indexed!** Add 1 for header row if data starts at row 2

**💾 Saving (USE save_workbook_to FOR EXPLICIT PATH!):**
- `save_workbook_to(output_path)`: Save workbook to specific path (RECOMMENDED)
  - **Usage:** `saved_file = save_workbook_to(output_path)`
  - **Returns:** The exact path where file was saved
  - **Important:** Use the `output_path` variable provided in the context

- `save_workbook()`: Save workbook with auto-generated '_output' suffix
  - **Usage:** `filename = save_workbook()`
  - **Note:** Prefer `save_workbook_to(output_path)` for explicit control

- `save_plot_to_excel(sheet_name, cell_position='A1', figsize=(10,6), dpi=100)`: Save matplotlib plot
  - **Usage:** `result = save_plot_to_excel("Charts", "D5", figsize=(8,6))`

**RESPONSE FORMATS - MANDATORY COMPLIANCE:**

SYSTEM CONSTRAINT: Your response must contain EXACTLY one of these formats and NOTHING ELSE:

FORMAT A - Thinking + Code execution:
**Thought:** [Your reasoning and analysis here]

```python
# Your Python code here
```

FORMAT B - Thinking + Final answer:
**Thought:** [Your reasoning and analysis here]

Final Answer: [Your conclusive answer]

CRITICAL REQUIREMENTS:
- ALWAYS start with **Thought:** to explain your reasoning
- Follow with EITHER code execution OR final answer
- NO additional text, explanation, or commentary outside these formats
- NO preamble, postamble, or "how it works" sections
- VIOLATION WILL RESULT IN TASK FAILURE

**CRITICAL DECISION FRAMEWORK - When to use Code vs. Direct Analysis:**

** USE DIRECT ANALYSIS (Give Final Answer immediately) when:**
- The Sheet Content preview shows ALL necessary data for the question
- Simple calculations can be performed mentally from visible data
- The question asks for values that are directly visible in the preview
- Table structure is clear and hierarchical relationships are evident
- No complex aggregations, transformations, or editing operations are needed
- Data relationships (parent-child, subtotals) are obvious from the preview

** USE CODE when:**
- Data extends beyond what's shown in the preview
- Complex calculations, aggregations, or statistical analysis is required
- Data transformation, filtering, or manipulation is needed
- **JOIN/MERGE operations** are needed (combining tables with common keys)
- **Multi-condition filtering** is required (e.g., score >= 60 AND major == '计算机')
- Need to edit/modify the Excel file
- Need to search across large datasets
- Verification of calculations through code is specifically requested

**IMPORTANT GUIDELINES:**
- **NO REDUNDANT CODE**: Don't write code to print data that's already visible in the Sheet Content
- Print intermediate results to show your thought process
- Use the helper functions for common operations
- **Identify hierarchical relationships** (e.g., "of which", "including", indented items)
- Use `save_workbook()` to save changes
- **ALWAYS call `save_workbook()` after making ANY changes to the Excel file**
- **VERIFICATION FOR MULTI-FILE CALCULATIONS**: When working with multiple files, ALWAYS:
  * Print the number of rows read from each file
  * Print the combined total number of rows
  * Verify that data from ALL files is included before calculating the final result
  * Example verification code:
    ```python
    print(f"Class A rows: {len(df_class_a)}")
    print(f"Class B rows: {len(df_class_b)}")
    print(f"Combined rows: {len(combined_data)}")
    print(f"Expected total: {len(df_class_a) + len(df_class_b)}")
    ```
""")

_EXECUTION_HELPER_SECTIONS_PART2 = textwrap.dedent("""\
### Multi-File Operations – CRITICAL INSTRUCTIONS
When working with multiple Excel files:

**⚠️ CRITICAL: If the Sheet Content shows multiple files, you MUST read from each file separately!**

**🚨 MANDATORY CHECKLIST for Multi-File Questions:**
1. ✅ Call `list_all_workbooks()` to confirm all files are loaded
2. ✅ Read data from File 1 using `inspector_multi(file1_path, range, sheet_name)`
3. ✅ Read data from File 2 using `inspector_multi(file2_path, range, sheet_name)`
4. ✅ Verify both DataFrames have data (print their lengths)
5. ✅ Combine both DataFrames using `pd.concat()`
6. ✅ Verify combined DataFrame has data from BOTH files (print total length)
7. ✅ Calculate result on COMBINED data, not individual files

**❌ COMMON MISTAKES TO AVOID:**
- DO NOT use `inspector()` for multi-file scenarios (it only reads from the first file)
- DO NOT calculate average on only one file's data
- DO NOT skip reading from the second file
- DO NOT assume both files have the same structure without checking

1. **List All Workbooks First**
   - Start by calling `list_all_workbooks()` to see all loaded file paths
   - Use `workbooks` dictionary to access specific workbooks by file path
   - Example: `all_files = list_all_workbooks()` returns `['/path/to/file1.xlsx', '/path/to/file2.xlsx']`
   - **VERIFY**: Print the list to confirm you have all files

2. **Access Data from Specific Files - MANDATORY for Multi-File Scenarios**
   - **DO NOT use `inspector()` for multi-file scenarios** - it only reads from the first workbook in workbooks!
   - **MUST use `inspector_multi(file_path, range_ref, sheet_name)` to read from each file separately**
   - Use `get_workbook(file_path)` to get a specific workbook
   - Use `get_sheet_from_workbook(file_path, sheet_name)` to get a sheet from a specific file
   - Example for two files:
     ```python
     # Get file paths
     all_files = list_all_workbooks()
     file1_path = all_files[0]  # or excel_paths[0]
     file2_path = all_files[1]  # or excel_paths[1]
     
     # Read from each file separately
     file1_data = inspector_multi(file1_path, "A1:D20", "Sheet1")
     file2_data = inspector_multi(file2_path, "A1:D20", "Sheet1")
     
     # Then combine the data
     df1 = pd.DataFrame(file1_data[1:], columns=file1_data[0])
     df2 = pd.DataFrame(file2_data[1:], columns=file2_data[0])
     combined = pd.concat([df1, df2])
     ```

3. **Cross-File Calculations - MANDATORY STEPS**
   - When the question involves multiple files (e.g., "average across two classes in different files"), you MUST:
     a. **FIRST**: Call `list_all_workbooks()` to get all file paths
     b. **SECOND**: Read data from EACH file separately using `inspector_multi(file_path, range_ref, sheet_name)`
     c. **THIRD**: Combine the data appropriately (using pandas if needed)
     d. **FOURTH**: Perform calculations on the combined dataset
   - **CRITICAL**: Never use `inspector()` alone for multi-file scenarios - it will only read from the first file!
   - Example for "average across two classes in different files":
     ```python
     # Step 1: Get all file paths
     all_files = list_all_workbooks()
     file1_path = all_files[0]  # First file (e.g., example_table.xlsx)
     file2_path = all_files[1]  # Second file (e.g., example2.xlsx)
     
     # Step 2: Read from each file using inspector_multi (NOT inspector!)
     # IMPORTANT: Include header row in range (e.g., A2:C7 includes row 2 as header)
     # Check the Sheet Content preview to determine correct ranges
     class1_data = inspector_multi(file1_path, "A2:C7", "PELAGIC")  # Read including header row
     class2_data = inspector_multi(file2_path, "A2:C7", "Sheet1")   # Read including header row
     
     # Step 3: Convert to DataFrames
     # First row of data is usually the header, rest are data rows
     df1 = pd.DataFrame(class1_data[1:], columns=class1_data[0])  # Skip first row if it's header
     df2 = pd.DataFrame(class2_data[1:], columns=class2_data[0])  # Skip first row if it's header
     
     # Step 4: Combine the dataframes
     combined = pd.concat([df1, df2], ignore_index=True)
     
     # Step 5: Calculate average on combined data
     combined['GRP Grades'] = pd.to_numeric(combined['GRP Grades'], errors='coerce')
     combined = combined.dropna(subset=['GRP Grades'])  # Remove any NaN values
     
     # CRITICAL: Verify data from both files is included
     print(f"Class A students: {len(df1)}")
     print(f"Class B students: {len(df2)}")
     print(f"Total students in combined data: {len(combined)}")
     if len(combined) != len(df1) + len(df2):
         print(f"WARNING: Expected {len(df1) + len(df2)} students, but got {len(combined)}")
     
     average = combined['GRP Grades'].mean()
     print(f"Overall average: {average}")
     print(f"Class A average: {df1['GRP Grades'].mean():.2f}")
     print(f"Class B average: {df2['GRP Grades'].mean():.2f}")
     ```

4. **File Relationships and JOIN Operations**
   - Identify if files contain related data (e.g., different classes, different time periods, different departments)
   - **For JOIN/MERGE operations**: When tables have a common key (e.g., student ID, employee ID), use `pd.merge()` to join them
   - **JOIN Types**: Use `how='inner'` (default) for matching records only, `how='left'` to keep all from left table, `how='outer'` for all records
   - **Example for JOIN with filtering**:
     ```python
     # Read two tables with common key
     table1_data = inspector_multi(file1_path, "A1:C10", "Sheet1")  # ID, Name, Score
     table2_data = inspector_multi(file2_path, "A1:B10", "Sheet1")  # ID, Major
     
     # Convert to DataFrames
     df1 = pd.DataFrame(table1_data[1:], columns=table1_data[0])
     df2 = pd.DataFrame(table2_data[1:], columns=table2_data[0])
     
     # JOIN on common key (e.g., student ID)
     merged = pd.merge(df1, df2, on='学生ID', how='inner')
     
     # Apply filters (e.g., score >= 60 AND major == '计算机')
     result = merged[(merged['均分'] >= 60) & (merged['专业'] == '计算机')]
     
     print(f"符合条件的学生数: {len(result)}")
     print(result)
     ```
   - Pay attention to file names in the Sheet Content preview to identify which file contains which data

### Multi-Sheet Operations – CRITICAL INSTRUCTIONS
When working with multiple sheets in a workbook:

1. **Always List Sheets First**
   - Start by calling `list_sheets()` to see all available sheets in the first workbook (from workbooks dictionary)
   - Use `get_all_sheets_info()` to understand the structure of all sheets
   - For multi-file scenarios, check each workbook separately using `get_workbook(file_path)`

2. **Explicitly Specify Sheet Names**
   - ALWAYS provide `sheet_name` parameter when calling `inspector()`, `get_sheet()`, etc.
   - Example: `data1 = inspector("A1:C10", "Sheet1")` and `data2 = inspector("A1:C10", "Sheet2")`
   - Never rely on default/active sheet when multiple sheets exist

3. **Cross-Sheet Calculations (within same file)**
   - When the question involves multiple sheets in the same workbook:
     a. Read data from each relevant sheet separately
     b. Combine the data appropriately (using pandas if needed)
     c. Perform calculations on the combined dataset
   - Example for "average across two sheets in same file":
     ```python
     # Get data from both sheets
     class1_data = inspector("A1:D20", "Class1")
     class2_data = inspector("A1:D20", "Class2")
     # Convert to DataFrames and combine
     df1 = pd.DataFrame(class1_data[1:], columns=class1_data[0])
     df2 = pd.DataFrame(class2_data[1:], columns=class2_data[0])
     combined = pd.concat([df1, df2])
     # Calculate average
     average = combined['GRP'].mean()
     ```

4. **Sheet Relationships**
   - Identify if sheets contain related data (e.g., different classes, different time periods)
   - Understand how to combine them (concatenate, merge, or calculate separately then aggregate)

### Multi-Table in One Sheet – Instructions
1. **Detect Multiple Tables**
   Recognize that a single sheet may contain several distinct tables separated by blank rows/columns or different header areas.
2. **Identify Boundaries**
   Clearly define the start and end range of each table to avoid mixing data.
3. **Check Relationships**
   Analyze whether tables are logically connected (e.g., raw data vs. summary, detail vs. KPIs).
4. **Follow Query Focus**
   If the query mentions multiple tables, address each one explicitly and compare where relevant.

### Complex Table – Instructions
1. **Identify Hierarchies**
   Detect multi-row column headers (top headers) and multi-level row headers (left headers) as hierarchical structures.
2. **Preserve Header Levels**
   Keep parent–child relationships intact when analyzing (e.g., Region → Product → Sales).
3. **Handle Subtotals**
   Recognize subtotal and total rows/columns, and clarify "of which" or aggregation relationships.
4. **Explain Hierarchy in Results**
   Clearly state how each level contributes to subtotals/totals in your explanation.

Start by exploring the data structure to understand what you're working with.
""")

_EXECUTION_USER_PROMPT = textwrap.dedent("""\
**USER QUERY:**
<<user_query>>

**UNDERSTANDING CONTEXT:**
<<understanding_output>>

**Sheet Content:**
<<execution_context>>

Please start by exploring the data structure and then work toward answering the task step by step.
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
