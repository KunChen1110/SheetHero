"""Execution runtime loop for multi-turn analysis."""

import os
import re
from typing import Dict, Any, Optional

from ...log.logger_registry import LoggerRegistry
from .executor import CodeExecutor
from .history import ExecutionHistory
from .llm_client import ExecutionLLMClient
from .parser import ExecutionResponseParser
from .summary import ExecutionSummary
from ..base.runtime import StageRuntime
from ...prompt.prompt_builder import PromptBuilder

logger = LoggerRegistry.setup_logger(__name__)


class ExecutionRuntime(StageRuntime):
    """Runs the execution loop with LLM responses and code execution."""

    def __init__(self, client, deployment: str, sandbox,
                 excel_context_execution: str,
                 output_instruction: Optional[str] = None, progress_log_file=None,
                 prompt_profile: str = "offline_strict"):
        super().__init__(progress_log_file)
        self.client = client
        self.deployment = deployment
        self.sandbox = sandbox
        self.excel_context_execution = excel_context_execution
        self.output_instruction = output_instruction or ""
        self.use_bounded_execution = True
        self.prompt_builder = PromptBuilder(profile=prompt_profile)

        self.llm_client = ExecutionLLMClient(client, deployment)
        self.parser = ExecutionResponseParser()
        self.executor = CodeExecutor(sandbox)
        self.history_formatter = ExecutionHistory()
        self.summary_builder = ExecutionSummary()

        self.conversation_history = []
        self._consecutive_forbidden = 0
        self._consecutive_format_errors = 0
        self._bounded_exec_max_tokens = (
            int(os.getenv("SHEETHERO_EXECUTION_MAX_TOKENS", "4096"))
            if self.use_bounded_execution else None
        )
        self._max_format_errors = int(os.getenv("SHEETHERO_MAX_FORMAT_ERRORS", "3"))
        self._max_forbidden_before_hard_reset = int(
            os.getenv("SHEETHERO_MAX_FORBIDDEN_BEFORE_RESET", "2")
        )
        self._max_same_error_streak = int(
            os.getenv("SHEETHERO_MAX_SAME_ERROR_STREAK", "2")
        )
        self._last_error_signature: Optional[str] = None
        self._same_error_streak = 0

    def _get_system_prompt(self) -> dict:
        system_content = self.prompt_builder.build_execution_system_prompt(
            self.output_instruction,
            use_bounded_execution=self.use_bounded_execution,
        )
        return {"role": "system", "content": system_content}

    @staticmethod
    def _extract_saved_path_from_result(execution_result: str) -> Optional[str]:
        """Extract saved file path from executor stdout (auto-stop when save detected)."""
        if not execution_result:
            return None
        # Match with or without emoji/prefix: "Workbook saved to: /path" or "💾 Workbook saved to: /path"
        # Allow any leading non-newline (e.g. emoji + space) before "Workbook saved to:"
        m = re.search(r"Workbook saved to:\s*(.+?)(?:\n|$)", execution_result)
        if m:
            path = m.group(1).strip()
            if path and not path.startswith("("):
                return path
        m = re.search(r"SAVED_FILE:\s*(.+?)(?:\n|$)", execution_result)
        if m:
            path = m.group(1).strip()
            if path:
                return path
        return None

    @staticmethod
    def _extract_rows_written(execution_result: str) -> list[int]:
        """Parse row counts from helper logs like 'Wrote N rows to Output!A1:B10'."""
        if not execution_result:
            return []
        matches = re.findall(r"Wrote\s+(\d+)\s+rows\s+to", execution_result, flags=re.IGNORECASE)
        rows = []
        for m in matches:
            try:
                rows.append(int(m))
            except Exception:
                continue
        return rows

    def _has_meaningful_output_rows(self, execution_result: str) -> bool:
        """
        Require at least 2 written rows in bounded mode (header + >=1 data row).
        Prevents false success when model writes placeholder header only.
        """
        if not self.use_bounded_execution:
            return True
        rows = self._extract_rows_written(execution_result)
        if not rows:
            return False
        return max(rows) >= 2

    @staticmethod
    def _parse_output_contract_flag(understanding_output: str, key: str) -> Optional[bool]:
        """Parse YES/NO contract flags from understanding output."""
        if not understanding_output:
            return None
        pattern = rf"{re.escape(key)}\s*:\s*(YES|NO|TRUE|FALSE)"
        m = re.search(pattern, understanding_output, flags=re.IGNORECASE)
        if not m:
            return None
        value = m.group(1).strip().upper()
        return value in {"YES", "TRUE"}

    def _extract_output_contract(self, understanding_output: str) -> Dict[str, Optional[bool]]:
        """Extract structured output intent contract from understanding stage text."""
        return {
            "requires_detailed_table": self._parse_output_contract_flag(
                understanding_output, "requires_detailed_table"
            ),
            "requires_highlight": self._parse_output_contract_flag(
                understanding_output, "requires_highlight"
            ),
            "requires_summary_metrics": self._parse_output_contract_flag(
                understanding_output, "requires_summary_metrics"
            ),
        }

    def _build_output_intent_feedback(self, execution_result: str,
                                      output_contract: Dict[str, Optional[bool]]) -> Optional[str]:
        """
        Validate that saved output matches question intent.
        Prevents premature success when model writes wrong output shape.
        """
        if not self.use_bounded_execution:
            return None

        need_detail = output_contract.get("requires_detailed_table") is True
        need_highlight = output_contract.get("requires_highlight") is True

        rows = self._extract_rows_written(execution_result)
        max_rows = max(rows) if rows else 0
        lower_result = (execution_result or "").lower()

        if need_detail and max_rows < 6:
            return (
                "OUTPUT_INTENT_MISMATCH_OFFLINE: question requires detailed table output, "
                "but current saved output is too small (likely metric-only).\n"
                "- Rebuild output as: detailed merged table first, then summary metrics.\n"
                "- Do not output only `Metric|Value` for merge/combine table tasks."
            )

        if need_highlight and "highlighted row(s)" not in lower_result:
            return (
                "OUTPUT_INTENT_MISMATCH_OFFLINE: question requires highlighting (for example max day in red), "
                "but no highlight evidence found.\n"
                "- After writing detailed table, call:\n"
                "  highlight_rows(\"Output\", row_numbers, {\"fill_color\": \"red\"})\n"
                "- Do not use HTML tags for highlighting."
            )

        return None

    def _create_initial_user_prompt(self, understanding_output: str,
                                    user_question: str) -> dict:
        bounded_understanding = understanding_output
        if self.use_bounded_execution:
            bounded_understanding = (
                "Offline bounded mode: treat this section as low-confidence hint only. "
                "If it conflicts with Sheet Content or runtime errors, ignore it."
            )
        user_content = self.prompt_builder.build_execution_user_prompt(
            self.excel_context_execution,
            bounded_understanding,
            user_question,
        )
        if self.use_bounded_execution:
            basenames = self._available_workbook_basenames()
            if basenames:
                file_lines = "\n".join(f"- `{name}`" for name in basenames)
                user_content += (
                    "\n\n**AVAILABLE INPUT FILES (STRICT):**\n"
                    f"{file_lines}\n"
                    "Use ONLY these names for input lookups."
                )
            schema_snapshot = self._build_schema_snapshot()
            if schema_snapshot:
                user_content += (
                    "\n\n**SCHEMA SNAPSHOT (RUNTIME, TRUST THIS):**\n"
                    f"{schema_snapshot}\n"
                    "Use these real headers for all select/merge operations. Do not invent columns."
                )
        return {"role": "user", "content": user_content}

    def _available_workbook_basenames(self) -> list[str]:
        """Return loaded workbook base names for repair hints."""
        try:
            workbooks = self.sandbox.workbooks or {}
            return [os.path.basename(str(path)) for path in workbooks.keys()]
        except Exception:
            return []

    def _build_schema_snapshot(self) -> str:
        """Build a compact schema snapshot (sheet + header row) from loaded workbooks."""
        try:
            workbooks = self.sandbox.workbooks or {}
            lines: list[str] = []
            for path, wb in workbooks.items():
                base = os.path.basename(str(path))
                sheet_name = wb.sheetnames[0] if getattr(wb, "sheetnames", None) else "(no_sheet)"
                headers: list[str] = []
                if getattr(wb, "sheetnames", None):
                    ws = wb[sheet_name]
                    # Use first non-empty row within first 5 rows as header candidate.
                    for row_idx in range(1, 6):
                        row_values = []
                        for c in range(1, 61):
                            value = ws.cell(row=row_idx, column=c).value
                            text = str(value).strip() if value is not None else ""
                            row_values.append(text)
                        candidate = [v for v in row_values if v != ""]
                        if candidate:
                            headers = candidate[:20]
                            break
                header_text = ", ".join(headers) if headers else "(no_detected_header)"
                lines.append(f"- `{base}` | sheet=`{sheet_name}` | columns={header_text}")
            return "\n".join(lines)
        except Exception:
            return ""

    def _detect_unknown_filename_lookup(self, code_action: str) -> Optional[str]:
        """Detect literal input filename lookups that are not in loaded workbook names."""
        if not self.use_bounded_execution:
            return None
        if not code_action or not code_action.strip():
            return None

        available = set(self._available_workbook_basenames())
        if not available:
            return None

        patterns = [
            r"file_by_name\[\s*['\"]([^'\"]+\.(?:csv|xlsx|xls))['\"]\s*\]",
            r"workbooks\[\s*['\"]([^'\"]+\.(?:csv|xlsx|xls))['\"]\s*\]",
            r"data_frames\[\s*['\"]([^'\"]+\.(?:csv|xlsx|xls))['\"]\s*\]",
            r"required_files\s*=\s*\[([^\]]+)\]",
        ]

        referenced: list[str] = []
        for idx, pattern in enumerate(patterns):
            matches = re.findall(pattern, code_action, flags=re.IGNORECASE)
            if not matches:
                continue
            if idx == 3:
                for raw_list in matches:
                    referenced.extend(
                        re.findall(r"['\"]([^'\"]+\.(?:csv|xlsx|xls))['\"]", raw_list, flags=re.IGNORECASE)
                    )
            else:
                referenced.extend(matches)

        unknown = sorted({
            os.path.basename(name) for name in referenced
            if os.path.basename(name) not in available
        })
        if not unknown:
            return None

        available_str = ", ".join(sorted(available))
        unknown_str = ", ".join(unknown)
        return (
            "GROUNDING_VIOLATION_OFFLINE: code references input filename(s) not loaded in this task.\n"
            f"- Unknown referenced names: {unknown_str}\n"
            f"- Available input filenames: {available_str}\n"
            "- Fix by using: all_files = list_all_workbooks(); "
            "file_by_name = {p.split('/')[-1]: p for p in all_files}"
        )

    @staticmethod
    def _error_signature(execution_result: str) -> str:
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

    def _update_error_streak(self, execution_result: str) -> str:
        """Update repeated error streak state and return current signature."""
        signature = self._error_signature(execution_result)
        if signature == self._last_error_signature:
            self._same_error_streak += 1
        else:
            self._last_error_signature = signature
            self._same_error_streak = 1
        return signature

    @staticmethod
    def _build_loop_breaker_feedback(error_signature: str) -> str:
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

        return (
            "LOOP_BREAKER_OFFLINE: same runtime error repeated.\n"
            "- Rewrite only the failing block from scratch, keep the rest minimal.\n"
            "- Use runtime helpers only and keep one complete executable code block."
        )

    def _build_bounded_error_feedback(self, execution_result: str) -> Optional[str]:
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
                    "  file_path = file_by_name['target.xlsx']\n"
                    "  wb = get_workbook(file_path)\n"
                    "  sheet_name = wb.sheetnames[0]\n"
                    "  raw = inspector_multi(file_path, \"A1:Z200\", sheet_name)\n"
                    "- Do not cache DataFrames in a dict with mixed key formats."
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
                "- Use runtime-injected helpers directly: list_all_workbooks, inspector_multi, create_output_sheet, write_dataframe_to_sheet, save_workbook_to."
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
                "  required = [\"name1.xlsx\", \"name2.xlsx\"]\n"
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

    def run(self, understanding_output: str, user_question: str,
            max_turns: int = 20) -> Dict[str, Any]:
        logger.info(f"Starting multi-turn analysis for: '{user_question}'")
        self._consecutive_forbidden = 0
        self._consecutive_format_errors = 0
        self._last_error_signature = None
        self._same_error_streak = 0
        output_contract = self._extract_output_contract(understanding_output)

        self.conversation_history = [self._get_system_prompt()]
        initial_prompt = self._create_initial_user_prompt(
            understanding_output,
            user_question
        )
        self.conversation_history.append(initial_prompt)

        execution_steps = []

        for turn in range(max_turns):
            logger.info(f"Execution turn {turn + 1}")
            self._log_to_file(f"\n---\n\n### Execution Turn {turn + 1}\n")

            try:
                max_tokens = self._bounded_exec_max_tokens if self.use_bounded_execution else None
                response_message = self.llm_client.get_response(
                    self.conversation_history,
                    max_tokens=max_tokens,
                )
                self.conversation_history.append(response_message)

                thought, code_action = self.parser.parse(response_message.content)

                if thought:
                    self._log_to_file(
                        f"\n**Thought (Turn {turn + 1}):**\n{thought}\n"
                    )

                if code_action is None:
                    # Bounded/offline: require executable code; ignore thought-only / final-answer-only output
                    if self.use_bounded_execution:
                        self._consecutive_format_errors += 1
                        strict_repair = ""
                        if self._consecutive_format_errors >= self._max_format_errors:
                            strict_repair = (
                                "\nTRUNCATION/FORMAT RECOVERY (MANDATORY):\n"
                                "- Return ONLY one complete code block.\n"
                                "- Keep code under 120 lines and avoid long comments.\n"
                                "- Ensure closing triple backticks are present.\n"
                                "- Use list_all_workbooks()+inspector_multi(); do not use pandas file readers.\n"
                            )
                        format_msg = (
                            "FORMAT_ERROR_OFFLINE: executable code is required.\n"
                            "Reply with exactly one ```python ... ``` block.\n"
                            "Include complete task logic: read -> compute -> write Output -> save_workbook_to(output_path)."
                            f"{strict_repair}"
                        )
                        logger.warning("Bounded: no code block, executable code required")
                        self._log_to_file(f"\n**Format error (Turn {turn + 1}):** no code block.\n")
                        self.conversation_history.append({"role": "user", "content": format_msg})
                        continue
                    # Non-bounded: allow Final Answer as termination
                    final_answer = self.parser.extract_final_answer(thought)
                    if final_answer is not None:
                        logger.info(f"Final answer found: {final_answer}")
                        self._log_to_file(
                            f"\n**Final Answer (Turn {turn + 1}):**\n{final_answer}\n"
                        )
                        return {
                            "success": True,
                            "answer": final_answer,
                            "total_turns": turn + 1,
                            "conversation_history": self.history_formatter.format_history(
                                self.conversation_history
                            ),
                            "execution_summary": self.summary_builder.build(
                                execution_steps,
                                final_answer
                            )
                        }
                    reminder = (
                        "CRITICAL FORMAT VIOLATION: You must respond in EXACTLY one of these formats:\n\n"
                        "FORMAT A - Thinking + Code:\n"
                        "**Thought:** [Your reasoning here]\n\n"
                        "```python\n# Your code here\n```\n\n"
                        "FORMAT B - Thinking + Final Answer:\n"
                        "**Thought:** [Your reasoning here]\n\n"
                        "Final Answer: Your answer here\n\n"
                        "NO other text is allowed. Start with **Thought:** ALWAYS."
                    )
                    self.conversation_history.append({"role": "user", "content": reminder})
                    continue
                self._consecutive_format_errors = 0

                # Bounded: static forbidden check before execution
                if self.use_bounded_execution:
                    forbidden_err = self.executor.check_forbidden_bounded(code_action)
                    if forbidden_err is not None:
                        self._consecutive_forbidden += 1
                        repair_hint = ""
                        if "to_excel" in forbidden_err or "DataFrame.to_excel" in forbidden_err:
                            repair_hint = (
                                "Replacement pattern:\n"
                                "create_output_sheet(\"Output\")\n"
                                "data_2d = [df.columns.tolist()] + df.values.tolist()\n"
                                "write_dataframe_to_sheet(data_2d, \"Output\", \"A1\")\n"
                                "saved_file = save_workbook_to(output_path)\n"
                                "print(\"SAVED_FILE:\", saved_file)\n"
                            )
                        elif "read_csv" in forbidden_err or "read_table" in forbidden_err or "read_excel" in forbidden_err:
                            repair_hint = (
                                "Do not load files via pandas readers.\n"
                                "Use preloaded workbooks instead:\n"
                                "all_files = list_all_workbooks()\n"
                                "file_by_name = {p.split('/')[-1]: p for p in all_files}\n"
                                "file_path = file_by_name['target.csv']\n"
                                "wb = get_workbook(file_path)\n"
                                "sheet_name = wb.sheetnames[0]\n"
                                "raw = inspector_multi(file_path, \"A1:Z200\", sheet_name)\n"
                                "df = pd.DataFrame(raw[1:], columns=raw[0])\n"
                            )
                        elif "open()" in forbidden_err or "File I/O" in forbidden_err:
                            repair_hint = (
                                "Do not write files with open(). Use write_dataframe_to_sheet(...)\n"
                                "and save_workbook_to(output_path) instead.\n"
                            )
                        if "openpyxl" in forbidden_err:
                            repair_hint = (
                                "Do not import openpyxl or pandas Excel readers/writers.\n"
                                "Only allowed import is: import pandas as pd\n"
                            )
                        if "/Users/" in forbidden_err:
                            repair_hint = (
                                "Do not hard-code input paths.\n"
                                "Always use: all_files = list_all_workbooks(); file_path = all_files[i]\n"
                            )
                        hard_reset = ""
                        if self._consecutive_forbidden >= self._max_forbidden_before_hard_reset:
                            hard_reset = (
                                "\nHARD RESET (GENERIC, NOT TASK-SPECIFIC):\n"
                                "- Rebuild from scratch using only allowed helpers.\n"
                                "- Load files from runtime only: all_files = list_all_workbooks().\n"
                                "- For each file: wb = get_workbook(file_path); sheet_name = wb.sheetnames[0]; "
                                "raw = inspector_multi(file_path, \"A1:Z200\", sheet_name).\n"
                                "- Build DataFrame with explicit header handling: pd.DataFrame(raw[1:], columns=raw[0]).\n"
                                "- Then run task-specific computation, write Output via write_dataframe_to_sheet, and save with save_workbook_to(output_path).\n"
                                "- Do not use placeholder outputs; write real result rows."
                            )
                        logger.warning(f"Forbidden pattern in code (bounded): {forbidden_err}")
                        self._log_to_file(
                            f"\n**Forbidden (Turn {turn + 1}):**\n{forbidden_err}\n"
                        )
                        self.conversation_history.append({
                            "role": "user",
                            "content": (
                                f"FORBIDDEN: {forbidden_err}\n"
                                "MINIMAL PATCH REQUIRED: modify only forbidden lines.\n"
                                "Allowed I/O helpers only: list_all_workbooks(), get_workbook(), inspector_multi(), "
                                "create_output_sheet(), write_dataframe_to_sheet(), save_workbook_to(output_path).\n"
                                f"{repair_hint}"
                                f"{hard_reset}"
                                "Output a single ```python ... ``` block with the corrected full code."
                            )
                        })
                        self._last_error_signature = None
                        self._same_error_streak = 0
                        continue

                    unknown_file_ref_err = self._detect_unknown_filename_lookup(code_action)
                    if unknown_file_ref_err is not None:
                        logger.warning(f"Unknown input filename reference (bounded): {unknown_file_ref_err}")
                        self._log_to_file(
                            f"\n**Grounding violation (Turn {turn + 1}):**\n{unknown_file_ref_err}\n"
                        )
                        self.conversation_history.append({
                            "role": "user",
                            "content": (
                                f"{unknown_file_ref_err}\n"
                                "MINIMAL PATCH REQUIRED: replace only unknown input filenames with names from available list.\n"
                                "Output a single ```python ... ``` block with corrected full code."
                            )
                        })
                        continue
                    self._consecutive_forbidden = 0

                logger.info(f"Executing Python code:\n{code_action}")
                self._log_to_file(
                    f"\n**Executing Python code (Turn {turn + 1}):**\n```python\n{code_action}\n```\n"
                )

                try:
                    execution_result = self.executor.execute(code_action)
                    observation = f"Code execution result:\n{execution_result}"
                    logger.info(f"Execution result:\n{execution_result}")

                    self._log_to_file(
                        f"\n**Execution result (Turn {turn + 1}):**\n```\n{execution_result}\n```\n"
                    )

                    is_execution_error = (
                        "Execution error:" in execution_result or
                        "Traceback:" in execution_result
                    )

                    execution_steps.append({
                        "turn": turn + 1,
                        "code": code_action,
                        "result": execution_result,
                        "success": not is_execution_error
                    })

                    if is_execution_error and self.use_bounded_execution:
                        error_signature = self._update_error_streak(execution_result)
                        targeted_feedback = self._build_bounded_error_feedback(execution_result)
                        if targeted_feedback is None:
                            targeted_feedback = (
                                "MINIMAL FIX REQUIRED: Fix only the smallest necessary part "
                                "(variable/column/type/range/signature). Do not add new helpers, new paths, or refactor unrelated code."
                            )
                        feedback_to_model = targeted_feedback + "\n\n" + execution_result
                        if self._same_error_streak >= self._max_same_error_streak:
                            loop_breaker = self._build_loop_breaker_feedback(error_signature)
                            feedback_to_model = (
                                targeted_feedback
                                + "\n\n"
                                + loop_breaker
                                + "\n\n"
                                + execution_result
                            )
                        self.conversation_history.append({"role": "user", "content": feedback_to_model})
                        continue

                    self._last_error_signature = None
                    self._same_error_streak = 0

                    # Auto-stop when we see a successful save in stdout (avoids Turn2+ repeat path)
                    saved_path = self._extract_saved_path_from_result(execution_result)
                    if saved_path is not None:
                        if self.use_bounded_execution and not self._has_meaningful_output_rows(execution_result):
                            self.conversation_history.append({
                                "role": "user",
                                "content": (
                                    "OUTPUT_INCOMPLETE_OFFLINE: saved file detected, but Output sheet appears to contain only header/placeholder rows.\n"
                                    "You MUST write a real result table (header + data rows) before saving.\n"
                                    "Do not use placeholder `[['Metric','Value']]`.\n"
                                    "Re-run full logic using list_all_workbooks() + inspector_multi(), then write complete table to Output and save_workbook_to(output_path)."
                                )
                            })
                            continue
                        output_intent_feedback = self._build_output_intent_feedback(
                            execution_result, output_contract
                        )
                        if output_intent_feedback is not None:
                            self.conversation_history.append({
                                "role": "user",
                                "content": output_intent_feedback
                            })
                            continue
                        logger.info(f"Final answer (from execution output): {saved_path}")
                        self._log_to_file(
                            f"\n**Final Answer (Turn {turn + 1}, from save output):**\n{saved_path}\n"
                        )
                        return {
                            "success": True,
                            "answer": saved_path,
                            "total_turns": turn + 1,
                            "conversation_history": self.history_formatter.format_history(
                                self.conversation_history
                            ),
                            "execution_summary": self.summary_builder.build(
                                execution_steps,
                                saved_path
                            )
                        }

                    self.conversation_history.append({"role": "user", "content": observation})

                except Exception as e:
                    error_message = f"Code execution error: {str(e)}"
                    logger.error(f"Execution error: {error_message}")

                    self._log_to_file(
                        f"\n**Execution error (Turn {turn + 1}):**\n```\n{error_message}\n```\n"
                    )

                    feedback_to_model = error_message
                    if self.use_bounded_execution:
                        error_signature = self._update_error_streak(error_message)
                        targeted_feedback = self._build_bounded_error_feedback(error_message)
                        if targeted_feedback is not None:
                            feedback_to_model = targeted_feedback + "\n\n" + error_message
                        else:
                            feedback_to_model = (
                                "MINIMAL FIX REQUIRED: Fix only the smallest necessary part "
                                "(variable/column/type/range). Do not add new code or invented paths.\n\n"
                                + error_message
                            )
                        if self._same_error_streak >= self._max_same_error_streak:
                            loop_breaker = self._build_loop_breaker_feedback(error_signature)
                            feedback_to_model = feedback_to_model + "\n\n" + loop_breaker

                    execution_steps.append({
                        "turn": turn + 1,
                        "code": code_action,
                        "result": error_message,
                        "success": False
                    })

                    self.conversation_history.append({"role": "user", "content": feedback_to_model})

            except Exception as e:
                logger.error(f"LLM Error: {str(e)}")
                return {
                    "success": False,
                    "answer": f"LLM communication error: {str(e)}",
                    "total_turns": turn + 1,
                    "conversation_history": self.history_formatter.format_history(
                        self.conversation_history
                    ),
                    "execution_summary": self.summary_builder.build(
                        execution_steps,
                        None
                    )
                }

        logger.warning("Reached maximum turns without finding final answer")
        return {
            "success": False,
            "answer": "Unable to find a complete answer within the maximum number of turns.",
            "total_turns": max_turns,
            "conversation_history": self.history_formatter.format_history(
                self.conversation_history
            ),
            "execution_summary": self.summary_builder.build(
                execution_steps,
                None
            )
        }
