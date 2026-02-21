"""Offline/local prompt texts."""

from __future__ import annotations

import textwrap

from .prompt_texts_online import (
    _UNDERSTANDING_PROMPT,
    _EXECUTION_SYSTEM_INTRO,
    _EXECUTION_USER_PROMPT,
    _VALIDATION_PROMPT,
)


_UNDERSTANDING_VERIFY_BEFORE_INFER_OFFLINE = textwrap.dedent("""
**OFFLINE NOTE (strict):**
- Base analysis only on observed sheet data.
- Do not infer semantics from filenames, file order, or assumed date ranges.
""").strip()

UNDERSTANDING_PROMPT_OFFLINE: str = (
    _UNDERSTANDING_PROMPT + "\n\n" + _UNDERSTANDING_VERIFY_BEFORE_INFER_OFFLINE
)


_EXECUTION_RESPONSE_FORMAT_OFFLINE = textwrap.dedent("""
**RESPONSE FORMAT (OFFLINE):**

Use exactly this format:

**Thought:** [brief reasoning]

```python
# executable code only
```
""").strip()

_OFFLINE_EXECUTION_RULES = textwrap.dedent("""
**OFFLINE EXECUTION RULES (MANDATORY):**
- Do not invent paths. Always call `all_files = list_all_workbooks()`.
- For multi-file questions, read every file in `all_files` using `inspector_multi(...)`.
- Exact helper signatures:
  - `inspector_multi(file_path, range_ref, sheet_name)` where `file_path` MUST be a string from `all_files`.
  - `get_workbook(file_path)` returns Workbook object (do not pass Workbook into `inspector_multi`).
- Do NOT write `from common_functions import ...` (helpers are already in runtime namespace).
- Do NOT use `range_ref=` keyword in `inspector_multi`; use positional args only.
- Correct example:
  - `data1 = inspector_multi(all_files[0], "A1:D40", "Sheet1")`
  - `data2 = inspector_multi(all_files[1], "A1:D40", "Sheet1")`
- Before selecting metric/date columns, print actual columns:
  `print("Columns:", df.columns.tolist())`
- Use only these spreadsheet I/O helpers:
  `list_all_workbooks()`, `get_workbook()`, `inspector_multi()`,
  `create_output_sheet()`, `write_dataframe_to_sheet()`, `save_workbook_to(output_path)`.
- Forbidden: `pd.read_excel`, `pd.ExcelFile`, `.to_excel`, `openpyxl`, `open(...)`, hard-coded paths.
- If runtime reports forbidden usage, apply a minimal patch: change only forbidden lines.
""").strip()

_OFFLINE_OUTPUT_WORKFLOW = textwrap.dedent("""
**OUTPUT WORKFLOW (MANDATORY):**
1. `create_output_sheet("Output")`
2. `data_2d = [df.columns.tolist()] + df.values.tolist()`
3. `write_dataframe_to_sheet(data_2d, "Output", "A1")`
4. `saved_file = save_workbook_to(output_path)`
5. `print("SAVED_FILE:", saved_file)`
6. Last expression should be `saved_file`
""").strip()

_EXECUTION_HELPER_SECTIONS_PART1_OFFLINE: str = (
    _EXECUTION_RESPONSE_FORMAT_OFFLINE
    + "\n\n"
    + _OFFLINE_EXECUTION_RULES
    + "\n\n"
    + _OFFLINE_OUTPUT_WORKFLOW
)


EXECUTION_SYSTEM_PROMPT_OFFLINE: str = (
    _EXECUTION_SYSTEM_INTRO
    + "\n\n"
    + _EXECUTION_HELPER_SECTIONS_PART1_OFFLINE
)

EXECUTION_USER_PROMPT_OFFLINE: str = _EXECUTION_USER_PROMPT

VALIDATION_PROMPT_OFFLINE: str = _VALIDATION_PROMPT
