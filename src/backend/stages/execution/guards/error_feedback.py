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
                "      table = read_table_multi(file_path, sheet_name, \"A1:Z200\")\n"
                "      df = pd.DataFrame(table[\"rows\"], columns=table[\"header\"]) if table[\"header\"] else pd.DataFrame()\n"
                "      print(file_path.split('/')[-1], 'columns:', df.columns.tolist())\n"
                "- Only select/merge on columns that are confirmed present in printed columns.\n"
                "- Do not invent semantic column names; map from actual headers."
            )

        if error_signature == "concat_non_unique_columns":
            return (
                "LOOP_BREAKER_OFFLINE: same concat error repeated.\n"
                "- Replace your DataFrame loading block with this safe pattern (task-agnostic):\n"
                "  table = read_table_multi(file_path, sheet_name, \"A1:Z200\")\n"
                "  header = table[\"header\"]\n"
                "  rows = table[\"rows\"]\n"
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

        if "schema mismatch between files" in error_signature:
            return (
                "LOOP_BREAKER_OFFLINE: repeated same-schema assumption on multi-file task.\n"
                "- Stop comparing all file headers for equality.\n"
                "- Load each workbook separately, print columns, and assign table roles from verified headers.\n"
                "- Keep complementary tables separate (for example task table vs dependency table).\n"
                "- Only concat tables that truly share the same role and same headers."
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

        if "Schema mismatch between files." in execution_result:
            return (
                "MINIMAL FIX REQUIRED: different file roles do not need matching schemas.\n"
                "- Do NOT assert same schema across all input files.\n"
                "- Keep each workbook as its own DataFrame and identify role by verified headers.\n"
                "- Task table: `Task ID` + duration/name/priority-like columns.\n"
                "- Dependency table: `Task ID` + `Depends on`.\n"
                "- Only concat tables that truly have the same role and same headers."
            )

        if (
            "Could not identify the P&L, sales/marketing, and KPI target tables." in execution_result
            or "No structured table matched headers" in execution_result
        ):
            return (
                "MINIMAL FIX REQUIRED: this dashboard task should use the single runtime helper path.\n"
                "- Use exactly:\n"
                "  `dashboard_result = build_financial_dashboard_report()`\n"
                "  `create_output_sheet('Output')`\n"
                "  `write_dataframe_to_sheet(dashboard_result['detail_data'], 'Output', 'A1')`\n"
                "  `saved_file = save_workbook_to(output_path)`\n"
                "- Do not manually parse header rows or rebuild the dashboard in code."
            )

        if "No candidate tables were loaded." in execution_result:
            return (
                "MINIMAL FIX REQUIRED: this screening task should use the single runtime helper path.\n"
                "- Use exactly:\n"
                "  `screening_result = build_candidate_screening_report()`\n"
                "  `create_output_sheet('Output')`\n"
                "  `write_dataframe_to_sheet(screening_result['detail_data'], 'Output', 'A1')`\n"
                "  `saved_file = save_workbook_to(output_path)`\n"
                "- Do not manually load or concatenate candidate files in code."
            )

        if "No inventory parameter table was loaded." in execution_result:
            return (
                "MINIMAL FIX REQUIRED: this EOQ task should use the single runtime helper path.\n"
                "- Use exactly:\n"
                "  `inventory_result = build_inventory_eoq_report()`\n"
                "  `create_output_sheet('Output')`\n"
                "  `write_dataframe_to_sheet(inventory_result['detail_data'], 'Output', 'A1')`\n"
                "  `saved_file = save_workbook_to(output_path)`\n"
                "- Do not manually parse parameters or build EOQ tables in code."
            )

        if "Hospital utilisation workflow expects patient, service, and staff tables." in execution_result:
            return (
                "MINIMAL FIX REQUIRED: this hospital task should use the single runtime helper path.\n"
                "- Use exactly:\n"
                "  `report = build_hospital_utilisation_report()`\n"
                "  `create_output_sheet('Output')`\n"
                "  `write_dataframe_to_sheet(report['detail_data'], 'Output', 'A1')`\n"
                "  `if report['highlight_rows']:` then highlight them; otherwise print `NO_HIGHLIGHT_ROWS:`.\n"
                "- Do not manually merge the patient/service/staff tables in code."
            )

        if "No module named 'plotnine'" in execution_result or "No module named 'seaborn'" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: do not import extra plotting libraries in this task.\n"
                "- `plt` is already available in the sandbox.\n"
                "- Keep the helper path:\n"
                "  `analysis = build_region_growth_analysis(all_files[0], sheet_name='Data', start_year=2020, end_year=2024)`\n"
                "  `chart_df = analysis['chart_df']`\n"
                "  `for region in analysis['region_columns']: plt.plot(chart_df['Year'], chart_df[region], label=region)`\n"
                "  `plt.xlabel('Year')`; `plt.ylabel('Penetration Rate')`; `plt.legend()`\n"
                "  `save_plot_to_excel('Output', 'F2')`\n"
                "- Remove `plotnine`, `seaborn`, and other external plot imports."
            )

        if (
            "No module named 'runtime_path'" in execution_result
            or "No module named 'runtime'" in execution_result
            or "No module named 'graph_helper'" in execution_result
            or "No module named 'excel_output'" in execution_result
        ):
            return (
                "MINIMAL FIX REQUIRED: do not import runtime helper modules.\n"
                "- Helper functions are already injected into the sandbox globals.\n"
                "- Remove imports like `from runtime import ...`, `from runtime_path import ...`, "
                "`from graph_helper import ...`, and `from excel_output import ...`.\n"
                "- Call the helpers directly."
            )

        if "'list' object has no attribute 'columns'" in execution_result or "'list' object has no attribute 'values'" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: helper `detail_data` output was treated like a DataFrame.\n"
                "- `...['detail_data']` is already a ready-to-write 2D table payload.\n"
                "- Write it directly:\n"
                "  `write_dataframe_to_sheet(result['detail_data'], 'Output', 'A1')`\n"
                "- Or use the DataFrame alias instead:\n"
                "  `write_dataframe_to_sheet(result['output_df'], 'Output', 'A1')`"
            )

        if "KeyError: 'coef'" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: the regression helper does not return a `coef` key.\n"
                "- Use the provided outputs instead:\n"
                "  `regression_result['output_df']`\n"
                "  `regression_result['detail_data']`\n"
                "  `regression_result['coefficients_df']`\n"
                "- Write `regression_result['output_df']` directly to Output."
            )

        if (
            "Column 'Task Name' not found in" in execution_result
            or "Column 'Priority' not found in" in execution_result
            or "Column 'Duration (hours)' not found in" in execution_result
        ):
            return (
                "MINIMAL FIX REQUIRED: `build_dependency_schedule(...)` was given the wrong task table shape.\n"
                "- Do NOT construct a simplified `pd.DataFrame({...})` before calling the helper.\n"
                "- Select tables with `find_table_by_headers(...)` and pass the original DataFrames directly:\n"
                "  `schedule_result = build_dependency_schedule(task_table['df'], dependency_table['df'], start_time='08:00')`\n"
                "- The helper requires real task metadata columns like `Task Name`, `Duration (hours)`, and `Priority`."
            )

        column_missing = re.search(r"KeyError:\s*'([^']+)'", execution_result)
        if column_missing:
            missing_col = column_missing.group(1)
            if re.fullmatch(r"[A-Za-z]+\d+", missing_col):
                return (
                    "MINIMAL FIX REQUIRED: graph/task lookup failed on a task ID, not on a column name.\n"
                    f"- Missing task ID during scheduling: '{missing_col}'\n"
                    "- Rebuild task and dependency tables from `table['rows']` + `table['header']` without dropping the first data row.\n"
                    "- Keep blank/NaN `Depends on` as ROOT (no incoming edge).\n"
                    "- Build adjacency/in_degree only from task IDs that exist in the task table."
                )
            if missing_col.strip().lower() == "depends on":
                return (
                    "MINIMAL FIX REQUIRED: dependency column missing, likely wrong file/sheet loaded.\n"
                    "- Expected dependency schema: ['Task ID', 'Depends on'].\n"
                    "- In multi-file tasks, read each workbook via read_table_multi(file_path, sheet_name, range_ref).\n"
                    "- Normalize headers before checks:\n"
                    "  df.columns = [str(c).replace('_x000D_', '').replace('_x000d_', '').strip() for c in df.columns]\n"
                    "- Assert required columns before DAG construction."
                )
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
                    "  table = read_table_multi(file_path, sheet_name, \"A1:Z200\")\n"
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

        if "KeyError: nan" in execution_result or re.search(r"Execution error:\s*nan(?:\n|$)", execution_result):
            return (
                "MINIMAL FIX REQUIRED: blank/NaN dependency was used as a graph key.\n"
                "- Treat blank or NaN `Depends on` as ROOT and skip edge creation.\n"
                "- Use exactly:\n"
                "  if pd.isna(dep) or str(dep).strip() == '':\n"
                "      continue\n"
                "  adjacency[dep].append(task_id)\n"
                "  in_degree[task_id] += 1"
            )

        if "float() argument must be a string or a real number, not 'Series'" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: `float(...)` was called on a filtered pandas Series.\n"
                "- Select one task row first, then read scalar fields from that row.\n"
                "- Use exactly:\n"
                "  task_row = task_df.loc[task_df['Task ID'] == task_id].iloc[0]\n"
                "  duration_minutes = int(round(float(task_row['Duration (hours)']) * 60))\n"
                "  task_name = task_row['Task Name']\n"
                "  priority = task_row['Priority']\n"
                "- Do not wrap `task_df[task_df['Task ID'] == task_id]['Duration (hours)']` directly with `float(...)`."
            )

        if "tuple indices must be integers or slices, not str" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: a `(index, row)` tuple from `iterrows()` was treated like a row object.\n"
                "- Replace `for row in df.iterrows():` with `for _, row in df.iterrows():` before any `row['col']` access.\n"
                "- For total duration, prefer the column directly:\n"
                "  total_duration_hours = pd.to_numeric(task_df['Duration (hours)'], errors='coerce').sum()\n"
                "  total_duration_minutes = int(round(total_duration_hours * 60))\n"
                "- Do not access `row['Duration (hours)']` if `row` came from plain `iterrows()` without unpacking."
            )

        if "The truth value of a DataFrame is ambiguous" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: a pandas DataFrame was used directly in an `if` condition.\n"
                "- Use `is None` to check whether the task/dependency DataFrame was found.\n"
                "- Correct shape:\n"
                "  task_df = None\n"
                "  dependency_df = None\n"
                "  ...\n"
                "  if task_df is None or dependency_df is None:\n"
                "      raise ValueError('Missing either task table or dependency table')\n"
                "- Do not write `if not task_df` or `if task_df:`."
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
                    "  table = read_table_multi(file_path, sheet_name, \"A1:Z200\")\n"
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
                "- Use runtime-injected helpers directly: list_all_workbooks, read_table_multi, "
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

        if "unexpected keyword argument 'wb'" in execution_result and "read_table_multi" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: read_table_multi does not accept keyword `wb`.\n"
                "- Correct signature: read_table_multi(file_path, sheet_name, range_ref)\n"
                "- Example:\n"
                "  wb = get_workbook(file_path)\n"
                "  sheet_name = wb.sheetnames[0]\n"
                "  table = read_table_multi(file_path, sheet_name, \"A1:Z200\")"
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
                "MINIMAL FIX REQUIRED: read_table_multi first argument must be FILE PATH STRING, not Workbook object.\n"
                "- Correct signature: read_table_multi(file_path, sheet_name, range_ref)\n"
                "- Example: table = read_table_multi(all_files[0], \"Sheet1\", \"A1:D30\")"
            )

        if "'generator' object has no attribute 'tolist'" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: you are treating worksheet/generator as DataFrame.\n"
                "- First get cleaned tabular values via read_table_multi(...)\n"
                "- Then build DataFrame with header row:\n"
                "  table = read_table_multi(all_files[0], \"Sheet1\", \"A1:D30\")\n"
                "  df = pd.DataFrame(table[\"rows\"], columns=table[\"header\"])"
            )

        if "'list' object has no attribute 'columns'" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: read_table_multi returns a table dict, not a DataFrame.\n"
                "- Do NOT do: pd.DataFrame(read_table_multi(...))\n"
                "- Correct pattern:\n"
                "  table = read_table_multi(file_path, sheet_name, \"A1:Z200\")\n"
                "  df = pd.DataFrame(table[\"rows\"], columns=table[\"header\"])\n"
                "- Then use df.columns and merge/groupby operations."
            )

        if "cannot concatenate object of type '<class 'list'>'" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: you are concatenating lists instead of DataFrames.\n"
                "- For each file:\n"
                "  table = read_table_multi(file_path, sheet_name, \"A1:Z200\")\n"
                "  df = pd.DataFrame(table[\"rows\"], columns=table[\"header\"])\n"
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

        not_in_index = re.search(r"Execution error:\s*\"?\[([^\]]+)\]\s+not in index\"?", execution_result)
        if not_in_index:
            requested_cols = [c.strip().strip("'").strip('"') for c in not_in_index.group(1).split(",")]
            requested_display = ", ".join([c for c in requested_cols if c])
            return (
                "MINIMAL FIX REQUIRED: selected columns are missing in current DataFrame.\n"
                f"- Missing selection: {requested_display}\n"
                "- Print columns and select by intersection only:\n"
                "  want = ['col1','col2']\n"
                "  present = [c for c in want if c in df.columns]\n"
                "  missing = [c for c in want if c not in df.columns]\n"
                "  print('missing columns:', missing)\n"
                "  df_selected = df[present].copy()\n"
                "- Do not assume columns exist without checking."
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
                "  table = read_table_multi(file_path, sheet_name, \"A1:Z200\")\n"
                "  header = table[\"header\"]\n"
                "  rows = table[\"rows\"]\n"
                "  seen = {}; uniq = []\n"
                "  for h in header: n = seen.get(h, 0); seen[h] = n + 1; uniq.append(h if n == 0 else f\"{h}_{n+1}\")\n"
                "  df = pd.DataFrame(rows, columns=uniq)\n"
                "- Then concat with ignore_index=True."
            )

        if "unexpected keyword argument 'range_ref'" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: read_table_multi does not accept keyword range_ref.\n"
                "- Use positional args only.\n"
                "- Correct: read_table_multi(file_path, \"Sheet1\", \"A1:D30\")"
            )

        if "missing 1 required positional argument: 'rr'" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: read_table_multi missing range argument.\n"
                "- Pass range_ref as third positional arg.\n"
                "- Correct: read_table_multi(file_path, \"Sheet1\", \"A1:D30\")"
            )

        if "Sheet '" in execution_result and "not found" in execution_result and "Available sheets:" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: wrong sheet/workbook selection.\n"
                "- Do not hard-code sheet names like 'Sheet1'.\n"
                "- In multi-file tasks, read per file with read_table_multi(...).\n"
                "- Use dynamic sheet name per file:\n"
                "  wb = get_workbook(file_path)\n"
                "  sheet_name = wb.sheetnames[0]\n"
                "  table = read_table_multi(file_path, sheet_name, \"A1:Z200\")"
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

        simple_runtime_file_missing = re.search(
            r"Execution error:\s*File '([^']+\.(?:csv|xlsx|xls))' not found\.",
            execution_result,
            flags=re.IGNORECASE,
        )
        if simple_runtime_file_missing:
            missing_name = simple_runtime_file_missing.group(1)
            return (
                "MINIMAL FIX REQUIRED: membership check used basename against full path list.\n"
                f"- Missing filename: {missing_name}\n"
                "- Do not use: `if file_name not in all_files`.\n"
                "- Use exact mapping:\n"
                "  all_files = list_all_workbooks()\n"
                "  file_by_name = {p.split('/')[-1]: p for p in all_files}\n"
                "  file_path = file_by_name['" + missing_name + "']\n"
                "- Then read via `get_workbook(file_path)` + `read_table_multi(...)`."
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
                    "  table = read_table_multi(file_path, sheet_name, \"A1:Z200\")\n"
                    "  df = pd.DataFrame(table[\"rows\"], columns=table[\"header\"])"
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

        if "unsupported operand type(s) for +: 'int' and 'str'" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: time arithmetic is mixing integers and strings.\n"
                "- Keep scheduling time as integer minutes only:\n"
                "  current_minutes = 8 * 60\n"
                "  end_minutes = current_minutes + int(round(duration * 60))\n"
                "- Format only when writing output:\n"
                "  start_str = f\"{current_minutes // 60:02d}:{current_minutes % 60:02d}\"\n"
                "  end_str = f\"{end_minutes // 60:02d}:{end_minutes % 60:02d}\""
            )

        if re.search(r"invalid literal for int\(\) with base 10:\s*'t\d+'", execution_result, flags=re.IGNORECASE):
            return (
                "MINIMAL FIX REQUIRED: task IDs like `T1` are string labels, not integers.\n"
                "- Do NOT cast `Task ID` or `Depends on` to `int`.\n"
                "- Keep graph nodes as the exact string IDs from the sheets.\n"
                "- Use:\n"
                "  task_id_set = set(task_df['Task ID'])\n"
                "  adjacency = {task_id: [] for task_id in task_id_set}\n"
                "  in_degree = {task_id: 0 for task_id in task_id_set}\n"
                "- Build edges with `adjacency[depends_on].append(task_id)` and `in_degree[task_id] += 1`."
            )

        if "invalid literal for int() with base 10:" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: a string value was multiplied before numeric conversion.\n"
                "- Convert duration/text values to float before `* 60`.\n"
                "- Correct pattern:\n"
                "  df_tasks['Duration (hours)'] = pd.to_numeric(df_tasks['Duration (hours)'], errors='raise').astype(float)\n"
                "  duration_minutes = int(round(float(duration_value) * 60))\n"
                "- Do not do `int(string_value * 60)`."
            )

        if "unsupported operand type(s) for -: 'list' and 'set'" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: task coverage comparison is mixing list and set types.\n"
                "- Build `task_id_set` as a real set:\n"
                "  task_id_set = set(task_df['Task ID'])\n"
                "- Build `scheduled_task_ids` as a set before comparison.\n"
                "- Do not use `.tolist()` for the task-id coverage assertion."
            )

        if "type str doesn't define __round__ method" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: duration is still a string.\n"
                "- Convert duration column once before scheduling:\n"
                "  df_tasks['Duration (hours)'] = pd.to_numeric(df_tasks['Duration (hours)'], errors='raise').astype(float)\n"
                "- Do not call round() on raw string values."
            )

        if "name 'completion_times' is not defined" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: completion_times must be initialized before the scheduling loop.\n"
                "- Add before loop: `completion_times = {}`\n"
                "- Keep all completion values in integer minutes, not strings."
            )

        if "could not convert string to float" in execution_result and "09:30" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: wrong column was cast to float (time string detected).\n"
                "- Only cast numeric duration column to float.\n"
                "- Keep Start Time / End Time as datetime or formatted string.\n"
                "- Avoid positional indexing like row[3]/row[4]; use explicit column names."
            )

        if "could not convert string to float: 'male'" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: categorical text is entering numeric correlation input.\n"
                "- Encode categorical columns before correlation:\n"
                "  df['Sex_num'] = df['Sex'].map({'male': 0, 'female': 1})\n"
                "- Or compute correlation on numeric-only frame:\n"
                "  num_df = df.select_dtypes(include=['number']).copy()\n"
                "- Do not include raw text columns in `corr()` input."
            )

        if "could not convert string to float: ''" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: empty strings are being cast to float.\n"
                "- Before numeric conversion, normalize blanks:\n"
                "  s = series.replace('', None)\n"
                "  s = pd.to_numeric(s, errors='coerce')\n"
                "- Run correlation/aggregation on rows where required numeric columns are non-null."
            )

        if "float() argument must be a string or a real number, not 'NAType'" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: pandas NA values are passed into float().\n"
                "- Replace direct float(...) casts with:\n"
                "  num = pd.to_numeric(series, errors='coerce')\n"
                "- Drop or fill NaN before downstream numeric operations."
            )

        if "Expected value of kwarg 'errors' to be one of ['raise', 'ignore']. Supplied value is 'coerce'" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: `astype(..., errors='coerce')` is invalid.\n"
                "- Use `pd.to_numeric(series, errors='coerce')` for coercion.\n"
                "- Keep `astype(float)` only when data is already clean."
            )

        if "All arrays must be of the same length" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: output DataFrame/dict columns have different lengths.\n"
                "- Build output from one aligned DataFrame slice, not separate independent arrays.\n"
                "- Example:\n"
                "  cols = ['A','B','C']\n"
                "  present = [c for c in cols if c in df.columns]\n"
                "  out_df = df[present].copy()\n"
                "- Then write `out_df` directly."
            )

        if "Invalid type <class 'str'>. Must be int or float." in execution_result:
            return (
                "MINIMAL FIX REQUIRED: time arithmetic received string duration values.\n"
                "- Convert duration to float before scheduling:\n"
                "  tasks['Duration (hours)'] = pd.to_numeric(tasks['Duration (hours)'], errors='raise').astype(float)\n"
                "- Use numeric duration only in timedelta calculations."
            )

        if "No module named 'networkx'" in execution_result or "name 'nx' is not defined" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: external graph library is unavailable in runtime.\n"
                "- Remove networkx usage.\n"
                "- Implement DAG ordering with plain-Python Kahn algorithm (dict + in_degree + queue)."
            )

        if "No module named 'sklearn'" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: sklearn is unavailable in runtime.\n"
                "- Do not import sklearn.\n"
                "- For linear regression, use numpy least squares instead:\n"
                "  import numpy as np\n"
                "  X = df[feature_cols].apply(pd.to_numeric, errors='coerce')\n"
                "  y = pd.to_numeric(df[target_col], errors='coerce')\n"
                "  tmp = pd.concat([X, y], axis=1).dropna()\n"
                "  A = np.c_[np.ones(len(tmp)), tmp[feature_cols].to_numpy(float)]\n"
                "  b = tmp[target_col].to_numpy(float)\n"
                "  beta = np.linalg.lstsq(A, b, rcond=None)[0]\n"
                "- Then write coefficients table to Output and save."
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
            if "return outside function" in lower_detail:
                return (
                    "MINIMAL FIX REQUIRED: `return` used at top level.\n"
                    "- Remove top-level `return` statements.\n"
                    "- End script with final expression `saved_file` instead."
                )
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
