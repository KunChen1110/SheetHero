"""Offline/local strict prompt texts (fully independent from online prompts)."""

from __future__ import annotations

import textwrap


_UNDERSTANDING_PROMPT_OFFLINE = textwrap.dedent("""\
You are an OFFLINE spreadsheet planner. Ground every claim in visible workbook content only.

User question:
<<user_question>>

Workbook context:
<<excel_context_understanding>>

Return analysis only, not the final numeric answer.

Use this exact structure:

### 1. Sheet Summary
- Files / sheets visible in context
- Key headers exactly as shown
- Data quality notes that could block execution

### 2. Execution Plan (Offline Strict)
- Read / inspect plan
- Schema grounding plan
- Computation plan
- Output plan
- Validation plan

### 3. Output Contract (MANDATORY, machine-readable)
requires_detailed_table: YES or NO
requires_highlight: YES or NO
requires_summary_metrics: YES or NO
contract_reason: one short sentence

Rules:
- Treat workbook content as source of truth.
- Do not invent unseen files, sheets, or columns.
- Prefer generic grounded steps over task-shaped assumptions.
- Multi-file tasks may legitimately have different schemas.
- Keep Output Contract aligned with the user request.
- If user asks for a new table/schedule/spreadsheet, `requires_detailed_table` should usually be YES.
- Output plain text only. No code fences or executable code.
- Never mention forbidden APIs (`pd.read_excel`, `pd.ExcelFile`, `pd.read_csv`, `pd.read_table`, `to_excel`, `openpyxl`).
- Keep it compact.
""")

_ENHANCED_UNDERSTANDING_PROMPT_OFFLINE = textwrap.dedent("""\
<<understanding_output>>

**IMPROVEMENT FEEDBACK FROM PREVIOUS ITERATION:**
<<improvement_feedback>>

**ISSUES TO ADDRESS:**
<<issues_to_address>>

Revise the plan with minimal assumptions and stronger grounding checks.
Keep the `Output Contract` block with explicit YES/NO flags.
""")

_UNDERSTANDING_VERIFY_BEFORE_INFER_OFFLINE = textwrap.dedent("""

**OFFLINE VERIFY-BEFORE-INFER RULE (MANDATORY):**
- Only trust values/headers/sheets that are explicitly present in runtime context.
- If uncertain, print schema first and branch from observed columns.
""").strip()

UNDERSTANDING_PROMPT_OFFLINE: str = (
    _UNDERSTANDING_PROMPT_OFFLINE + "\n\n" + _UNDERSTANDING_VERIFY_BEFORE_INFER_OFFLINE
)


_EXECUTION_SYSTEM_INTRO_OFFLINE = textwrap.dedent("""\
You are an OFFLINE STRICT execution agent for spreadsheet analysis.
Return one compact Python block that uses ONLY approved spreadsheet helpers.
Prefer shortest correct grounded solution.
""")

_EXECUTION_RESPONSE_FORMAT_OFFLINE = textwrap.dedent("""\
**FORMAT:**
```python
# executable code only
```
- Code block is mandatory.
- Optional: one short `**Thought:**` line before the code block. If unsure, omit it and return code only.
- <=80 lines, close backticks, no extra text.
- Do not output hidden reasoning or `<think>...</think>` blocks.
""")

_OFFLINE_EXECUTION_RULES = textwrap.dedent("""\
**EXECUTION RULES:**
- Start with `tables = load_all_tables()` and print file names, sheet names, and headers.
- `load_all_tables()` returns a LIST: use `tables[i]["df"]`, never `tables["name"]`.
- Sheet selection: use `tables[i]["sheet"]` to identify each sheet by name. Never assume the first table is the target — a workbook may have metadata sheets before the actual data sheet.
- For multi-file tasks, classify tables by verified headers, not filenames or file order.
- Use `find_table_by_headers(...)` or `read_table_multi(...)` when needed.
- Verify columns before select / merge; standard pandas (`pd.merge`, `pd.concat`, filters) is allowed.
- If expected columns are missing, write a diagnostic Output sheet and still save.
- `write_dataframe_to_sheet(df_or_rows, "Output", "A1")` writes the header row automatically for DataFrames.
- Highlight rows with flat 1-based ints only.
- FORBID only file I/O: `pd.read_excel`, `pd.read_csv`, `to_excel`, `openpyxl`, literal input paths/files, `inspector()`.
- End with:
  `saved_file = save_workbook_to(output_path)`
  `print("SAVED_FILE:", saved_file)`
  `saved_file`
""")

_EXECUTION_HELPER_SECTIONS_PART1_OFFLINE: str = (
    _EXECUTION_RESPONSE_FORMAT_OFFLINE
    + "\n\n"
    + _OFFLINE_EXECUTION_RULES
)

_EXECUTION_HELPER_SECTIONS_PART2_OFFLINE = textwrap.dedent("""\
**MERGE GUIDANCE:**
- Same schema -> `pd.concat`
- Shared verified key -> `pd.merge`
- Assignment schedules -> prefer `build_grouped_assignment_join(...)`
- Print both column lists before merge
""")

_EXECUTION_USER_PROMPT_OFFLINE = textwrap.dedent("""\
**Sheet Content:**
<<execution_context>>

**Understanding Hint (low confidence):**
<<understanding_output>>

**User Question:**
<<user_query>>

Ground on runtime schema first. If hint conflicts with runtime, trust runtime.
""")

_VALIDATION_PROMPT_OFFLINE = textwrap.dedent("""\
You are an OFFLINE validator for spreadsheet execution.

**Original User Question:**
<<user_query>>

**Excel Context:**
<<excel_context_understanding>>

**Execution Results:**
- Success: <<execution_success>>
- Total Turns: <<total_turns>>
- Final Answer: <<final_answer>>
- Code Executions: <<total_code_executions>>
- Successful Executions: <<successful_executions>>
- Failed Executions: <<failed_executions>>

**Conversation History:**
<<conversation_history_text>>

Return STRICTLY in this exact format (no markdown code fences):

VALIDATION_STATUS: PASSED or FAILED
CONFIDENCE_SCORE: <0.00-1.00>
ISSUES_FOUND:
- <issue 1> (or `- None identified.`)
IMPROVEMENT_FEEDBACK:
<short actionable feedback>
FINAL_ASSESSMENT:
<one short paragraph>

Rules:
- If execution failed, validation cannot pass.
- If final answer is file path, execution must include save evidence.
- For merge/detail/highlight tasks, writing only `Metric | Value` is not acceptable.
- Prioritize correctness and reproducibility over style.
- Standard pandas operations (`pd.merge`, `pd.concat`, `groupby`, `fillna`, etc.) are ALLOWED and expected.
- Only file I/O is forbidden: `pd.read_excel`, `pd.read_csv`, `to_excel`, `openpyxl` direct.
- Do NOT flag `pd.merge()` or any standard DataFrame operation as a violation.
""")


_QUALITY_DIAG_PROMPT_OFFLINE = textwrap.dedent("""\
You are an OFFLINE data quality inspector.

Use ONLY the provided Excel context.

Rules:
- Output a plain bullet list only.
- Each line must start with "- ".
- One issue per line.
- Keep each issue short and concrete.
- If no issue is found, output an empty response.
- Do not infer business intent.

Excel Context:
<<excel_context_understanding>>
""")


_UNDERSTANDING_CONTEXT_MATCH_PROMPT_OFFLINE = textwrap.dedent("""\
Decide whether session context is relevant to the current user question.

Rules:
- Return YES only when the context clearly matches.
- Return NO for mismatch or uncertainty.
- Output ONE token only: YES or NO.

User question:
<<user_question>>

Session context:
<<session_context_understanding>>
""")


_DIAGNOSE_CODE_PROMPT_OFFLINE = textwrap.dedent("""\
You are an OFFLINE diagnose code generator.

Goal:
- Inspect workbook samples and detect blocking data-quality risks.

Inputs:
- User task:
<<user_task>>
- Schema summary:
<<schema_summary>>

Output requirements:
- Write Python code only.
- Do not use markdown fences.
- Print ONLY one JSON array of strings via json.dumps(...).
- If no risk is found, print [].
""")


_DIAGNOSE_PROMPT_OFFLINE = textwrap.dedent("""\
You are an OFFLINE diagnose agent.

Task:
- Read the user task and sampled workbook text.
- Return a JSON array of blocking risks that require user clarification.

User task:
<<user_task>>

Sampled data:
<<scan_report>>

Rules:
- Output ONLY valid JSON array, nothing else.
- Keep each item as one short sentence.
- Focus on blocking schema/data-quality risks only.
- Do not propose fixes.
- If no risk exists, output [].

Each issue should include:
- file name
- sheet name
- column name
- one row anchor (column=value) when possible
""")


_DIAGNOSE_PRIORITIZE_PROMPT_OFFLINE = textwrap.dedent("""\
You are an OFFLINE triage agent.

User task:
<<user_task>>

Understanding of which files are needed:
<<understanding_output>>

Candidate issues:
<<candidate_questions>>

Task:
- Use the understanding to determine which files are DIRECTLY required to produce the output.
  DROP every issue from files not listed as input sources in the understanding — even if they have missing values.
- Keep only issues that would cause the final result to be wrong or incomplete.
- Do NOT merge or rephrase issues. Copy each kept issue VERBATIM from the candidate list.
- Keep at most 6 issues.

Output format:
- Output ONLY a JSON array of strings.
- If none, output [].
""")


_DIAGNOSE_ROUTER_PROMPT_OFFLINE = textwrap.dedent("""\
Decide whether diagnose stage is needed before execution.

Return only YES or NO.

Use YES when:
- Data cleaning or ambiguity resolution is needed.
- Missing values / format inconsistency may block correctness.

Use NO when:
- Task is direct analysis and no clarification is needed.
- Uncertain.

User question:
<<user_question>>

Understanding summary:
<<understanding_output>>
""")


_QA_PROMPT_OFFLINE = textwrap.dedent("""\
You are an OFFLINE QA agent for data-cleaning decisions.

Detected data issues:
<<quality_table>>

Original user task:
<<original_question>>

User reply:
<<user_reply>>

Rules:
- Ask one clarification question if decision is unclear.
- Keep the question short and concrete.
- Do not invent options outside the issue scope.
""")


_QA_QUESTION_PROMPT_OFFLINE = textwrap.dedent("""\
Ask ONE clarification question for the current data issue.

Detected issues:
<<quality_table>>

Current issue:
<<current_problem>>

Rules:
- Output one sentence only.
- No explanation, no heading.
- Keep the question directly answerable by end users.
- Do not add new decision branches that are not in the issue.
""")


_QA_MATCH_PROMPT_OFFLINE = textwrap.dedent("""\
Check whether the user reply semantically answers the clarification question.

Question:
<<question>>

User reply:
<<reply>>

Decision rules:
- Treat the reply semantically, not literally. The reply may be short, indirect, multilingual, or phrased naturally.
- If reply gives ANY decision, instruction, or preference — even partial — set MATCH to YES.
- If reply means no change (ignore, keep, as is, leave blank), set MATCH=YES.
- Only set MATCH=NO if the reply is completely unrelated gibberish or an empty response.

DECISION_KIND rules:
- For missing-value issues: use `fill_value` or `no_change`
- For choice / option issues: use `choose_option` or `no_change`
- For period / interpretation issues: use one of `restrict_window`, `use_latest`, `interpolate`, `unavailable`, or `no_change`
- If uncertain but user intent is still clear, choose the closest valid decision kind.

Field rules:
- VALUE: numeric/string payload when decision needs a fill value
- SELECTED_OPTION: exact option/header/value chosen by the user when relevant
- POLICY_KIND: optional compact tag for interpretation decisions
- ACTION: optional one-sentence executable action; leave blank if structured fields are enough
- MISSING_SLOT: if MATCH=NO, name the missing thing such as `fill_value`, `selected_option`, or `policy_choice`

Output format (STRICT, EXACTLY 6 LINES):
MATCH: YES or NO
DECISION_KIND: <fill_value | choose_option | restrict_window | use_latest | interpolate | unavailable | no_change | empty>
VALUE: <value or empty>
SELECTED_OPTION: <exact chosen option or empty>
POLICY_KIND: <tag or empty>
ACTION: <complete instruction, NO_OP, or empty>

If MATCH=NO, add a seventh line:
MISSING_SLOT: <short slot name>

No markdown. No extra text beyond the required lines.
""")


_QA_INSTRUCTION_PROMPT_OFFLINE = textwrap.dedent("""\
Convert a user reply into one executable cleaning instruction.

Issue:
<<problem>>

Reply:
<<reply>>

Rules:
- Output one sentence only.
- Must include target column and operation.
- If reply means no change, output NO_OP.
- Do not add explanation.
""")


_QA_ACTIONS_PROMPT_OFFLINE = textwrap.dedent("""\
Produce cleaning actions from confirmed user clarifications.

Detected issues:
<<quality_table>>

Clarification summary:
<<answers_summary>>

Rules:
- Output a bullet list only.
- Each bullet must start with "- ".
- One action per line.
- If no action is needed, output an empty response.
""")


_QA_DECISION_PROMPT_OFFLINE = textwrap.dedent("""\
You are an OFFLINE decision agent.

Inputs:
- Original request:
<<original_question>>
- Detected issues:
<<quality_table>>
- Clarifications:
<<answers_summary>>

Task:
- Produce a clean final task specification (analysis goal only).
- Keep cleaning decisions out of the task description.

Output:
- Plain text task specification only.
- No markdown.
""")


EXECUTION_SYSTEM_PROMPT_OFFLINE: str = (
    _EXECUTION_SYSTEM_INTRO_OFFLINE
    + "\n\n"
    + _EXECUTION_HELPER_SECTIONS_PART1_OFFLINE
)
