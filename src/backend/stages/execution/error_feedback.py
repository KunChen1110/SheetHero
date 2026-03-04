"""Execution error-signature and repair-feedback helpers."""

from __future__ import annotations

import os
import re
from typing import Callable, Optional


class ExecutionErrorFeedbackBuilder:
    """Build targeted repair feedback for common execution failures."""

    def __init__(
        self,
        available_workbook_basenames_fn: Callable[[], list[str]],
        observed_header_set_fn: Callable[[], set[str]],
        build_schema_snapshot_fn: Callable[[], str],
    ) -> None:
        self._available_workbook_basenames = available_workbook_basenames_fn
        self._observed_header_set = observed_header_set_fn
        self._build_schema_snapshot = build_schema_snapshot_fn

    @staticmethod
    def error_signature(execution_result: str) -> str:
        """Build a compact error signature for repeated-error loop detection."""
        if not execution_result:
            return "unknown"

        if "None of [Index(" in execution_result and "are in the [columns]" in execution_result:
            return "missing_required_columns"

        if "Reindexing only valid with uniquely valued Index objects" in execution_result:
            return "concat_non_unique_columns"

        if "SyntaxError:" in execution_result:
            if re.search(r"\n\s*[A-Za-z_]\w*\s*=\s*\n\s*\^", execution_result):
                return "syntax_truncated_assignment"
            return "syntax_error"

        name_error = re.search(r"NameError:\s*name '([^']+)' is not defined", execution_result)
        if name_error:
            return f"name_error:{name_error.group(1)}"

        key_error = re.search(r"KeyError:\s*'([^']+)'", execution_result)
        if key_error:
            return f"key_error:{key_error.group(1)}"

        first_line = re.search(r"Execution error:\s*(.+?)(?:\n|$)", execution_result)
        if first_line:
            return first_line.group(1).strip().lower()

        return "unknown"

    @staticmethod
    def build_loop_breaker_feedback(error_signature: str) -> str:
        """Provide stronger generic guidance when the same error repeats."""
        if error_signature == "missing_required_columns":
            return (
                "LOOP_BREAKER_OFFLINE: repeated missing-column failure.\n"
                "- Rebuild with schema discovery BEFORE merge/select:\n"
                "  all_files = list_all_workbooks()\n"
                "  for file_path in all_files:\n"
                "      wb = get_workbook(file_path)\n"
                "      sheet_name = wb.sheetnames[0]\n"
                "      raw = inspector_multi(file_path, \"A1:Z200\", sheet_name)\n"
                "      df = pd.DataFrame(raw[1:], columns=raw[0]) if raw and len(raw) > 1 else pd.DataFrame()\n"
                "      print(file_path.split('/')[-1], 'columns:', df.columns.tolist())\n"
                "- Only select/merge on columns that are confirmed present in printed columns.\n"
                "- Do not invent semantic column names; map from actual headers."
            )

        if error_signature == "concat_non_unique_columns":
            return (
                "LOOP_BREAKER_OFFLINE: same concat error repeated.\n"
                "- Replace your DataFrame loading block with this safe pattern (task-agnostic):\n"
                "  raw = inspector_multi(file_path, \"A1:Z200\", sheet_name)\n"
                "  header = [str(h).strip() if h is not None else \"\" for h in raw[0]]\n"
                "  keep = [i for i,h in enumerate(header) if h != \"\"]\n"
                "  header = [header[i] for i in keep]\n"
                "  rows = [[r[i] if i < len(r) else None for i in keep] for r in raw[1:]]\n"
                "  seen = {}; uniq = []\n"
                "  for h in header:\n"
                "      n = seen.get(h, 0); seen[h] = n + 1\n"
                "      uniq.append(h if n == 0 else f\"{h}_{n+1}\")\n"
                "  df = pd.DataFrame(rows, columns=uniq)\n"
                "- Use A1-based ranges for all files unless you manually set headers.\n"
                "- After loading, print columns once and continue task-specific computation."
            )

        if error_signature == "syntax_truncated_assignment":
            return (
                "LOOP_BREAKER_OFFLINE: repeated truncated code.\n"
                "- Send a fresh full code block from scratch (prefer <90 lines).\n"
                "- Do NOT leave partial assignment lines like `raw2 =`.\n"
                "- Keep only essential pipeline: load -> compute -> write Output -> save_workbook_to(output_path)."
            )

        if "cycle detected, not a dag" in error_signature:
            return (
                "LOOP_BREAKER_OFFLINE: repeated cycle-detection failure.\n"
                "- Rebuild DAG input with strict filtering:\n"
                "  1) Build task_id_set from task table first.\n"
                "  2) Parse dependencies, and keep edge (pred -> task) ONLY if both IDs are in task_id_set.\n"
                "  3) If predecessor is NaN/blank, treat as root and skip edge.\n"
                "  4) Drop note/example/free-text rows before graph build.\n"
                "- Then rerun topological sort and assert all scheduled IDs cover task_id_set."
            )

        if "no module named 'networkx'" in error_signature or error_signature == "name_error:nx":
            return (
                "LOOP_BREAKER_OFFLINE: repeated unavailable graph-library usage.\n"
                "- Remove all networkx/nx imports and calls.\n"
                "- Implement plain-Python Kahn algorithm only (dict adjacency + in_degree + queue).\n"
                "- Keep code self-contained and runnable in current sandbox."
            )

        if "could not convert string to float" in error_signature and "09:30" in error_signature:
            return (
                "LOOP_BREAKER_OFFLINE: repeated wrong-type casting on time column.\n"
                "- Stop positional casting (row[3]/row[4]).\n"
                "- Cast ONLY duration field to float, keep time fields as datetime/string.\n"
                "- Use explicit column-name access for all numeric conversions."
            )

        return (
            "LOOP_BREAKER_OFFLINE: same runtime error repeated.\n"
            "- Rewrite only the failing block from scratch, keep the rest minimal.\n"
            "- Use runtime helpers only and keep one complete executable code block."
        )

    def build_bounded_error_feedback(self, execution_result: str) -> Optional[str]:
        """Build targeted bounded-mode repair feedback from common execution errors."""
        if not execution_result:
            return None

        sheet_missing = re.search(
            r"Sheet '([^']+)' not found in ([^.\n]+)\. Available sheets: (\[[^\]]*\])",
            execution_result
        )
        if sheet_missing:
            missing_sheet = sheet_missing.group(1)
            workbook_name = sheet_missing.group(2)
            available_sheets = sheet_missing.group(3)
            return (
                "MINIMAL FIX REQUIRED: do not invent sheet names.\n"
                f"- Invalid sheet: '{missing_sheet}' in {workbook_name}\n"
                f"- Use one of available sheets only: {available_sheets}\n"
                "- Keep the same overall code shape; only replace the wrong sheet_name string."
            )

        column_missing = re.search(r"KeyError:\s*'([^']+)'", execution_result)
        if column_missing:
            missing_col = column_missing.group(1)
            if missing_col.endswith(".xlsx") or "/" in missing_col:
                basenames = self._available_workbook_basenames()
                available_str = ", ".join(basenames) if basenames else "(unknown)"
                return (
                    "MINIMAL FIX REQUIRED: workbook key mismatch (basename vs full path).\n"
                    f"- Missing dict key: '{missing_col}'\n"
                    f"- Available workbook basenames now: {available_str}\n"
                    "- Build mapping and read by full path:\n"
                    "  all_files = list_all_workbooks()\n"
                    "  file_by_name = {p.split('/')[-1]: p for p in all_files}\n"
                    "  input_name = sorted(file_by_name.keys())[0]\n"
                    "  file_path = file_by_name[input_name]\n"
                    "  wb = get_workbook(file_path)\n"
                    "  sheet_name = wb.sheetnames[0]\n"
                    "  raw = inspector_multi(file_path, \"A1:Z200\", sheet_name)\n"
                    "- Do not cache DataFrames in a dict with mixed key formats."
                )
            observed_headers = self._observed_header_set()
            if missing_col not in observed_headers:
                schema_snapshot = self._build_schema_snapshot()
                snapshot_block = f"\n- Runtime schema snapshot:\n{schema_snapshot}" if schema_snapshot else ""
                return (
                    "MINIMAL FIX REQUIRED: missing key looks like a hallucinated column.\n"
                    f"- Missing column: '{missing_col}'\n"
                    f"- Observed headers do not include '{missing_col}'.{snapshot_block}\n"
                    "- For multi-file tasks with different schemas, DO NOT concat all files into one DataFrame first.\n"
                    "- Read files separately and keep a dict by basename:\n"
                    "  data_by_file[basename] = df\n"
                    "- For each merge, print both column lists and use only verified join keys."
                )
            return (
                "MINIMAL FIX REQUIRED: do not invent column names.\n"
                f"- Missing column: '{missing_col}'\n"
                "- Print actual columns first with: print('Columns:', df.columns.tolist())\n"
                "- Replace only the wrong column reference with one that exists in printed columns."
            )

        name_error = re.search(r"NameError:\s*name '([^']+)' is not defined", execution_result)
        if name_error:
            missing_name = name_error.group(1)
            if missing_name == "saved_file":
                return (
                    "MINIMAL FIX REQUIRED: final variable `saved_file` is missing.\n"
                    "- End with:\n"
                    "  saved_file = save_workbook_to(output_path)\n"
                    "  print(\"SAVED_FILE:\", saved_file)\n"
                    "  saved_file\n"
                    "- Do not assign to output_path; keep output_path as runtime input variable."
                )
            if missing_name in {"wb", "file_path"}:
                return (
                    "MINIMAL FIX REQUIRED: undefined helper variable in workbook read path.\n"
                    f"- Undefined name: '{missing_name}'\n"
                    "- Define variables in-order for each file:\n"
                    "  wb = get_workbook(file_path)\n"
                    "  sheet_name = wb.sheetnames[0]\n"
                    "  raw = inspector_multi(file_path, \"A1:Z200\", sheet_name)\n"
                    "- Do not use variables before assignment."
                )
            if missing_name == "sheet":
                return (
                    "MINIMAL FIX REQUIRED: do not use raw worksheet object `sheet` for manual cell writes.\n"
                    "- Replace sheet.cell loops with helper flow only:\n"
                    "  create_output_sheet(\"Output\")\n"
                    "  data_2d = [df.columns.tolist()] + df.values.tolist()\n"
                    "  write_dataframe_to_sheet(data_2d, \"Output\", \"A1\")"
                )
            return (
                "MINIMAL FIX REQUIRED: undefined variable/function.\n"
                f"- Undefined name: '{missing_name}'\n"
                "- Define all variables in this turn before use.\n"
                "- If named files are needed, use mapping:\n"
                "  all_files = list_all_workbooks()\n"
                "  file_by_name = {p.split('/')[-1]: p for p in all_files}\n"
                "- Do not reference helper variables before assignment."
            )

        if "No module named 'common_functions'" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: remove external helper imports.\n"
                "- Do NOT import common_functions.\n"
                "- Use runtime-injected helpers directly: list_all_workbooks, inspector_multi, "
                "create_output_sheet, write_dataframe_to_sheet, save_workbook_to."
            )

        if "create_output_workbook" in execution_result and "is not defined" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: create_output_workbook() is not available in this runtime.\n"
                "- Use existing helpers only:\n"
                "  create_output_sheet(\"Output\")\n"
                "  write_dataframe_to_sheet(data_2d, \"Output\", \"A1\")\n"
                "  saved_file = save_workbook_to(output_path)"
            )

        if "write_dataframe_to_sheet() got an unexpected keyword argument" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: wrong write_dataframe_to_sheet signature.\n"
                "- Correct call: write_dataframe_to_sheet(data_2d, \"Output\", \"A1\")\n"
                "- Do not use pandas-style kwargs like startrow/startcol."
            )

        if "unexpected keyword argument 'wb'" in execution_result and "inspector_multi" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: inspector_multi does not accept keyword `wb`.\n"
                "- Correct signature: inspector_multi(file_path, range_ref, sheet_name)\n"
                "- Example:\n"
                "  wb = get_workbook(file_path)\n"
                "  sheet_name = wb.sheetnames[0]\n"
                "  raw = inspector_multi(file_path, \"A1:Z200\", sheet_name)"
            )

        if "Sheet 'Output' not found in output workbook" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: Output sheet missing before write/add_summary_row.\n"
                "- Add this before any write/add_summary_row call:\n"
                "  create_output_sheet(\"Output\")\n"
                "- Then write table with:\n"
                "  data_2d = [df.columns.tolist()] + df.values.tolist()\n"
                "  write_dataframe_to_sheet(data_2d, \"Output\", \"A1\")"
            )

        if "Cannot convert" in execution_result and "to Excel" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: write_dataframe_to_sheet got nested row structure.\n"
                "- Do NOT wrap data_2d with an extra list.\n"
                "- Wrong: data_2d = [[df.columns.tolist()] + df.values.tolist()]\n"
                "- Correct: data_2d = [df.columns.tolist()] + df.values.tolist()"
            )

        if "expected string or bytes-like object, got 'list'" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: wrong parameter type passed to helper.\n"
                "- write_dataframe_to_sheet expects: (data_2d, sheet_name, start_cell)\n"
                "- Ensure sheet_name is a string like \"Output\", not worksheet/list object."
            )

        if "expected str, bytes or os.PathLike object, not NoneType" in execution_result and "get_workbook" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: get_workbook(None) is invalid.\n"
                "- Pass a real file path from list_all_workbooks().\n"
                "- Correct pattern:\n"
                "  all_files = list_all_workbooks()\n"
                "  file_path = all_files[0]\n"
                "  wb = get_workbook(file_path)"
            )

        if "expected str, bytes or os.PathLike object, not Workbook" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: inspector_multi first argument must be FILE PATH STRING, not Workbook object.\n"
                "- Correct signature: inspector_multi(file_path, range_ref, sheet_name)\n"
                "- Example: data = inspector_multi(all_files[0], \"A1:D30\", \"Sheet1\")"
            )

        if "'generator' object has no attribute 'tolist'" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: you are treating worksheet/generator as DataFrame.\n"
                "- First get tabular values via inspector_multi(...)\n"
                "- Then build DataFrame with header row:\n"
                "  data = inspector_multi(all_files[0], \"A1:D30\", \"Sheet1\")\n"
                "  df = pd.DataFrame(data[1:], columns=data[0])"
            )

        if "'list' object has no attribute 'columns'" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: inspector_multi returns list-of-lists, not DataFrame.\n"
                "- Do NOT do: pd.DataFrame(inspector_multi(...))\n"
                "- Correct pattern:\n"
                "  raw = inspector_multi(file_path, \"A1:Z200\", sheet_name)\n"
                "  df = pd.DataFrame(raw[1:], columns=raw[0])\n"
                "- Then use df.columns and merge/groupby operations."
            )

        if "cannot concatenate object of type '<class 'list'>'" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: you are concatenating lists instead of DataFrames.\n"
                "- For each file:\n"
                "  raw = inspector_multi(file_path, \"A1:Z200\", sheet_name)\n"
                "  df = pd.DataFrame(raw[1:], columns=raw[0])\n"
                "- Append DataFrames to a list and then pd.concat(df_list, ignore_index=True)."
            )

        missing_index_cols = re.search(
            r"None of \[Index\(\[(.+?)\], dtype='[^']+'\)\] are in the \[columns\]",
            execution_result,
            flags=re.DOTALL,
        )
        if missing_index_cols:
            raw_cols = missing_index_cols.group(1)
            requested_cols = re.findall(r"'([^']+)'", raw_cols)
            requested_display = ", ".join(requested_cols) if requested_cols else raw_cols
            return (
                "MINIMAL FIX REQUIRED: requested columns are not present in DataFrame.\n"
                f"- Missing requested columns: {requested_display}\n"
                "- Before any df[[...]] or merge(..., on=...), print each DataFrame columns:\n"
                "  print('df_a columns:', df_a.columns.tolist())\n"
                "  print('df_b columns:', df_b.columns.tolist())\n"
                "- Build `needed` and `missing` checks:\n"
                "  needed = ['col1','col2']\n"
                "  missing = [c for c in needed if c not in df.columns]\n"
                "  print('missing:', missing)\n"
                "- Replace invented column names with actual headers from printed columns only."
            )

        if "columns passed, passed data had 0 columns" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: header/row index mapping is wrong.\n"
                "- Keep non-empty header indices from ORIGINAL raw[0] positions.\n"
                "- Use this exact shape-safe extraction:\n"
                "  header_raw = [str(h).strip() if h is not None else \"\" for h in raw[0]]\n"
                "  keep = [i for i,h in enumerate(header_raw) if h != \"\"]\n"
                "  header = [header_raw[i] for i in keep]\n"
                "  rows = [[r[i] if i < len(r) else None for i in keep] for r in raw[1:]]\n"
                "  rows = [row for row in rows if any(v not in (None, \"\") for v in row)]\n"
                "  df = pd.DataFrame(rows, columns=header)\n"
                "- Do not use columns_to_delete for row extraction."
            )

        if "Reindexing only valid with uniquely valued Index objects" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: concat failed because columns are non-unique (often from wrong header row/range).\n"
                "- Read with header row included: use range starting at A1 (not A2) unless you set headers manually.\n"
                "- Build DataFrame with cleaned unique headers:\n"
                "  raw = inspector_multi(file_path, \"A1:Z200\", sheet_name)\n"
                "  header = [str(h).strip() if h is not None else \"\" for h in raw[0]]\n"
                "  keep = [i for i,h in enumerate(header) if h != \"\"]\n"
                "  header = [header[i] for i in keep]\n"
                "  rows = [[r[i] for i in keep] for r in raw[1:]]\n"
                "  seen = {}; uniq = []\n"
                "  for h in header: n = seen.get(h, 0); seen[h] = n + 1; uniq.append(h if n == 0 else f\"{h}_{n+1}\")\n"
                "  df = pd.DataFrame(rows, columns=uniq)\n"
                "- Then concat with ignore_index=True."
            )

        if "unexpected keyword argument 'range_ref'" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: inspector_multi does not accept keyword range_ref.\n"
                "- Use positional args only.\n"
                "- Correct: inspector_multi(file_path, \"A1:D30\", \"Sheet1\")"
            )

        if "missing 1 required positional argument: 'rr'" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: inspector_multi missing range argument.\n"
                "- Pass range_ref as second positional arg.\n"
                "- Correct: inspector_multi(file_path, \"A1:D30\", \"Sheet1\")"
            )

        if "Sheet 'Sheet1' not found" in execution_result and "Available sheets:" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: wrong sheet name assumption.\n"
                "- For CSV-backed workbooks, sheet is often filename-based (not 'Sheet1').\n"
                "- Use dynamic sheet name:\n"
                "  wb = get_workbook(file_path)\n"
                "  sheet_name = wb.sheetnames[0]\n"
                "  raw = inspector_multi(file_path, \"A1:Z200\", sheet_name)"
            )

        if ".xlsx.xlsx" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: file extension duplicated.\n"
                "- Do not append '.xlsx' if file name already ends with '.xlsx'.\n"
                "- Keep required names as full filename and resolve with file_by_name mapping."
            )

        if "One or more required workbooks are missing" in execution_result:
            basenames = self._available_workbook_basenames()
            available_str = ", ".join(basenames) if basenames else "(unknown)"
            return (
                "MINIMAL FIX REQUIRED: workbook existence check is wrong.\n"
                f"- Available workbook basenames now: {available_str}\n"
                "- Use this exact pattern:\n"
                "  all_files = list_all_workbooks()\n"
                "  file_by_name = {p.split('/')[-1]: p for p in all_files}\n"
                "  required = sorted(file_by_name.keys())\n"
                "  missing = [n for n in required if n not in file_by_name]\n"
                "- If missing is empty, read via file_by_name[name] and continue."
            )

        workbook_list_miss = re.search(
            r"File\s+([^.\n]+?\.(?:csv|xlsx|xls))\s+not found(?: in workbook list)?\.?\s*Available files:\s*(\[[^\]]*\])?",
            execution_result,
            flags=re.IGNORECASE,
        )
        if workbook_list_miss:
            missing_name = workbook_list_miss.group(1)
            available_list = workbook_list_miss.group(2) or "[]"
            return (
                "MINIMAL FIX REQUIRED: referenced input file is not loaded in this task.\n"
                f"- Missing filename: {missing_name}\n"
                f"- Runtime available filenames: {available_list}\n"
                "- Use only runtime-provided filenames via file_by_name mapping."
            )

        file_not_found = re.search(
            r"FileNotFoundError:\s*\[Errno\s*2\]\s*No such file or directory:\s*'([^']+)'",
            execution_result
        )
        if file_not_found:
            missing_path = file_not_found.group(1)
            missing_base = os.path.basename(missing_path)
            available = self._available_workbook_basenames()
            available_str = ", ".join(available) if available else "[]"
            exists_by_name = missing_base in set(available)
            if exists_by_name:
                return (
                    "MINIMAL FIX REQUIRED: wrong input path construction.\n"
                    f"- Missing path: {missing_path}\n"
                    f"- Filename exists in loaded inputs: {missing_base}\n"
                    f"- Available input filenames: {available_str}\n"
                    "- Do NOT use pd.read_csv/pd.read_excel or hard-coded paths.\n"
                    "- Use:\n"
                    "  all_files = list_all_workbooks()\n"
                    "  file_by_name = {p.split('/')[-1]: p for p in all_files}\n"
                    "  file_path = file_by_name['" + missing_base + "']\n"
                    "  wb = get_workbook(file_path); sheet_name = wb.sheetnames[0]\n"
                    "  raw = inspector_multi(file_path, \"A1:Z200\", sheet_name)\n"
                    "  df = pd.DataFrame(raw[1:], columns=raw[0])"
                )
            return (
                "MINIMAL FIX REQUIRED: referenced input file/path is not part of loaded task inputs.\n"
                f"- Missing path: {missing_path}\n"
                f"- Available input filenames: {available_str}\n"
                "- Replace with a filename from available list via file_by_name mapping."
            )

        if "attempt to get argmax of an empty sequence" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: idxmax/argmax called on empty filtered data.\n"
                "- Before idxmax(), add guard:\n"
                "  if filtered_df.empty:\n"
                "      row_numbers = []\n"
                "  else:\n"
                "      max_idx = filtered_df['value_col'].idxmax()\n"
                "- Continue writing detailed table and summary even when highlight set is empty."
            )

        if "Cycle detected, not a DAG" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: dependency graph contains cycle after dirty-row ingestion.\n"
                "- Build task_id_set from task table first.\n"
                "- In dependency rows, keep only edges where both task and predecessor are in task_id_set.\n"
                "- Treat empty/NaN predecessor as ROOT (no edge).\n"
                "- Drop note/example rows (for example free-text instructions) before DAG build.\n"
                "- Recompute topological order after filtering and verify scheduled IDs == task_id_set."
            )

        if "Unknown dependency 'nan'" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: NaN dependency should be treated as root task.\n"
                "- Use: if pd.isna(dep) or str(dep).strip() == '': continue\n"
                "- Do NOT create graph edges from NaN/blank dependencies."
            )

        if "could not convert string to float" in execution_result and "09:30" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: wrong column was cast to float (time string detected).\n"
                "- Only cast numeric duration column to float.\n"
                "- Keep Start Time / End Time as datetime or formatted string.\n"
                "- Avoid positional indexing like row[3]/row[4]; use explicit column names."
            )

        if "No module named 'networkx'" in execution_result or "name 'nx' is not defined" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: external graph library is unavailable in runtime.\n"
                "- Remove networkx usage.\n"
                "- Implement DAG ordering with plain-Python Kahn algorithm (dict + in_degree + queue)."
            )

        if "Can only use .str accessor with string values" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: `.str` accessor used on non-string values.\n"
                "- Before any `.str.*` operation, cast the target column safely:\n"
                "  df[col] = df[col].fillna('').astype(str)\n"
                "- If this is a date task, use datetime path instead of `.str`:\n"
                "  df['Date'] = pd.to_datetime(df['Date'], errors='coerce')\n"
                "  filtered = df[df['Date'].dt.month == target_month]\n"
                "- Keep fixes local; do not rewrite unrelated merge/output logic."
            )

        if "'float' object has no attribute 'isnull'" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: scalar float does not have `.isnull()`.\n"
                "- Replace `x.isnull()` with `pd.isna(x)`.\n"
                "- Keep the rest unchanged."
            )

        if "'RangeIndex' object is not callable" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: `.index` is a property, not a function.\n"
                "- Wrong: df.index(...)\n"
                "- Correct: df[condition].index.tolist()\n"
                "- For highlight rows, convert to Output row numbers with header offset:\n"
                "  row_numbers = [i + 2 for i in idx_list]"
            )

        if "'RangeIndex' object cannot be interpreted as an integer" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: `range(df.index)` is invalid because index is not an int.\n"
                "- Use concrete list of indices:\n"
                "  idx_list = df[condition].index.tolist()\n"
                "  row_numbers = [i + 2 for i in idx_list]\n"
                "- Pass row_numbers directly to highlight_rows(...)."
            )

        if "Error highlighting rows" in execution_result and "'<' not supported between instances of 'list' and 'int'" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: highlight_rows received nested list instead of flat int list.\n"
                "- Wrong: highlight_rows(\"Output\", [[...]], {...})\n"
                "- Correct: highlight_rows(\"Output\", [2, 8, 15], {...})\n"
                "- Ensure each row number is an integer."
            )

        syntax_err = re.search(r"SyntaxError:\s*(.+)", execution_result)
        if syntax_err:
            syntax_detail = syntax_err.group(1)
            lower_detail = syntax_detail.lower()
            if re.search(r"\n\s*//", execution_result):
                return (
                    "MINIMAL FIX REQUIRED: invalid Python comment style.\n"
                    "- Replace every `// ...` with `# ...` (or remove comments).\n"
                    "- Keep one complete Python code block only."
                )
            if "unexpected eof" in lower_detail or "unterminated" in lower_detail or "eol while scanning string literal" in lower_detail:
                return (
                    "MINIMAL FIX REQUIRED: response was likely truncated or has unclosed literal.\n"
                    "- Re-send a complete, shorter code block (<120 lines) with valid closing backticks.\n"
                    "- Avoid partial variable names/strings and ensure all brackets/quotes are closed.\n"
                    "- Keep only essential steps: load -> merge -> write Output -> save_workbook_to(output_path)."
                )
            if "invalid syntax" in lower_detail and re.search(r"\n\s*[A-Za-z_]\w*\s*=\s*\n\s*\^", execution_result):
                return (
                    "MINIMAL FIX REQUIRED: code is truncated mid-assignment (for example `raw2 =`).\n"
                    "- Re-send one complete code block; do not leave any partial line.\n"
                    "- Keep code shorter (<120 lines) and fully closed with ```.\n"
                    "- Keep only essential steps: load -> compute -> write Output -> save_workbook_to(output_path)."
                )
            return (
                "MINIMAL FIX REQUIRED: syntax error.\n"
                "- Keep code minimal and valid Python; avoid renaming variables mid-line.\n"
                "- Ensure all identifiers use underscores only and are defined before use.\n"
                "- Re-emit one complete executable code block."
            )

        return None
