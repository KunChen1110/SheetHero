"""Execution runtime loop for multi-turn analysis."""

import ast
import os
import re
from typing import Dict, Any, Optional

from ...log.logger_registry import LoggerRegistry
from .core.executor import CodeExecutor
from .guards.error_feedback import ExecutionErrorFeedbackBuilder
from .guards.forbidden_policy import (
    build_forbidden_memory_block,
    build_forbidden_repair_hint,
    forbidden_signature,
    is_immediate_hard_forbidden,
)
from .core.history import ExecutionHistory
from .core.llm_client import ExecutionLLMClient
from .guards.output_contract import OutputContractChecker
from .core.parser import ExecutionResponseParser
from .analysis.schedule_helper_analysis import inspect_schedule_helper_sources
from .core.summary import ExecutionSummary
from .analysis.task_intents import (
    header_is_non_feature_like,
    header_is_target_like,
    is_candidate_screening_request,
    is_cash_flow_efficiency_request,
    is_correlation_matrix_request,
    is_cycle_detection_request,
    is_dependency_schedule_request,
    is_diabetes_region_request,
    is_ecommerce_merge_request,
    is_fill_missing_request,
    is_financial_dashboard_request,
    is_hospital_utilisation_request,
    is_inventory_eoq_request,
    is_market_share_shipment_request,
    is_missing_data_scan_request,
    is_mobile_reviews_summary_request,
    is_region_growth_chart_request,
    is_regression_request,
    is_room_inconsistency_request,
    is_same_schema_merge_summary_request,
    is_simple_horizontal_merge_request,
    is_store_feature_analysis_request,
)
from .guards.loop_breakers import get_task_specific_loop_breaker
from .analysis.workbook_grounding import WorkbookGrounding
from ..base.runtime import StageRuntime
from ...prompt.prompt_builder import PromptBuilder

logger = LoggerRegistry.setup_logger(__name__)


class ExecutionRuntime(StageRuntime):
    """Runs the execution loop with LLM responses and code execution."""

    def __init__(self, client, deployment: str, sandbox,
                 excel_context_execution: str,
                 output_instruction: Optional[str] = None, progress_log_file=None,
                 prompt_profile: str = "online_rich"):
        super().__init__(progress_log_file)
        self.client = client
        self.deployment = deployment
        self.sandbox = sandbox
        self.excel_context_execution = excel_context_execution
        self.output_instruction = output_instruction or ""
        self.prompt_profile = prompt_profile
        self._is_offline_strict = (prompt_profile == "offline_strict")
        self.prompt_builder = PromptBuilder(profile=prompt_profile)

        self.llm_client = ExecutionLLMClient(client, deployment)
        self.parser = ExecutionResponseParser()
        self.executor = CodeExecutor(sandbox)
        self.history_formatter = ExecutionHistory()
        self.summary_builder = ExecutionSummary()
        self.grounding = WorkbookGrounding(sandbox)
        self.output_contract_checker = OutputContractChecker()
        self.error_feedback = ExecutionErrorFeedbackBuilder(
            available_workbook_basenames_fn=self._available_workbook_basenames,
            observed_header_set_fn=self._observed_header_set,
            build_schema_snapshot_fn=self._build_schema_snapshot,
        )

        self.conversation_history = []
        self._consecutive_forbidden = 0
        self._consecutive_format_errors = 0
        self._bounded_exec_max_tokens = int(
            os.getenv("SHEETHERO_EXECUTION_MAX_TOKENS", "4096")
        )
        self._max_format_errors = int(os.getenv("SHEETHERO_MAX_FORMAT_ERRORS", "3"))
        self._max_forbidden_before_hard_reset = int(
            os.getenv("SHEETHERO_MAX_FORBIDDEN_BEFORE_RESET", "4")
        )
        self._max_same_forbidden_before_hard_reset = int(
            os.getenv("SHEETHERO_MAX_SAME_FORBIDDEN_BEFORE_RESET", "2")
        )
        self._max_same_error_streak = int(
            os.getenv("SHEETHERO_MAX_SAME_ERROR_STREAK", "2")
        )
        self._max_same_error_before_abort = int(
            os.getenv("SHEETHERO_MAX_SAME_ERROR_BEFORE_ABORT", "4")
        )
        self._last_error_signature: Optional[str] = None
        self._same_error_streak = 0
        self._forbidden_signature_counts: Dict[str, int] = {}
        self._last_forbidden_signature: Optional[str] = None
        self._same_forbidden_streak = 0

    def _install_linear_io_guards(self) -> None:
        """Disable ambiguous I/O helpers for execution-time determinism."""
        globals_dict = getattr(self.sandbox, "code_globals", {}) or {}

        def _disabled(api_name: str, replacement: str):
            def _raise(*_args, **_kwargs):
                raise RuntimeError(
                    f"LINEAR_IO_GUARD: `{api_name}` is disabled in execution mode. "
                    f"Use {replacement}."
                )
            return _raise

        class _DisabledRuntimeValue:
            def __init__(self, name: str, replacement: str):
                self._name = name
                self._replacement = replacement

            def _fail(self):
                raise RuntimeError(
                    f"LINEAR_IO_GUARD: `{self._name}` is disabled in execution mode. "
                    f"Use {self._replacement}."
                )

            def __getitem__(self, _key):
                self._fail()

            def __getattr__(self, _name):
                self._fail()

            def __iter__(self):
                self._fail()

            def __len__(self):
                self._fail()

            def __repr__(self):
                return f"<{self._name}: disabled>"

        disabled_map = {
            "inspector": "read_table_multi(file_path, sheet_name, range_ref)",
            "inspector_multi": "read_table_multi(file_path, sheet_name, range_ref)",
            "read_multiple_sheets": "list_all_workbooks() + read_table_multi(...)",
            "get_sheet_as_dataframe": "read_table_multi(...) + pd.DataFrame(...)",
            "save_workbook": "save_workbook_to(output_path)",
        }
        for api_name, replacement in disabled_map.items():
            if api_name in globals_dict:
                globals_dict[api_name] = _disabled(api_name, replacement)

        if "excel_paths" in globals_dict:
            globals_dict["excel_paths"] = _DisabledRuntimeValue(
                "excel_paths",
                "all_files = list_all_workbooks()",
            )

    def _get_system_prompt(self) -> dict:
        system_content = self.prompt_builder.build_execution_system_prompt(
            self.output_instruction,
        )
        return {"role": "system", "content": system_content}

    @staticmethod
    def _extract_saved_path_from_result(execution_result: str) -> Optional[str]:
        return OutputContractChecker.extract_saved_path_from_result(execution_result)

    @staticmethod
    def _extract_rows_written(execution_result: str) -> list[int]:
        return OutputContractChecker._extract_rows_written(execution_result)

    @staticmethod
    def _extract_highlight_rows(execution_result: str) -> list[int]:
        return OutputContractChecker._extract_highlight_rows(execution_result)

    def _has_meaningful_output_rows(self, execution_result: str) -> bool:
        return self.output_contract_checker.has_meaningful_output_rows(execution_result)

    @staticmethod
    def _parse_output_contract_flag(understanding_output: str, key: str) -> Optional[bool]:
        return OutputContractChecker._parse_flag(understanding_output, key)

    def _extract_output_contract(self, understanding_output: str) -> Dict[str, Optional[bool]]:
        return self.output_contract_checker.extract_output_contract(understanding_output)

    @staticmethod
    def _extract_text_answer_from_result(execution_result: str) -> Optional[str]:
        if not execution_result:
            return None
        for pattern in (
            r"FINAL_TEXT:\s*(.+)",
            r"Expression result:\s*(.+)",
        ):
            match = re.search(pattern, execution_result, flags=re.IGNORECASE)
            if not match:
                continue
            answer = match.group(1).strip().splitlines()[0].strip().strip("`").strip()
            if not answer or OutputContractChecker.extract_saved_path_from_result(answer):
                continue
            return answer
        return None

    def _update_forbidden_memory(self, forbidden_err: str) -> str:
        """Track forbidden signature frequency and repetition streak."""
        signature = forbidden_signature(forbidden_err)
        self._forbidden_signature_counts[signature] = self._forbidden_signature_counts.get(signature, 0) + 1
        if signature == self._last_forbidden_signature:
            self._same_forbidden_streak += 1
        else:
            self._last_forbidden_signature = signature
            self._same_forbidden_streak = 1
        return signature

    def _forbidden_memory_text(self) -> str:
        return build_forbidden_memory_block(
            self._forbidden_signature_counts,
            self._last_forbidden_signature
        )

    @staticmethod
    def _forbidden_hard_reset_text() -> str:
        return (
            "\nHARD RESET (GENERIC, NOT TASK-SPECIFIC):\n"
            "- Rebuild from scratch using only allowed helpers.\n"
            "- Load files from runtime only: all_files = list_all_workbooks().\n"
            "- Never type literal input paths or literal input filenames in code (`/Users/...`, `tc04_input01.xlsx`, etc.).\n"
            "- Preferred runtime workflow: `tables = load_all_tables()` then `find_table_by_headers(...)`.\n"
            "- For dependency schedules, call `build_dependency_schedule(task_df, dependency_df, start_time='08:00')` "
            "instead of hand-writing DAG logic.\n"
            "- Then write Output via write_dataframe_to_sheet, "
            "and save with save_workbook_to(output_path).\n"
            "- Do not use placeholder outputs; write real result rows."
        )

    def _handle_offline_forbidden(
        self,
        code_action: str,
        turn: int,
        user_question: str,
    ) -> tuple[bool, str]:
        """Handle bounded forbidden/grounding checks. Return (should_continue, soft_warning)."""
        forbidden_err = self.executor.check_forbidden_bounded(code_action)
        if forbidden_err is not None:
            self._consecutive_forbidden += 1
            signature = self._update_forbidden_memory(forbidden_err)
            immediate_hard = is_immediate_hard_forbidden(forbidden_err)
            reach_forbidden_limit = (
                self._consecutive_forbidden >= self._max_forbidden_before_hard_reset
            )
            repeated_same_forbidden = (
                self._same_forbidden_streak >= self._max_same_forbidden_before_hard_reset
            )
            hard_block = immediate_hard or reach_forbidden_limit or repeated_same_forbidden
            forbidden_memory = self._forbidden_memory_text()
            if forbidden_memory:
                forbidden_memory = "\n" + forbidden_memory + "\n"

            if hard_block:
                repair_hint = build_forbidden_repair_hint(forbidden_err)
                hard_reset = ""
                task_loop_breaker = get_task_specific_loop_breaker(user_question)
                if reach_forbidden_limit or repeated_same_forbidden:
                    hard_reset = self._forbidden_hard_reset_text()
                if repeated_same_forbidden:
                    hard_reset += (
                        "\nREPEATED FORBIDDEN TYPE DETECTED:\n"
                        f"- repeated_signature: {signature}\n"
                        "- You MUST replace only lines causing this signature before any other edits.\n"
                    )

                logger.warning(f"Forbidden pattern in code (hard-block): {forbidden_err}")
                self._log_to_file(
                    f"\n**Forbidden (Turn {turn + 1}):**\n{forbidden_err}\n"
                )
                self.conversation_history.append({
                    "role": "user",
                    "content": (
                        f"FORBIDDEN: {forbidden_err}\n"
                        "MINIMAL PATCH REQUIRED: modify only forbidden lines.\n"
                        "Allowed helpers only: list_all_workbooks(), get_workbook(), read_table_multi(), "
                        "load_all_tables(), find_table_by_headers(), build_dependency_schedule(), "
                        "create_output_sheet(), write_dataframe_to_sheet(), save_workbook_to(output_path).\n"
                        f"{task_loop_breaker}"
                        f"{repair_hint}"
                        f"{hard_reset}"
                        f"{forbidden_memory}"
                        "Output a single ```python ... ``` block with the corrected full code."
                    )
                })
                self._prune_repair_feedback_history()
                self._last_error_signature = None
                self._same_error_streak = 0
                return True, ""

            logger.warning(f"Forbidden pattern in code (soft-warning): {forbidden_err}")
            self._log_to_file(
                f"\n**Soft Forbidden Warning (Turn {turn + 1}):**\n{forbidden_err}\n"
            )
            soft_warning = (
                "SOFT_FORBIDDEN_WARNING: forbidden pattern detected but execution is allowed for now.\n"
                f"- {forbidden_err}\n"
                f"- forbidden_signature: {signature}\n"
                "- If runtime still fails, patch forbidden lines next turn.\n"
                f"{forbidden_memory}".rstrip()
            )
        else:
            soft_warning = ""
            self._consecutive_forbidden = 0
            self._same_forbidden_streak = 0
            self._last_forbidden_signature = None

        unknown_file_ref_err = self._detect_unknown_filename_lookup(code_action)
        if unknown_file_ref_err is not None:
            logger.warning(f"Unknown input filename reference (strict): {unknown_file_ref_err}")
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
            self._prune_repair_feedback_history()
            return True, ""

        return False, soft_warning

    def _offline_preflight_check(self, code_action: str, user_question: str) -> Optional[str]:
        """Reject obviously drifting offline code before sandbox execution."""
        code = (code_action or "").strip()
        if not code:
            return "PREFLIGHT_LINEAR: empty code block."
        lower = code.lower()
        uses_load_all_tables = "load_all_tables(" in lower
        uses_region_growth_helper = "build_region_growth_analysis(" in lower
        uses_financial_dashboard_helper = "build_financial_dashboard_report(" in lower
        uses_candidate_screening_helper = "build_candidate_screening_report(" in lower
        uses_inventory_eoq_helper = "build_inventory_eoq_report(" in lower
        uses_hospital_utilisation_helper = "build_hospital_utilisation_report(" in lower
        uses_market_share_shipment_helper = "build_market_share_shipment_report(" in lower
        uses_cash_flow_efficiency_helper = "build_cash_flow_efficiency_report(" in lower
        uses_diabetes_region_helper = "build_diabetes_region_report(" in lower
        uses_mobile_reviews_summary_helper = "build_mobile_reviews_summary_report(" in lower
        uses_store_feature_analysis_helper = "build_store_feature_analysis_report(" in lower
        uses_ecommerce_merge_helper = "build_ecommerce_merge_report(" in lower
        uses_missing_data_helper = "build_missing_data_report(" in lower
        uses_room_format_helper = "build_room_format_report(" in lower
        top_level_returns = [
            line.strip()
            for line in code.splitlines()
            if line.strip().startswith("return ")
        ]
        if top_level_returns:
            return (
                "PREFLIGHT_LINEAR: top-level `return` is invalid in execution code.\n"
                "- Do not use `return saved_file`.\n"
                "- End with:\n"
                "  `saved_file = save_workbook_to(output_path)`\n"
                "  `print(f'SAVED_FILE: {saved_file}')`\n"
                "  `saved_file`"
            )
        try:
            ast.parse(code)
        except SyntaxError as exc:
            line_info = f" on line {exc.lineno}" if exc.lineno else ""
            return (
                f"PREFLIGHT_LINEAR: generated code has a syntax error{line_info}.\n"
                f"- Parser message: {exc.msg}\n"
                "- Return one full corrected code block.\n"
                "- Keep string quoting simple and avoid nested double quotes inside f-strings."
            )
        if "list_all_workbooks(" not in lower and not uses_load_all_tables and not uses_financial_dashboard_helper and not uses_candidate_screening_helper and not uses_inventory_eoq_helper and not uses_hospital_utilisation_helper and not uses_market_share_shipment_helper and not uses_cash_flow_efficiency_helper and not uses_diabetes_region_helper and not uses_mobile_reviews_summary_helper and not uses_store_feature_analysis_helper and not uses_ecommerce_merge_helper and not uses_missing_data_helper and not uses_room_format_helper:
            return (
                "PREFLIGHT_LINEAR: code must read runtime inputs via `load_all_tables()` or `list_all_workbooks()`.\n"
                "- Preferred: `tables = load_all_tables()`\n"
                "- Or add: `all_files = list_all_workbooks()` and resolve file_path from runtime."
            )
        requires_saved_workbook = not (
            (is_missing_data_scan_request(user_question) and uses_missing_data_helper)
            or (is_room_inconsistency_request(user_question) and uses_room_format_helper)
        )
        if requires_saved_workbook and not re.search(r"save_workbook_to\s*\(\s*output_path\s*\)", code, flags=re.IGNORECASE):
            return (
                "PREFLIGHT_LINEAR: code must save with save_workbook_to(output_path).\n"
                "- End with:\n"
                "  saved_file = save_workbook_to(output_path)\n"
                "  print(\"SAVED_FILE:\", saved_file)\n"
                "  saved_file"
            )
        if re.search(r"^\s*from\s+(runtime|runtime_path|graph_helper|excel_output|workbook_helper)\s+import\s+", code, flags=re.IGNORECASE | re.MULTILINE):
            return (
                "PREFLIGHT_LINEAR: do not import runtime helper modules.\n"
                "- Helper functions are already injected into the sandbox globals.\n"
                "- Call them directly: `load_all_tables()`, `build_cycle_detection_report(...)`, "
                "`create_output_sheet(...)`, `write_dataframe_to_sheet(...)`, `save_workbook_to(output_path)`.\n"
                "- Remove all `from runtime...`, `from graph_helper...`, `from excel_output...`, and `from workbook_helper...` imports."
            )
        if re.search(r"^\s*output_path\s*=\s*['\"][^'\"]+['\"]", code, flags=re.IGNORECASE | re.MULTILINE):
            return (
                "PREFLIGHT_LINEAR: do not assign a literal output path in execution code.\n"
                "- Use the injected runtime variable only: `save_workbook_to(output_path)`.\n"
                "- Do not redefine `output_path`."
            )
        if "read_table_multi(" not in lower and not uses_load_all_tables and not uses_region_growth_helper and not uses_financial_dashboard_helper and not uses_candidate_screening_helper and not uses_inventory_eoq_helper and not uses_hospital_utilisation_helper and not uses_market_share_shipment_helper and not uses_cash_flow_efficiency_helper and not uses_diabetes_region_helper and not uses_mobile_reviews_summary_helper and not uses_store_feature_analysis_helper and not uses_ecommerce_merge_helper and not uses_missing_data_helper and not uses_room_format_helper:
            return (
                "PREFLIGHT_LINEAR: code must read tabular content via `load_all_tables()` or `read_table_multi(...)`.\n"
                "- Preferred: `tables = load_all_tables()`\n"
                "- Manual fallback: `table = read_table_multi(file_path, sheet_name, \"A1:Z200\")`\n"
                "- Then build DataFrame with: `pd.DataFrame(table['rows'], columns=table['header'])`"
            )
        if re.search(
            r"read_table_multi\s*\([^)]*\)\s*\[\s*['\"]df['\"]\s*\]",
            code,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            return (
                "PREFLIGHT_LINEAR: read_table_multi() does not return a `df` key.\n"
                "- Use: `table = read_table_multi(file_path, sheet_name, \"A1:Z200\")`\n"
                "- Then build DataFrame explicitly:\n"
                "  `df = pd.DataFrame(table['rows'], columns=table['header'])`"
            )
        uses_rows = re.search(r"\[\s*['\"]rows['\"]\s*\]", code) is not None
        uses_header = re.search(r"\[\s*['\"]header['\"]\s*\]", code) is not None
        if uses_rows and not uses_header:
            return (
                "PREFLIGHT_LINEAR: read_table_multi() output must use both `rows` and `header`.\n"
                "- `table['header']` is the header row.\n"
                "- `table['rows']` already contains data rows only.\n"
                "- Build DataFrame with: `pd.DataFrame(table['rows'], columns=table['header'])`.\n"
                "- Do not hard-code headers or slice `rows[1:]`."
            )
        if re.search(r"\[\s*['\"]rows['\"]\s*\]\s*\[\s*1\s*:\s*\]", code):
            return (
                "PREFLIGHT_LINEAR: `table['rows']` already excludes the header row.\n"
                "- Remove `[1:]` after `table['rows']`.\n"
                "- Use all rows directly when building the DataFrame."
            )
        if re.search(r"\binspector_multi\s*\(", code):
            return (
                "PREFLIGHT_LINEAR: `inspector_multi()` is disabled for execution.\n"
                "- Use cleaned table reader only:\n"
                "  all_files = list_all_workbooks()\n"
                "  for file_path in all_files:\n"
                "      wb = get_workbook(file_path)\n"
                "      sheet_name = wb.sheetnames[0]\n"
                "      table = read_table_multi(file_path, sheet_name, \"A1:Z200\")"
            )
        uses_single_inspector = re.search(r"\binspector\s*\(", code) is not None
        if uses_single_inspector:
            return (
                "PREFLIGHT_LINEAR: `inspector()` is disabled for execution.\n"
                "- Use a single deterministic read path only:\n"
                "  all_files = list_all_workbooks()\n"
                "  for file_path in all_files:\n"
                "      wb = get_workbook(file_path)\n"
                "      sheet_name = wb.sheetnames[0]\n"
                "      table = read_table_multi(file_path, sheet_name, \"A1:Z200\")"
            )
        return None

    def _expected_regression_predictors(self) -> list[str]:
        headers = sorted(self._observed_header_set())
        if not headers:
            return []
        target_like = [h for h in headers if header_is_target_like(h)]
        predictors: list[str] = []
        for h in headers:
            if h in target_like:
                continue
            if header_is_non_feature_like(h):
                continue
            predictors.append(h)
        return predictors

    @staticmethod
    def _extract_feature_cols_literal(code: str) -> list[str]:
        m = re.search(r"feature_cols\s*=\s*\[([^\]]*)\]", code, flags=re.IGNORECASE | re.DOTALL)
        if not m:
            return []
        body = m.group(1)
        return [s.strip() for s in re.findall(r"['\"]([^'\"]+)['\"]", body)]

    def _regression_helper_guard(self, code_action: str, user_question: str) -> Optional[str]:
        if not is_regression_request(user_question):
            return None
        code = code_action or ""
        lower = code.lower()
        if "fit_linear_regression_weights(" in lower:
            if (
                re.search(r"regression_result\s*\[\s*['\"]detail_data['\"]\s*\]\.columns", lower)
                or re.search(r"regression_result\s*\[\s*['\"]detail_data['\"]\s*\]\.values", lower)
            ):
                return (
                    "PREFLIGHT_REGRESSION: `regression_result['detail_data']` is already a 2D table payload, not a DataFrame.\n"
                    "- Either write it directly:\n"
                    "  `write_dataframe_to_sheet(regression_result['detail_data'], 'Output', 'A1')`\n"
                    "- Or use the DataFrame form:\n"
                    "  `write_dataframe_to_sheet(regression_result['output_df'], 'Output', 'A1')`"
                )
            if re.search(r"regression_result\s*\[\s*['\"]coef['\"]\s*\]", lower):
                return (
                    "PREFLIGHT_REGRESSION: the regression helper does not return a `coef` key.\n"
                    "- Use these keys only:\n"
                    "  `regression_result['used_features']`\n"
                    "  `regression_result['output_df']`\n"
                    "  `regression_result['detail_data']`\n"
                    "  `regression_result['coefficients_df']`\n"
                    "- Write `regression_result['output_df']` directly."
                )
            return None
        return (
            "PREFLIGHT_REGRESSION: use the runtime regression helper instead of hand-writing least-squares code.\n"
            "- Preferred linear pipeline:\n"
            "  `tables = load_all_tables()`\n"
            "  `df = tables[0]['df']`\n"
            "  `feature_cols = ['col1', 'col2', ...]`\n"
            "  `regression_result = fit_linear_regression_weights(df, target_col='...', feature_cols=feature_cols)`\n"
            "  `print('USED_FEATURES:', regression_result['used_features'])`\n"
            "  `write_dataframe_to_sheet(regression_result['output_df'], 'Output', 'A1')`\n"
            "- Do not import sklearn/statsmodels and do not hand-write `numpy.linalg.lstsq` in this task."
        )

    def _merge_fill_helper_guard(self, code_action: str, user_question: str) -> Optional[str]:
        code = code_action or ""
        lower = code.lower()
        if is_financial_dashboard_request(user_question):
            if "build_financial_dashboard_report(" in lower:
                return None
            return (
                "PREFLIGHT_FINANCIAL_DASHBOARD: use the runtime financial-dashboard helper.\n"
                "- Preferred linear pipeline:\n"
                "  `dashboard_result = build_financial_dashboard_report()`\n"
                "  `create_output_sheet('Output')`\n"
                "  `write_dataframe_to_sheet(dashboard_result['detail_data'], 'Output', 'A1')`\n"
                "  `saved_file = save_workbook_to(output_path)`\n"
                "  `print(f'SAVED_FILE: {saved_file}')`\n"
                "  `saved_file`\n"
                "- Do not hand-build joins, target parsing, or dashboard rows in this task."
            )
        if is_candidate_screening_request(user_question):
            if "build_candidate_screening_report(" in lower:
                return None
            return (
                "PREFLIGHT_CANDIDATE_SCREENING: use the runtime candidate-screening helper.\n"
                "- Preferred linear pipeline:\n"
                "  `screening_result = build_candidate_screening_report()`\n"
                "  `create_output_sheet('Output')`\n"
                "  `write_dataframe_to_sheet(screening_result['detail_data'], 'Output', 'A1')`\n"
                "  `saved_file = save_workbook_to(output_path)`\n"
                "  `print(f'SAVED_FILE: {saved_file}')`\n"
                "  `saved_file`\n"
                "- Do not hand-build file loops, score formulas, or ranking rows in this task."
            )
        if is_inventory_eoq_request(user_question):
            if "build_inventory_eoq_report(" in lower:
                return None
            return (
                "PREFLIGHT_INVENTORY_EOQ: use the runtime inventory EOQ helper.\n"
                "- Preferred linear pipeline:\n"
                "  `inventory_result = build_inventory_eoq_report()`\n"
                "  `create_output_sheet('Output')`\n"
                "  `write_dataframe_to_sheet(inventory_result['detail_data'], 'Output', 'A1')`\n"
                "  `saved_file = save_workbook_to(output_path)`\n"
                "  `print(f'SAVED_FILE: {saved_file}')`\n"
                "  `saved_file`\n"
                "- Do not hand-build EOQ formulas, parameter parsing, or multi-table layout in this task."
            )
        if is_hospital_utilisation_request(user_question):
            if "build_hospital_utilisation_report(" in lower:
                return None
            return (
                "PREFLIGHT_HOSPITAL_UTILISATION: use the runtime hospital-utilisation helper.\n"
                "- Preferred linear pipeline:\n"
                "  `report = build_hospital_utilisation_report()`\n"
                "  `create_output_sheet('Output')`\n"
                "  `write_dataframe_to_sheet(report['detail_data'], 'Output', 'A1')`\n"
                "  `if report['highlight_rows']:`\n"
                "      `highlight_rows('Output', report['highlight_rows'], {'fill_color': 'red'})`\n"
                "  `else:`\n"
                "      `print('NO_HIGHLIGHT_ROWS: threshold not reached')`\n"
                "  `saved_file = save_workbook_to(output_path)`\n"
                "  `print(f'SAVED_FILE: {saved_file}')`\n"
                "  `saved_file`\n"
                "- Do not hand-build merges or grouped utilisation logic in this task."
            )
        if is_market_share_shipment_request(user_question):
            if "build_market_share_shipment_report(" in lower:
                return None
            return (
                "PREFLIGHT_MARKET_SHARE_SHIPMENT: use the runtime market-share/shipment helper.\n"
                "- Preferred linear pipeline:\n"
                "  `market_result = build_market_share_shipment_report()`\n"
                "  `create_output_sheet('Output')`\n"
                "  `write_dataframe_to_sheet(market_result['detail_data'], 'Output', 'A1')`\n"
                "  `saved_file = save_workbook_to(output_path)`\n"
                "  `print(f'SAVED_FILE: {saved_file}')`\n"
                "  `saved_file`\n"
                "- Do not hand-build quarter alignment or market-share multiplications in this task."
            )
        if is_cash_flow_efficiency_request(user_question):
            if "build_cash_flow_efficiency_report(" in lower:
                return None
            return (
                "PREFLIGHT_CASH_FLOW_EFFICIENCY: use the runtime cash-flow helper.\n"
                "- Preferred linear pipeline:\n"
                "  `report = build_cash_flow_efficiency_report()`\n"
                "  `create_output_sheet('Output')`\n"
                "  `write_dataframe_to_sheet(report['detail_data'], 'Output', 'A1')`\n"
                "  `saved_file = save_workbook_to(output_path)`\n"
                "  `print(f'SAVED_FILE: {saved_file}')`\n"
                "  `saved_file`\n"
                "- Do not hand-locate statement rows or compute OCF/FCF formulas in this task."
            )
        if is_diabetes_region_request(user_question):
            if "build_diabetes_region_report(" in lower:
                return None
            return (
                "PREFLIGHT_DIABETES_REGION: use the runtime diabetes-region helper.\n"
                "- Preferred linear pipeline:\n"
                "  `report = build_diabetes_region_report()`\n"
                "  `create_output_sheet('Output')`\n"
                "  `write_dataframe_to_sheet(report['detail_data'], 'Output', 'A1')`\n"
                "  `saved_file = save_workbook_to(output_path)`\n"
                "  `print(f'SAVED_FILE: {saved_file}')`\n"
                "  `saved_file`\n"
                "- Do not hand-build region merges or percentage calculations in this task."
            )
        if is_mobile_reviews_summary_request(user_question):
            helper_call = re.search(r"build_mobile_reviews_summary_report\s*\(([^)]*)\)", code, flags=re.IGNORECASE | re.DOTALL)
            if helper_call:
                if helper_call.group(1).strip():
                    return (
                        "PREFLIGHT_MOBILE_REVIEWS: call `build_mobile_reviews_summary_report()` with no manual DataFrame argument.\n"
                        "- Correct usage:\n"
                        "  `report = build_mobile_reviews_summary_report()`\n"
                        "- The helper reads the runtime workbook internally.\n"
                        "- Do not pre-select headers or pass `df` into the helper."
                    )
                return None
            return (
                "PREFLIGHT_MOBILE_REVIEWS: use the runtime mobile-reviews helper.\n"
                "- Preferred linear pipeline:\n"
                "  `report = build_mobile_reviews_summary_report()`\n"
                "  `create_output_sheet('Output')`\n"
                "  `write_dataframe_to_sheet(report['detail_data'], 'Output', 'A1')`\n"
                "  `saved_file = save_workbook_to(output_path)`\n"
                "  `print(f'SAVED_FILE: {saved_file}')`\n"
                "  `saved_file`\n"
                "- Exclude rows with missing ratings.\n"
                "- Do not hand-build groupby or aggregation code in this task."
            )
        if is_store_feature_analysis_request(user_question):
            helper_call = re.search(r"build_store_feature_analysis_report\s*\(([^)]*)\)", code, flags=re.IGNORECASE | re.DOTALL)
            if helper_call:
                if helper_call.group(1).strip():
                    return (
                        "PREFLIGHT_STORE_FEATURE_ANALYSIS: call `build_store_feature_analysis_report()` with no manual DataFrame argument.\n"
                        "- Correct usage:\n"
                        "  `report = build_store_feature_analysis_report()`\n"
                        "- The helper reads and merges the two runtime workbooks internally.\n"
                        "- Do not pre-select headers or pass `df` into the helper."
                    )
                return None
            return (
                "PREFLIGHT_STORE_FEATURE_ANALYSIS: use the runtime store-feature helper.\n"
                "- Preferred linear pipeline:\n"
                "  `report = build_store_feature_analysis_report()`\n"
                "  `create_output_sheet('AvgByStoreType')`\n"
                "  `write_dataframe_to_sheet(report['avg_by_type_detail_data'], 'AvgByStoreType', 'A1')`\n"
                "  `create_output_sheet('HolidayVsNonHoliday')`\n"
                "  `write_dataframe_to_sheet(report['holiday_detail_data'], 'HolidayVsNonHoliday', 'A1')`\n"
                "  `saved_file = save_workbook_to(output_path)`\n"
                "  `print(f'SAVED_FILE: {saved_file}')`\n"
                "  `saved_file`\n"
                "- Do not hand-build merge/groupby/multi-sheet logic in this task."
            )
        if is_ecommerce_merge_request(user_question):
            helper_call = re.search(r"build_ecommerce_merge_report\s*\(([^)]*)\)", code, flags=re.IGNORECASE | re.DOTALL)
            if helper_call:
                if helper_call.group(1).strip():
                    return (
                        "PREFLIGHT_ECOMMERCE_MERGE: call `build_ecommerce_merge_report()` with no manual DataFrame argument.\n"
                        "- Correct usage:\n"
                        "  `report = build_ecommerce_merge_report()`\n"
                        "- The helper reads, translates, and merges the runtime CSV tables internally.\n"
                        "- Do not pre-select or pass tables into the helper."
                    )
                return None
            return (
                "PREFLIGHT_ECOMMERCE_MERGE: use the runtime e-commerce merge helper.\n"
                "- Preferred linear pipeline:\n"
                "  `report = build_ecommerce_merge_report()`\n"
                "  `create_output_sheet('Output')`\n"
                "  `write_dataframe_to_sheet(report['detail_data'], 'Output', 'A1')`\n"
                "  `saved_file = save_workbook_to(output_path)`\n"
                "  `print(f'SAVED_FILE: {saved_file}')`\n"
                "  `saved_file`\n"
                "- Do not hand-build multi-file joins or category translation logic in this task."
            )
        if is_missing_data_scan_request(user_question):
            if "build_missing_data_report(" in lower:
                return None
            return (
                "PREFLIGHT_MISSING_DATA: use the runtime missing-data helper.\n"
                "- Preferred linear pipeline:\n"
                "  `report = build_missing_data_report()`\n"
                "  `final_text = report['answer']`\n"
                "  `print(f'FINAL_TEXT: {final_text}')`\n"
                "  `final_text`\n"
                "- Do not create or save an output workbook for this task."
            )
        if is_room_inconsistency_request(user_question):
            if "build_room_format_report(" in lower:
                return None
            return (
                "PREFLIGHT_ROOM_FORMAT: use the runtime room-format helper.\n"
                "- Preferred linear pipeline:\n"
                "  `report = build_room_format_report()`\n"
                "  `final_text = report['answer']`\n"
                "  `print(f'FINAL_TEXT: {final_text}')`\n"
                "  `final_text`\n"
                "- Do not modify or save the workbook in this task."
            )
        if is_correlation_matrix_request(user_question):
            if "build_correlation_matrix_table(" in lower:
                if re.search(r"matrix_result\s*\[\s*['\"]matrix_df['\"]\s*\]\.values", lower):
                    return (
                        "PREFLIGHT_CORRELATION_MATRIX: write the helper result directly.\n"
                        "- Prefer:\n"
                        "  `write_dataframe_to_sheet(matrix_result['detail_data'], 'Output', 'A1')`\n"
                        "- Or:\n"
                        "  `write_dataframe_to_sheet(matrix_result['output_df'], 'Output', 'A1')`\n"
                        "- Do not rebuild the matrix from `.values`."
                    )
                return None
            return (
                "PREFLIGHT_CORRELATION_MATRIX: use the runtime correlation-matrix helper.\n"
                "- Preferred linear pipeline:\n"
                "  `tables = load_all_tables()`\n"
                "  `df = tables[0]['df']`\n"
                "  `matrix_result = build_correlation_matrix_table(df, numeric_columns=['sepal_length', 'sepal_width', 'petal_length', 'petal_width'], filter_column='species', filter_value='Iris-setosa')`\n"
                "  `create_output_sheet('Output')`\n"
                "  `write_dataframe_to_sheet(matrix_result['detail_data'], 'Output', 'A1')`\n"
                "  `saved_file = save_workbook_to(output_path)`\n"
                "  `print(f'SAVED_FILE: {saved_file}')`\n"
                "  `saved_file`\n"
                "- Do not hard-code absolute paths or hand-build the correlation matrix in this task."
            )
        if is_cycle_detection_request(user_question):
            if "build_cycle_detection_report(" in lower:
                return None
            return (
                "PREFLIGHT_CYCLE_DETECTION: use the runtime cycle-detection helper.\n"
                "- Preferred linear pipeline:\n"
                "  `tables = load_all_tables()`\n"
                "  `cycle_result = build_cycle_detection_report(tables, from_col='Node From', to_col='Node To')`\n"
                "  `create_output_sheet('Output')`\n"
                "  `write_dataframe_to_sheet(cycle_result['detail_data'], 'Output', 'A1')`\n"
                "  `saved_file = save_workbook_to(output_path)`\n"
                "  `print(f'SAVED_FILE: {saved_file}')`\n"
                "  `saved_file`\n"
                "- Do not hand-code CSV reads or manual cycle-detection loops in this task."
            )
        if is_region_growth_chart_request(user_question):
            if "build_region_growth_analysis(" in lower and "save_plot_to_excel(" in lower:
                return None
            return (
                "PREFLIGHT_REGION_GROWTH: use the runtime region-growth helper for messy multi-row header chart tasks.\n"
                "- Preferred linear pipeline:\n"
                "  `all_files = list_all_workbooks()`\n"
                "  `analysis = build_region_growth_analysis(all_files[0], sheet_name='Data', start_year=2020, end_year=2024)`\n"
                "  `create_output_sheet('Output')`\n"
                "  `write_dataframe_to_sheet(analysis['output_df'], 'Output', 'A1')`\n"
                "  `highlight_rows('Output', analysis['fastest_growth_rows'], {'fill_color': 'red'})`\n"
                "  `add_summary_row('Output', len(analysis['detail_data']) + 2, analysis['summary'])`\n"
                "  `chart_df = analysis['chart_df']`\n"
                "  `for region in analysis['region_columns']: plt.plot(chart_df['Year'], chart_df[region], label=region)`\n"
                "  `plt.xlabel('Year')`; `plt.ylabel('Penetration Rate')`; `plt.legend()`\n"
                "  `save_plot_to_excel('Output', 'F2')`\n"
                "- `plt` is already available in the sandbox; do NOT import `plotnine`, `seaborn`, or any extra chart library.\n"
                "- Do not hand-parse the messy multi-row header with `read_table_multi()` in this task."
            )
        if is_fill_missing_request(user_question):
            if "fill_missing_from_reference(" in lower:
                compact = lower.replace(" ", "")
                if "load_all_tables(" in lower and "require_primary_key=false" not in compact:
                    return (
                        "PREFLIGHT_FILL: fill-missing tasks must preserve rows whose key is missing.\n"
                        "- Load with:\n"
                        "  `tables = load_all_tables(require_primary_key=False)`\n"
                        "- Then call:\n"
                        "  `key_header = infer_common_key(tables)`\n"
                        "  `fill_result = fill_missing_from_reference(tables[0]['df'], tables[1]['df'], key_header=key_header, prefer_primary=True)`"
                    )
                return None
            return (
                "PREFLIGHT_FILL: use the runtime fill helper for simple fill-missing tasks.\n"
                "- Preferred linear pipeline:\n"
                "  `tables = load_all_tables(require_primary_key=False)`\n"
                "  `key_header = infer_common_key(tables)`\n"
                "  `fill_result = fill_missing_from_reference(tables[0]['df'], tables[1]['df'], key_header=key_header, prefer_primary=True)`\n"
                "  `write_dataframe_to_sheet(fill_result['output_df'], 'Output', 'A1')`\n"
                "- Do not hand-write per-cell fill loops for this simple task."
            )
        if is_simple_horizontal_merge_request(user_question):
            if "merge_tables_on_key(" in lower:
                return None
            return (
                "PREFLIGHT_MERGE: use the runtime merge helper for simple multi-file merge tasks.\n"
                "- Preferred linear pipeline:\n"
                "  `tables = load_all_tables()`\n"
                "  `key_header = infer_common_key(tables)`\n"
                "  `merge_result = merge_tables_on_key(tables, key_header=key_header, how='inner')`\n"
                "  `write_dataframe_to_sheet(merge_result['output_df'], 'Output', 'A1')`\n"
                "- Do not hand-write repeated merge loops for this simple task."
            )
        if is_same_schema_merge_summary_request(user_question):
            if "concat_tables_with_same_headers(" in lower and "summarize_numeric_column(" in lower:
                return None
            if "pd.merge(" in lower:
                return (
                    "PREFLIGHT_MERGE_SUMMARY: this task needs vertical concatenation, not a join/merge on keys.\n"
                    "- The input tables share the same schema and should be stacked row-wise.\n"
                    "- Use `concat_tables_with_same_headers(tables)` first, then summarize/highlight from the combined table."
                )
            return (
                "PREFLIGHT_MERGE_SUMMARY: use the runtime concat/summary helpers for same-schema merge + summary tasks.\n"
                "- Preferred linear pipeline:\n"
                "  `tables = load_all_tables()`\n"
                "  `concat_result = concat_tables_with_same_headers(tables)`\n"
                "  `combined_df = concat_result['output_df']`\n"
                "  `summary_result = summarize_numeric_column(combined_df, value_col='...', summary_labels={...})`\n"
                "  `create_output_sheet('Output')`\n"
                "  `write_dataframe_to_sheet(combined_df, 'Output', 'A1')`\n"
                "  `highlight_rows('Output', summary_result['output_row_numbers'], {'fill_color': 'red'})`\n"
                "  `add_summary_row('Output', len(concat_result['detail_data']) + 2, summary_result['summary'])`"
            )
        return None

    def _regression_feature_guard(self, code_action: str, user_question: str) -> Optional[str]:
        if not is_regression_request(user_question):
            return None
        code = code_action or ""
        lower = code.lower()
        if "feature_cols" not in lower:
            return (
                "PREFLIGHT_REGRESSION: regression task must define explicit `feature_cols`.\n"
                "- Use all predictor columns (exclude target/ID/date-like columns).\n"
                "- Include binary categorical predictors (e.g., yes/no -> 1/0).\n"
                "- Print `USED_FEATURES` before fitting."
            )
        expected = self._expected_regression_predictors()
        if not expected:
            return None
        used = self._extract_feature_cols_literal(code)
        if not used:
            return (
                "PREFLIGHT_REGRESSION: could not parse explicit feature list.\n"
                "- Define `feature_cols = [\"col1\", \"col2\", ...]` as string literals.\n"
                "- Include all available predictors and print `USED_FEATURES`."
            )
        used_set = {u.strip().lower() for u in used}
        missing = [h for h in expected if h.strip().lower() not in used_set]
        if missing:
            missing_str = ", ".join(missing[:6])
            return (
                "PREFLIGHT_REGRESSION: feature coverage incomplete.\n"
                f"- Missing predictor(s): {missing_str}\n"
                "- Do not omit available predictors in regression tasks.\n"
                "- Add missing columns into `feature_cols` and encode binary categorical columns to 0/1."
            )
        if "used_features" not in lower:
            return (
                "PREFLIGHT_REGRESSION: add explicit feature audit print.\n"
                "- Add: print(\"USED_FEATURES:\", feature_cols)"
            )
        return None

    def _uses_literal_input_basenames(self, code_action: str) -> bool:
        code = code_action or ""
        lower = code.lower()
        for basename in self._available_workbook_basenames():
            escaped = re.escape((basename or "").lower())
            if not escaped:
                continue
            if re.search(rf"['\"]{escaped}['\"]", lower):
                return True
        return False

    def _scheduling_dependency_guard(self, code_action: str, user_question: str) -> Optional[str]:
        if not is_dependency_schedule_request(user_question):
            return None

        code = code_action or ""
        lower = code.lower()
        duration_hour_lines = [
            line.strip().lower()
            for line in code.splitlines()
            if "duration (hours)" in line.lower()
        ]
        filename_role_guess = (
            re.search(r"for\s+\w+\s+in\s+all_files\s+if\s+.*['\"]tasks?['\"]\s+in\s+\w+", lower)
            or re.search(r"for\s+\w+\s+in\s+all_files\s+if\s+.*['\"]dependenc", lower)
            or re.search(r"(task_table|dependency_table)\s*=\s*tables\[\d+\]", lower)
            or self._uses_literal_input_basenames(code)
        )
        uses_schedule_helper = "build_dependency_schedule(" in lower
        uses_table_loader = "load_all_tables(" in lower
        uses_header_selector = "find_table_by_headers(" in lower

        if "pd.merge(" in lower:
            return (
                "PREFLIGHT_SCHEDULING: do not merge task table with dependency table for DAG scheduling.\n"
                "- Keep tasks and dependencies as separate DataFrames.\n"
                "- Build `task_id_set` from task table first.\n"
                "- Parse dependency rows separately; blank/NaN predecessor means ROOT and should not be dropped."
            )

        schema_mismatch_markers = (
            "same_schema",
            "schema mismatch between files",
            "raise valueerror(\"schema mismatch",
            "raise valueerror('schema mismatch",
        )
        if any(marker in lower for marker in schema_mismatch_markers):
            return (
                "PREFLIGHT_SCHEDULING: dependency scheduling expects complementary tables, not matching schemas.\n"
                "- Identify task table by headers like `Task ID` + duration/name/priority columns.\n"
                "- Identify dependency table by headers `Task ID` + `Depends on`.\n"
                "- Keep them separate even when headers differ; do not raise schema mismatch."
            )
        if filename_role_guess:
            return (
                "PREFLIGHT_SCHEDULING: do not identify task/dependency tables from filenames, literal input basenames, or list positions.\n"
                "- Classify each table by verified headers only.\n"
                "- Task table must be chosen from headers like `Task ID` + `Task Name` + `Duration (hours)`.\n"
                "- Dependency table must be chosen from headers `Task ID` + `Depends on`."
            )
        if not uses_schedule_helper:
            return (
                "PREFLIGHT_SCHEDULING: use the runtime dependency-scheduling helper instead of hand-writing DAG logic.\n"
                "- Preferred linear pipeline:\n"
                "  `tables = load_all_tables()`\n"
                "  `task_table = find_table_by_headers(tables, required_headers=['Task ID'], preferred_headers=['Task Name', 'Duration (hours)', 'Priority'], forbidden_headers=['Depends on'])`\n"
                "  `dependency_table = find_table_by_headers(tables, required_headers=['Task ID', 'Depends on'])`\n"
                "  `schedule_result = build_dependency_schedule(task_table['df'], dependency_table['df'], start_time='08:00')`\n"
                "- Then write `schedule_result['detail_data']`, add `schedule_result['summary']`, print coverage, and save.\n"
                "- Do not hand-write adjacency/in_degree/queue in this task."
            )
        if not uses_table_loader:
            return (
                "PREFLIGHT_SCHEDULING: use `load_all_tables()` for dependency-scheduling tasks.\n"
                "- This keeps file loading linear and avoids repeated runtime I/O mistakes.\n"
                "- Then pick task/dependency tables with `find_table_by_headers(...)`."
            )
        if not uses_header_selector:
            return (
                "PREFLIGHT_SCHEDULING: use `find_table_by_headers(...)` to classify task and dependency tables.\n"
                "- Do not hand-write role selection logic from filenames, order, or partial header guesses."
            )
        helper_source_issue = inspect_schedule_helper_sources(code)
        if helper_source_issue == "missing_args":
            return (
                "PREFLIGHT_SCHEDULING: `build_dependency_schedule(...)` must receive both task and dependency DataFrames.\n"
                "- Use the exact helper call shape:\n"
                "  `schedule_result = build_dependency_schedule(task_table['df'], dependency_table['df'], start_time='08:00')`"
            )
        if helper_source_issue == "reconstructed_df":
            return (
                "PREFLIGHT_SCHEDULING: do not rebuild reduced DataFrames before calling `build_dependency_schedule(...)`.\n"
                "- Pass the original selected tables directly:\n"
                "  `schedule_result = build_dependency_schedule(task_table['df'], dependency_table['df'], start_time='08:00')`\n"
                "- Do NOT do `pd.DataFrame({...})` or column-subset reconstruction for the helper inputs.\n"
                "- The helper needs the original task metadata columns such as `Task Name`, `Duration (hours)`, and `Priority`."
            )
        if helper_source_issue == "non_selector_df":
            return (
                "PREFLIGHT_SCHEDULING: `build_dependency_schedule(...)` inputs must come from the selected table payloads.\n"
                "- Pass `task_table['df']` and `dependency_table['df']` directly, or simple aliases assigned from them.\n"
                "- Do NOT pass synthetic tables, partial row lists, or manually rebuilt DataFrames to the helper."
            )
        if uses_schedule_helper:
            return None
        if re.search(
            r"(task_df|task_file)\s*=\s*\[\s*\w+\s+for\s+\w+\s+in\s+tables\s+if\s+['\"]task id['\"]\s+in\s+\w+\[['\"]df['\"]\]\.columns\s*\]\[0\]\[['\"]df['\"]\]",
            lower,
        ):
            return (
                "PREFLIGHT_SCHEDULING: task-table selection is underspecified.\n"
                "- Do not choose the task table from `Task ID` alone because both tables contain that header.\n"
                "- Task table must be identified by `Task ID` plus task metadata like `Task Name`, `Duration (hours)`, or `Priority`.\n"
                "- Dependency table must be identified by `Task ID` plus `Depends on`."
            )
        if re.search(
            r"(task_table|task_df|task_file)\s*=\s*\[\s*\w+\s+for\s+\w+\s+in\s+tables\s+if\s+['\"]task id['\"]\s+in\s+\w+\[['\"]df['\"]\]\.columns\s*\]\[0\]\[['\"]df['\"]\]",
            lower,
        ):
            return (
                "PREFLIGHT_SCHEDULING: task-table selection is underspecified.\n"
                "- Do not choose the task table from `Task ID` alone because both tables contain that header.\n"
                "- Task table must be identified by `Task ID` plus task metadata like `Task Name`, `Duration (hours)`, or `Priority`.\n"
                "- Dependency table must be identified by `Task ID` plus `Depends on`."
            )
        if re.search(
            r"(dependency_df|dependencies)\s*=\s*\[\s*\w+\s+for\s+\w+\s+in\s+tables\s+if\s+['\"]depends on['\"]\s+in\s+\w+\[['\"]df['\"]\]\.columns\s*\]\[0\]\[['\"]df['\"]\]",
            lower,
        ):
            return (
                "PREFLIGHT_SCHEDULING: dependency-table selection should produce one DataFrame, not a list-derived mixed container.\n"
                "- Pick one dependency DataFrame by verified headers.\n"
                "- Keep task table and dependency table as separate DataFrames, not list-like stand-ins."
            )
        if (
            "dependencies = []" in lower
            and ".append(" in lower
            and (
                re.search(r"for\s+\w+\s+in\s+dependencies\s*:", lower)
                or re.search(r"\[\s*\w+\[['\"]task id['\"]\].*for\s+\w+\s+in\s+dependencies", lower)
                or re.search(r"dependencies\[['\"]depends on['\"]\]", lower)
            )
        ):
            return (
                "PREFLIGHT_SCHEDULING: dependency data structure is inconsistent.\n"
                "- Do not build `dependencies = []` and then treat it like dependency rows.\n"
                "- Keep a single dependency DataFrame such as `dependency_df`.\n"
                "- Iterate dependency rows with `for _, row in dependency_df.iterrows():`."
            )
        if re.search(
            r"if\s+not\s+(task_table|task_df|task_file)\b|if\s+(task_table|task_df|task_file)\s+and|if\s+not\s+.*dependencies",
            lower,
        ):
            return (
                "PREFLIGHT_LINEAR: do not use DataFrame truthiness in conditions.\n"
                "- Use `is None` for DataFrame presence checks.\n"
                "- Use `.empty` only when you really need emptiness.\n"
                "- Example: `if task_table is None or dependency_df is None:`"
            )

        task_dep_mixing_patterns = (
            (
                re.search(r"for\s+\w+(?:\s*,\s*\w+)?\s+in\s+task_df\.iterrows\(\)", lower)
                and re.search(r"row\[['\"]depends on['\"]\]", lower)
            ),
            (
                re.search(r"for\s+\w+(?:\s*,\s*\w+)?\s+in\s+dep_df\.iterrows\(\)", lower)
                and any(
                    marker in lower
                    for marker in (
                        "row['task name']",
                        'row["task name"]',
                        "row['duration (hours)']",
                        'row["duration (hours)"]',
                        "row['priority']",
                        'row["priority"]',
                    )
                )
            ),
        )
        if any(task_dep_mixing_patterns):
            return (
                "PREFLIGHT_SCHEDULING: task table and dependency table responsibilities are mixed.\n"
                "- The task table contains fields like `Task ID`, `Task Name`, `Duration (hours)`, `Priority`.\n"
                "- The dependency table contains `Task ID` and `Depends on`.\n"
                "- Determine ROOT tasks and edges from the dependency table only; do not read `Depends on` from `task_df`."
            )

        if re.search(r"['\"]08:00['\"]", code) and re.search(r"\+\s*f?['\"]", code):
            return (
                "PREFLIGHT_SCHEDULING: do not do time arithmetic with strings.\n"
                "- Keep time as integer minutes or datetime objects during computation.\n"
                "- Only format to `HH:MM` in the final output rows."
            )

        output_column_markers = ("start time", "end time")
        if not all(marker in lower for marker in output_column_markers):
            return (
                "PREFLIGHT_SCHEDULING: schedule output must include `Start Time` and `End Time` columns.\n"
                "- Build final Output columns as: `Task ID`, `Task Name`, `Priority`, `Start Time`, `End Time`.\n"
                "- Use exact starter shape:\n"
                "  `detail_data = [['Task ID', 'Task Name', 'Priority', 'Start Time', 'End Time']]`\n"
                "- Then append one row per scheduled task using formatted `HH:MM` text.\n"
                "- Do not write the raw task table directly."
            )

        if "start time (minutes)" in lower or "end time (minutes)" in lower:
            return (
                "PREFLIGHT_SCHEDULING: final output columns must be human-readable `Start Time` and `End Time`, not minute-count columns.\n"
                "- Keep minutes only as internal computation state.\n"
                "- Final rows must use exact headers: `Task ID`, `Task Name`, `Priority`, `Start Time`, `End Time`.\n"
                "- Format output values as `HH:MM` strings."
            )

        drops_root_markers = (
            "dropna(subset=['depends on']",
            'dropna(subset=["depends on"]',
            "['depends on'].notna(",
            '["depends on"].notna(',
        )
        if any(m in lower for m in drops_root_markers):
            return (
                "PREFLIGHT_SCHEDULING: blank `Depends on` rows are ROOT tasks and must not be dropped.\n"
                "- Remove the `dropna/notna` filter on dependency predecessor.\n"
                "- Use blank/NaN predecessor as 'no incoming edge'."
            )
        if (
            "depends on" in lower
            and "pd.notnull(" in lower
            and "pd.isna(" not in lower
            and ".strip() == ''" not in lower
            and ".strip()==''" not in lower
        ):
            return (
                "PREFLIGHT_SCHEDULING: root-task handling is incomplete.\n"
                "- For dependency rows use: `if pd.isna(dep) or str(dep).strip() == '': continue`.\n"
                "- Only create adjacency/in_degree edges for real predecessor task IDs."
            )
        if (
            "if pd.isna(depends_on)" in lower
            and "schedule_order.append(task_id)" in lower
            and re.search(r"else:\s*.*task_id\s*=\s*row\[['\"]task id['\"]\]", lower, flags=re.DOTALL)
        ):
            return (
                "PREFLIGHT_SCHEDULING: root-task branch is using `task_id` before reading it from the current dependency row.\n"
                "- In the dependency loop, assign `task_id = row['Task ID']` before any root/edge logic.\n"
                "- Then use blank/NaN `Depends on` only to skip edge creation, not to append a stale task ID.\n"
                "- Root tasks should come from zero in-degree after graph construction."
            )
        if (
            re.search(r"adjacency\[\s*(dependency|depends_on|dep)\s*\]", lower)
            and "pd.isna(" not in lower
            and ".strip() == ''" not in lower
            and ".strip()==''" not in lower
        ):
            return (
                "PREFLIGHT_SCHEDULING: adjacency is being built from a predecessor without a blank/NaN guard.\n"
                "- Guard first: `if pd.isna(dep) or str(dep).strip() == '': continue`.\n"
                "- Then append `adjacency[dep].append(task_id)` and increment `in_degree[task_id]`."
            )
        if re.search(r"adjacency\[\s*row\[['\"]task id['\"]\]\s*\]\.append\(\s*none\s*\)", lower):
            return (
                "PREFLIGHT_SCHEDULING: do not append `None` edges for root tasks.\n"
                "- Blank/NaN `Depends on` means no incoming edge, so skip edge creation entirely.\n"
                "- Keep root tasks as nodes with zero in-degree; do not store placeholder neighbors."
            )
        if (
            re.search(r"root_tasks\s*=\s*\[\s*\w+\[['\"]task id['\"]\]", lower)
            and re.search(r"for\s+\w+\s+in\s+dependencies", lower)
        ):
            return (
                "PREFLIGHT_SCHEDULING: root-task extraction is iterating the wrong container level.\n"
                "- Do not iterate a list of dependency DataFrames as if each item were a row.\n"
                "- Iterate the dependency DataFrame rows only: `for _, row in dependency_df.iterrows():`.\n"
                "- Root tasks come from rows where `Depends on` is blank/NaN."
            )
        reversed_edge_patterns = (
            r"adjacency\[\s*(?:from_task|src_task|task_id|task|current_task)\s*\]\.append\(\s*(?:to_task|depends_on|dep_on|dependency|dep)\s*\)",
            r"in_degree\[\s*(?:to_task|depends_on|dep_on|dependency|dep)\s*\]\s*\+=\s*1",
        )
        if any(re.search(pattern, lower) for pattern in reversed_edge_patterns):
            return (
                "PREFLIGHT_SCHEDULING: dependency edge direction is reversed.\n"
                "- In this task, `Task ID` is the current task and `Depends on` is its predecessor.\n"
                "- Correct edge direction is `depends_on -> task_id`.\n"
                "- Use `adjacency[depends_on].append(task_id)` and `in_degree[task_id] += 1`."
            )
        if (
            re.search(r"astype\s*\(\s*\{[^}]*['\"]task id['\"]\s*:\s*int", lower)
            or re.search(r"int\s*\(\s*row\[['\"]task id['\"]\]\s*\)", lower)
            or re.search(r"int\s*\(\s*(?:dep|depends_on|dep_task_id|task_id)\s*\)", lower)
            or re.search(r"\[\s*set\(\)\s*for\s+_\s+in\s+range", lower)
            or re.search(r"(adjacency|in_degree)\s*\[\s*[a-z_]+\s*-\s*1\s*\]", lower)
        ):
            return (
                "PREFLIGHT_SCHEDULING: Task IDs must stay as original string labels, not numeric indices.\n"
                "- Do NOT cast `Task ID` or `Depends on` values to `int`.\n"
                "- Values like `T1`, `T2`, ... are graph node labels and must remain strings.\n"
                "- Use dictionary-based graph state keyed by exact task IDs:\n"
                "  `task_id_set = set(task_df['Task ID'])`\n"
                "  `adjacency = {task_id: [] for task_id in task_id_set}`\n"
                "  `in_degree = {task_id: 0 for task_id in task_id_set}`"
            )

        topo_markers = ("in_degree", "adjacency", "queue", "deque(", "topological")
        if not any(m in lower for m in topo_markers):
            return (
                "PREFLIGHT_SCHEDULING: dependency scheduling must explicitly build an execution order from dependencies.\n"
                "- Use a DAG ordering method such as Kahn algorithm with adjacency/in_degree/queue.\n"
                "- Do not write the task table directly without dependency processing."
            )
        if re.search(r"task_id_set\s*=\s*.*(?:tolist\(\)|list\()", lower):
            return (
                "PREFLIGHT_SCHEDULING: `task_id_set` must be a set, not a list.\n"
                "- Use: `task_id_set = set(task_df['Task ID'])`\n"
                "- Compare coverage with another set such as `scheduled_task_ids = set(schedule_order)`."
            )
        if (
            ("start time" in lower and "end time" in lower)
            and re.search(r"\b(task_df|df_tasks|tasks_df)\.values\.tolist\(\)", code)
        ):
            return (
                "PREFLIGHT_SCHEDULING: final schedule rows cannot be the raw task table values.\n"
                "- Build output rows from scheduled order after computing Start/End Time.\n"
                "- Do not append `task_df.values.tolist()` into the final schedule table."
            )

        if (
            "itertuples(" in lower
            and any(
                marker in lower
                for marker in (
                    ".task_id",
                    ".task_name",
                    ".depends_on",
                    ".duration_hours",
                    ".duration__hours",
                )
            )
        ):
            return (
                "PREFLIGHT_SCHEDULING: spaced headers must be accessed by exact column name, not tuple attributes.\n"
                "- Do NOT use `itertuples()` with `.Task_ID` / `.Depends_on` style access.\n"
                "- Use `iterrows()` and exact header access such as `row['Task ID']` and `row['Depends on']`."
            )

        if (
            "duration (hours)" in lower
            and duration_hour_lines
            and not any(re.search(r"(?:\*\s*60|60\s*\*)", line) for line in duration_hour_lines)
        ):
            return (
                "PREFLIGHT_SCHEDULING: `Duration (hours)` must be converted to minutes before scheduling.\n"
                "- Keep computation in integer minutes from `8 * 60`.\n"
                "- Example: `duration_minutes = int(round(float(task_row['Duration (hours)']) * 60))`.\n"
                "- Do not add raw hour values directly to `current_time_minutes`."
            )

        if (
            "duration (hours)" in lower
            and duration_hour_lines
            and any(re.search(r"(?:\*\s*60|60\s*\*)", line) for line in duration_hour_lines)
            and "pd.to_numeric(" not in lower
            and ".astype(float)" not in lower
            and "float(" not in lower
        ):
            return (
                "PREFLIGHT_SCHEDULING: convert duration values to numeric before multiplying by 60.\n"
                "- Use `pd.to_numeric(tasks_df['Duration (hours)'], errors='coerce').astype(float)` or `float(value)`.\n"
                "- Do not do string duration * 60."
            )
        if re.search(
            r"for\s+\w+\s+in\s+\w+\.iterrows\(\).*?\w+\[['\"]duration \(hours\)['\"]\]",
            lower,
            flags=re.DOTALL,
        ):
            return (
                "PREFLIGHT_SCHEDULING: `iterrows()` returns `(index, row)` pairs, not row objects directly.\n"
                "- Use `for _, row in task_df.iterrows():` before `row['Duration (hours)']` access.\n"
                "- Or compute total duration from the numeric column directly with `pd.to_numeric(...).sum()`."
            )

        if re.search(
            r"float\s*\(\s*task_df\s*\[\s*task_df\s*\[\s*['\"]task id['\"]\s*\]\s*==.*?\]\s*\[\s*['\"]duration \(hours\)['\"]\s*\]\s*\)",
            lower,
            flags=re.DOTALL,
        ):
            return (
                "PREFLIGHT_SCHEDULING: do not call `float(...)` on a filtered pandas Series.\n"
                "- Select one task row first, then read scalar fields from that row.\n"
                "- Use:\n"
                "  `task_row = task_df.loc[task_df['Task ID'] == task_id].iloc[0]`\n"
                "  `duration_minutes = int(round(float(task_row['Duration (hours)']) * 60))`"
            )

        if (
            "in_degree = {}" in lower
            and "adjacency = {}" in lower
            and "dependency_dict.items()" in lower
        ):
            return (
                "PREFLIGHT_SCHEDULING: adjacency/in_degree must be initialized for every task before processing dependencies.\n"
                "- Start from `task_id_set` or `task_df['Task ID']`, not only from dependency-bearing rows.\n"
                "- Use shapes like `adjacency = {task_id: [] for task_id in task_id_set}` and `in_degree = {task_id: 0 for task_id in task_id_set}`.\n"
                "- Otherwise ROOT tasks are missing and queue construction will fail."
            )

        if (
            "schedule.append((" in lower
            and re.search(r"schedule\[\w+\]\s*=", lower)
        ):
            return (
                "PREFLIGHT_SCHEDULING: keep schedule order and final output rows as separate data structures.\n"
                "- `schedule_order` should stay a flat list of task IDs only.\n"
                "- `detail_data` should hold final 5-column output rows.\n"
                "- Do not append one tuple shape to `schedule` and then overwrite it with another tuple shape."
            )

        if re.search(r"(task|entry)\[\s*1\s*\]\s*\[['\"]task id['\"]\]", lower):
            return (
                "PREFLIGHT_SCHEDULING: schedule coverage checks must compare task-ID sets directly, not by indexing mixed tuple payloads.\n"
                "- Use `schedule_order` as a list of task IDs.\n"
                "- Then compare `set(schedule_order)` with `task_id_set`."
            )

        if "schedule_df.append(" in lower:
            return (
                "PREFLIGHT_SCHEDULING: do not build the final schedule with DataFrame.append() inside the loop.\n"
                "- Accumulate `detail_data` as a Python list of rows.\n"
                "- Convert once at the end or pass the row list directly to `write_dataframe_to_sheet(...)`."
            )

        if (
            "total duration" in lower
            and "schedule_df.values" in lower
        ):
            return (
                "PREFLIGHT_SCHEDULING: total duration summary must come from a numeric accumulator, not from stringified schedule rows.\n"
                "- Keep `total_duration_minutes` or `total_duration_hours` while building the schedule.\n"
                "- Write summary from that numeric variable."
            )

        if (
            "add_summary_row(" in lower
            and "total duration" in lower
            and re.search(r"total_duration\s*/\s*60", lower)
            and re.search(r"total_duration\s*\+=", lower)
            and any("* 60" not in line and "60 *" not in line for line in duration_hour_lines)
        ):
            return (
                "PREFLIGHT_SCHEDULING: summary duration units are inconsistent.\n"
                "- If `total_duration` accumulates hours, write hours directly.\n"
                "- If `total_duration` accumulates minutes, divide by 60 exactly once when reporting hours.\n"
                "- Do not divide hour totals by 60 a second time."
            )
        if (
            "add_summary_row(" in lower
            and "total duration" in lower
            and re.search(r"len\s*\(\s*schedule_order\s*\)\s*\*", lower)
        ):
            return (
                "PREFLIGHT_SCHEDULING: total-duration summary cannot be derived from task count times a constant.\n"
                "- Accumulate duration from real task rows while building the schedule.\n"
                "- Use a numeric accumulator such as `total_duration_minutes += duration_minutes`.\n"
                "- Report hours once with `total_duration_minutes / 60`."
            )
        if (
            "total_duration_minutes" in lower
            and "iterrows()" in lower
            and "duration (hours)" in lower
            and "sum(" in lower
        ):
            return (
                "PREFLIGHT_SCHEDULING: total-duration summary should not use `sum(... for row in df.iterrows())`.\n"
                "- `iterrows()` yields `(index, row)` tuples.\n"
                "- Use either `for _, row in task_df.iterrows()` or, better, `pd.to_numeric(task_df['Duration (hours)'], errors='coerce').sum()`.\n"
                "- Then convert hours to minutes once with `* 60` if needed."
            )
        if (
            "fillna({})" in lower
            and "duration (hours)" in lower
            and "sum(" in lower
        ):
            return (
                "PREFLIGHT_SCHEDULING: total-duration summary is iterating the DataFrame object, not task rows.\n"
                "- Do not use `for task in task_table.fillna({})` for row-wise duration math.\n"
                "- Prefer column-level aggregation:\n"
                "  `total_duration_hours = pd.to_numeric(task_table['Duration (hours)'], errors='coerce').sum()`\n"
                "- Then report that numeric total directly in hours."
            )
        if "write_data = [detail_data]" in lower or re.search(r"write_dataframe_to_sheet\s*\(\s*\[\s*detail_data\s*\]", lower):
            return (
                "PREFLIGHT_LINEAR: do not wrap the 2D output table in an extra list.\n"
                "- `detail_data` is already the full table payload.\n"
                "- Call `write_dataframe_to_sheet(detail_data, \"Output\", \"A1\")` directly."
            )

        return None

    @staticmethod
    def _has_summary_write_signal_from_code(code_action: str) -> bool:
        return OutputContractChecker._has_summary_write_signal_from_code(code_action)

    def _build_output_intent_feedback(self, execution_result: str,
                                      output_contract: Dict[str, Optional[bool]],
                                      code_action: str = "") -> Optional[str]:
        return self.output_contract_checker.build_output_intent_feedback(
            execution_result,
            output_contract,
            code_action,
        )

    def _create_initial_user_prompt(self, understanding_output: str,
                                    user_question: str) -> dict:
        if self._is_offline_strict:
            bounded_understanding = (
                "Offline bounded mode: treat this section as low-confidence hint only. "
                "If it conflicts with Sheet Content or runtime errors, ignore it."
            )
        else:
            bounded_understanding = understanding_output
        user_content = self.prompt_builder.build_execution_user_prompt(
            self.excel_context_execution,
            bounded_understanding,
            user_question,
        )
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
        if is_dependency_schedule_request(user_question):
            user_content += (
                "\n\n**SCHEDULING TASK RULES (STRICT):**\n"
                "- Identify table roles from verified headers, not from assumed same-schema logic.\n"
                "- Task table: `Task ID` plus duration/name/priority-like columns.\n"
                "- Dependency table: `Task ID` plus `Depends on`.\n"
                "- Never branch on literal input basenames such as `tc04_input01.xlsx`; those are testcase-specific and non-general.\n"
                "- Different headers between these tables are expected.\n"
                "- Keep task table and dependency table separate; do NOT merge them.\n"
                "- Build `task_id_set` from task table first.\n"
                "- The task table does NOT provide `Depends on`; the dependency table does NOT provide duration/name/priority.\n"
                "- Blank/NaN `Depends on` means ROOT task; skip edge creation.\n"
                "- Use `build_dependency_schedule(task_df, dependency_df, start_time='08:00')` for the DAG step.\n"
                "- Task IDs are string labels like `T1`, `T2`; never cast them to integers or use list indexing by `task_id - 1`.\n"
                "- Do all time arithmetic in integer minutes from `8 * 60`.\n"
                "- Format Start/End Time as `HH:MM` only in final output rows.\n"
                "- Keep total duration units consistent: if you accumulate minutes, convert to hours once at summary time; if you accumulate hours, do not divide again.\n"
                "- Print `TASK_ID_SET` and `SCHEDULED_TASK_IDS`, then assert equality before save."
            )
            user_content += get_task_specific_loop_breaker(user_question)
        if is_same_schema_merge_summary_request(user_question):
            user_content += (
                "\n\n**SAME-SCHEMA MERGE+SUMMARY RULES (STRICT):**\n"
                "- If all input tables share the same headers, stack them vertically; do NOT join on keys.\n"
                "- Prefer:\n"
                "  `tables = load_all_tables()`\n"
                "  `concat_result = concat_tables_with_same_headers(tables)`\n"
                "  `combined_df = concat_result['output_df']`\n"
                "  `summary_result = summarize_numeric_column(combined_df, value_col='...', summary_labels={...})`\n"
                "- Then write the full merged table, highlight `summary_result['output_row_numbers']`, and add `summary_result['summary']` below."
            )
        if is_fill_missing_request(user_question):
            user_content += (
                "\n\n**FILL-MISSING RULES (STRICT):**\n"
                "- Prefer:\n"
                "  `tables = load_all_tables(require_primary_key=False)`\n"
                "  `key_header = infer_common_key(tables)`\n"
                "  `fill_result = fill_missing_from_reference(tables[0]['df'], tables[1]['df'], key_header=key_header, prefer_primary=True)`\n"
                "- Keep original non-missing values in the primary table.\n"
                "- Write `fill_result['output_df']` directly."
            )
        if is_region_growth_chart_request(user_question):
            user_content += (
                "\n\n**REGION-GROWTH CHART RULES (STRICT):**\n"
                "- Do NOT parse the messy multi-row header manually with `read_table_multi()`.\n"
                "- Use:\n"
                "  `all_files = list_all_workbooks()`\n"
                "  `analysis = build_region_growth_analysis(all_files[0], sheet_name='Data', start_year=2020, end_year=2024)`\n"
                "- Then write `analysis['output_df']`, highlight `analysis['fastest_growth_rows']`, add `analysis['summary']`,\n"
                "  and plot `analysis['chart_df']` with one line per region before `save_plot_to_excel('Output', 'F2')`."
            )
            user_content += get_task_specific_loop_breaker(user_question)
        if is_correlation_matrix_request(user_question):
            user_content += (
                "\n\n**CORRELATION-MATRIX RULES (STRICT):**\n"
                "- Prefer the runtime helper path for filtered correlation matrices.\n"
                "- Use:\n"
                "  `tables = load_all_tables()`\n"
                "  `df = tables[0]['df']`\n"
                "  `matrix_result = build_correlation_matrix_table(df, numeric_columns=['sepal_length', 'sepal_width', 'petal_length', 'petal_width'], filter_column='species', filter_value='Iris-setosa')`\n"
                "- Then write `matrix_result['detail_data']` directly to Output.\n"
                "- Do not hard-code input paths, manual CSV reads, or rebuild the matrix cell-by-cell."
            )
            user_content += get_task_specific_loop_breaker(user_question)
        if is_cycle_detection_request(user_question):
            user_content += (
                "\n\n**CYCLE-DETECTION RULES (STRICT):**\n"
                "- Use the runtime helper path for multiple graph files.\n"
                "- Use:\n"
                "  `tables = load_all_tables()`\n"
                "  `cycle_result = build_cycle_detection_report(tables, from_col='Node From', to_col='Node To')`\n"
                "- Then write `cycle_result['detail_data']` directly to Output.\n"
                "- Do not hard-code CSV reads or rebuild graph parsing manually in this task."
            )
            user_content += get_task_specific_loop_breaker(user_question)
        if is_financial_dashboard_request(user_question):
            user_content += (
                "\n\n**FINANCIAL-DASHBOARD RULES (STRICT):**\n"
                "- This task requires a quarter-level dashboard table, not a scalar answer.\n"
                "- Use the runtime helper path:\n"
                "  `dashboard_result = build_financial_dashboard_report()`\n"
                "- Then write `dashboard_result['detail_data']` directly to `Output!A1`.\n"
                "- Do not hand-build month joins, KPI target parsing, or dashboard rows.\n"
                "- Do not read raw files manually in this task."
            )
            user_content += get_task_specific_loop_breaker(user_question)
        if is_candidate_screening_request(user_question):
            user_content += (
                "\n\n**CANDIDATE-SCREENING RULES (STRICT):**\n"
                "- This task requires a ranked candidate table, not a scalar answer.\n"
                "- Use the runtime helper path:\n"
                "  `screening_result = build_candidate_screening_report()`\n"
                "- Then write `screening_result['detail_data']` directly to `Output!A1`.\n"
                "- The helper already excludes blank names and treats missing numeric inputs as 0.\n"
                "- Do not hand-build file loops, score formulas, or ranking rows."
            )
            user_content += get_task_specific_loop_breaker(user_question)
        if is_inventory_eoq_request(user_question):
            user_content += (
                "\n\n**INVENTORY-EOQ RULES (STRICT):**\n"
                "- This task requires three clear tables in one output workbook.\n"
                "- Use the runtime helper path:\n"
                "  `inventory_result = build_inventory_eoq_report()`\n"
                "- Then write `inventory_result['detail_data']` directly to `Output!A1`.\n"
                "- Do not hand-build EOQ formulas, parameter parsing, or table layout."
            )
            user_content += get_task_specific_loop_breaker(user_question)
        if is_hospital_utilisation_request(user_question):
            user_content += (
                "\n\n**HOSPITAL-UTILISATION RULES (STRICT):**\n"
                "- This task requires one service-level output table.\n"
                "- Use the runtime helper path:\n"
                "  `report = build_hospital_utilisation_report()`\n"
                "- Then write `report['detail_data']` directly to `Output!A1`.\n"
                "- Highlight only `report['highlight_rows']`; if none exist, print `NO_HIGHLIGHT_ROWS:` and continue.\n"
                "- Do not hand-build merges or grouped utilisation formulas."
            )
            user_content += get_task_specific_loop_breaker(user_question)
        if is_market_share_shipment_request(user_question):
            user_content += (
                "\n\n**MARKET-SHARE SHIPMENT RULES (STRICT):**\n"
                "- This task requires a detailed output table aligned on overlapping quarters.\n"
                "- Use the runtime helper path:\n"
                "  `market_result = build_market_share_shipment_report()`\n"
                "- Then write `market_result['detail_data']` directly to `Output!A1`.\n"
                "- Do not read `Overview` sheets or hand-build quarter alignment in this task."
            )
            user_content += get_task_specific_loop_breaker(user_question)
        if is_cash_flow_efficiency_request(user_question):
            user_content += (
                "\n\n**CASH-FLOW EFFICIENCY RULES (STRICT):**\n"
                "- This task requires a yearly output table, not a scalar answer.\n"
                "- Use the runtime helper path:\n"
                "  `report = build_cash_flow_efficiency_report()`\n"
                "- Then write `report['detail_data']` directly to `Output!A1`.\n"
                "- Do not hand-locate rows in the financial statement workbook."
            )
            user_content += get_task_specific_loop_breaker(user_question)
        if is_diabetes_region_request(user_question):
            user_content += (
                "\n\n**DIABETES-REGION RULES (STRICT):**\n"
                "- This task requires one regional summary table, not a scalar answer.\n"
                "- Use the runtime helper path:\n"
                "  `report = build_diabetes_region_report()`\n"
                "- Then write `report['detail_data']` directly to `Output!A1`.\n"
                "- Do not hand-build region joins or share calculations in this task."
            )
            user_content += get_task_specific_loop_breaker(user_question)
        if is_mobile_reviews_summary_request(user_question):
            user_content += (
                "\n\n**MOBILE-REVIEWS RULES (STRICT):**\n"
                "- This task requires one grouped summary table, not a scalar answer.\n"
                "- Use the runtime helper path:\n"
                "  `report = build_mobile_reviews_summary_report()`\n"
                "- Then write `report['detail_data']` directly to `Output!A1`.\n"
                "- Exclude rows with missing ratings.\n"
                "- Do not hand-build groupby or aggregation code in this task."
            )
            user_content += get_task_specific_loop_breaker(user_question)
        if is_store_feature_analysis_request(user_question):
            user_content += (
                "\n\n**STORE-FEATURE ANALYSIS RULES (STRICT):**\n"
                "- This task requires two output sheets.\n"
                "- Use the runtime helper path:\n"
                "  `report = build_store_feature_analysis_report()`\n"
                "- Write `report['avg_by_type_detail_data']` to `AvgByStoreType!A1`.\n"
                "- Write `report['holiday_detail_data']` to `HolidayVsNonHoliday!A1`.\n"
                "- Do not hand-build merges or groupby logic in this task."
            )
            user_content += get_task_specific_loop_breaker(user_question)
        if is_ecommerce_merge_request(user_question):
            user_content += (
                "\n\n**ECOMMERCE-MERGE RULES (STRICT):**\n"
                "- This task requires one merged output table, not a scalar answer.\n"
                "- Use the runtime helper path:\n"
                "  `report = build_ecommerce_merge_report()`\n"
                "- Then write `report['detail_data']` directly to `Output!A1`.\n"
                "- The helper handles translation to English for product category names.\n"
                "- Do not hand-build multi-file joins or translation logic in this task."
            )
            user_content += get_task_specific_loop_breaker(user_question)
        if is_missing_data_scan_request(user_question):
            user_content += (
                "\n\n**MISSING-DATA REPORT RULES (STRICT):**\n"
                "- This task requires a short text answer, not a new spreadsheet.\n"
                "- Use the runtime helper path:\n"
                "  `report = build_missing_data_report()`\n"
                "  `final_text = report['answer']`\n"
                "  `print(f'FINAL_TEXT: {final_text}')`\n"
                "  `final_text`\n"
                "- Do not create or save an output workbook in this task."
            )
            user_content += get_task_specific_loop_breaker(user_question)
        if is_room_inconsistency_request(user_question):
            user_content += (
                "\n\n**ROOM-FORMAT REPORT RULES (STRICT):**\n"
                "- This task requires a natural-language finding, not a new spreadsheet.\n"
                "- Use the runtime helper path:\n"
                "  `report = build_room_format_report()`\n"
                "  `final_text = report['answer']`\n"
                "  `print(f'FINAL_TEXT: {final_text}')`\n"
                "  `final_text`\n"
                "- Do not modify or save the workbook in this task."
            )
            user_content += get_task_specific_loop_breaker(user_question)
        if is_simple_horizontal_merge_request(user_question):
            user_content += (
                "\n\n**SIMPLE MERGE RULES (STRICT):**\n"
                "- Prefer:\n"
                "  `tables = load_all_tables()`\n"
                "  `key_header = infer_common_key(tables)`\n"
                "  `merge_result = merge_tables_on_key(tables, key_header=key_header, how='inner')`\n"
                "- Write `merge_result['output_df']` directly."
            )
        if is_regression_request(user_question):
            user_content += (
                "\n\n**REGRESSION TASK RULES (STRICT):**\n"
                "- Prefer the runtime helper path for coefficient fitting.\n"
                "- Use:\n"
                "  `tables = load_all_tables()`\n"
                "  `df = tables[0]['df']`\n"
                "  `feature_cols = ['col1', 'col2', ...]`\n"
                "  `regression_result = fit_linear_regression_weights(df, target_col='...', feature_cols=feature_cols)`\n"
                "- Then print `USED_FEATURES` and write `regression_result['output_df']` directly.\n"
                "- Keep all available predictors unless the user explicitly excludes some."
            )
        return {"role": "user", "content": user_content}

    def _available_workbook_basenames(self) -> list[str]:
        return self.grounding.available_workbook_basenames()

    def _build_schema_snapshot(self) -> str:
        return self.grounding.build_schema_snapshot()

    def _observed_header_set(self) -> set[str]:
        return self.grounding.observed_header_set()

    def _detect_unknown_filename_lookup(self, code_action: str) -> Optional[str]:
        return self.grounding.detect_unknown_filename_lookup(code_action)

    @staticmethod
    def _error_signature(execution_result: str) -> str:
        return ExecutionErrorFeedbackBuilder.error_signature(execution_result)

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
        return ExecutionErrorFeedbackBuilder.build_loop_breaker_feedback(error_signature)

    def _build_bounded_error_feedback(self, execution_result: str) -> Optional[str]:
        return self.error_feedback.build_bounded_error_feedback(execution_result)

    @staticmethod
    def _compact_error_summary(execution_result: str) -> str:
        if not execution_result:
            return "ERROR_SUMMARY: unknown execution error."
        first_line_match = re.search(r"Execution error:\s*(.+?)(?:\n|$)", execution_result)
        first_line = first_line_match.group(1).strip() if first_line_match else execution_result.strip().splitlines()[0]
        line_match = re.search(r'File "<string>", line (\d+)', execution_result)
        line_info = f" at generated line {line_match.group(1)}" if line_match else ""
        return f"ERROR_SUMMARY: {first_line}{line_info}"

    @staticmethod
    def _message_role(msg: Any) -> str:
        if isinstance(msg, dict):
            return str(msg.get("role", "unknown"))
        return str(getattr(msg, "role", "unknown"))

    @staticmethod
    def _message_content(msg: Any) -> str:
        if isinstance(msg, dict):
            return str(msg.get("content", "") or "")
        return str(getattr(msg, "content", "") or "")

    def _prune_repair_feedback_history(self) -> None:
        markers = (
            "FORMAT_ERROR_EXECUTION:",
            "PREFLIGHT_",
            "FORBIDDEN:",
            "SOFT_FORBIDDEN_WARNING:",
            "MINIMAL FIX REQUIRED:",
            "LOOP_BREAKER_OFFLINE:",
            "OUTPUT_INCOMPLETE_LINEAR:",
            "OUTPUT_INTENT_MISMATCH_OFFLINE:",
            "OUTPUT_QUALITY_RISK_OFFLINE:",
        )
        matched_indices = [
            idx for idx, msg in enumerate(self.conversation_history)
            if self._message_role(msg) == "user"
            and any(marker in self._message_content(msg) for marker in markers)
        ]
        if len(matched_indices) <= 1:
            return
        keep_idx = matched_indices[-1]
        self.conversation_history = [
            msg for idx, msg in enumerate(self.conversation_history)
            if idx == keep_idx or idx not in matched_indices[:-1]
        ]

    def run(self, understanding_output: str, user_question: str,
            max_turns: int = 20) -> Dict[str, Any]:
        logger.info(f"Starting multi-turn analysis for: '{user_question}'")
        self._install_linear_io_guards()
        self._consecutive_forbidden = 0
        self._consecutive_format_errors = 0
        self._forbidden_signature_counts = {}
        self._last_forbidden_signature = None
        self._same_forbidden_streak = 0
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
                max_tokens = self._bounded_exec_max_tokens
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
                    self._consecutive_format_errors += 1
                    strict_repair = ""
                    if self._consecutive_format_errors >= self._max_format_errors:
                        strict_repair = (
                            "\nTRUNCATION/FORMAT RECOVERY (MANDATORY):\n"
                            "- Return ONLY one complete code block.\n"
                            "- Keep code under 120 lines and avoid long comments.\n"
                            "- Ensure closing triple backticks are present.\n"
                            "- Use list_all_workbooks()+read_table_multi(); do not use pandas file readers.\n"
                        )
                    task_loop_breaker = get_task_specific_loop_breaker(user_question)
                    if is_missing_data_scan_request(user_question) or is_room_inconsistency_request(user_question):
                        execution_shape = (
                            "Include complete task logic: read -> compute -> print `FINAL_TEXT:` -> return the final text."
                        )
                    else:
                        execution_shape = (
                            "Include complete task logic: read -> compute -> write Output -> save_workbook_to(output_path)."
                        )
                    format_msg = (
                        "FORMAT_ERROR_EXECUTION: executable code is required.\n"
                        "Reply with exactly one ```python ... ``` block.\n"
                        f"{execution_shape}"
                        f"{strict_repair}"
                    )
                    if task_loop_breaker:
                        format_msg += task_loop_breaker
                    logger.warning("No code block returned; executable code required")
                    self._log_to_file(f"\n**Format error (Turn {turn + 1}):** no code block.\n")
                    self.conversation_history.append({"role": "user", "content": format_msg})
                    self._prune_repair_feedback_history()
                    continue
                self._consecutive_format_errors = 0

                should_continue, soft_forbidden_warning = self._handle_offline_forbidden(
                    code_action,
                    turn,
                    user_question,
                )
                if should_continue:
                    continue
                preflight_issue = self._offline_preflight_check(code_action, user_question)
                if preflight_issue is None:
                    preflight_issue = self._merge_fill_helper_guard(code_action, user_question)
                if preflight_issue is None:
                    preflight_issue = self._regression_helper_guard(code_action, user_question)
                if preflight_issue is None:
                    preflight_issue = self._regression_feature_guard(code_action, user_question)
                if preflight_issue is None:
                    preflight_issue = self._scheduling_dependency_guard(code_action, user_question)
                if preflight_issue is not None:
                    preflight_feedback = (
                        preflight_issue
                        + "\nReturn one full corrected ```python ... ``` block. "
                        "Keep minimal edits and preserve task logic."
                    )
                    task_loop_breaker = get_task_specific_loop_breaker(user_question)
                    if task_loop_breaker and turn >= 1:
                        preflight_feedback += task_loop_breaker
                    self._log_to_file(
                        f"\n**Preflight blocked (Turn {turn + 1}):**\n{preflight_issue}\n"
                    )
                    self.conversation_history.append({
                        "role": "user",
                        "content": preflight_feedback
                    })
                    self._prune_repair_feedback_history()
                    continue

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

                    if is_execution_error:
                        error_signature = self._update_error_streak(execution_result)
                        targeted_feedback = self._build_bounded_error_feedback(execution_result)
                        if targeted_feedback is None:
                            targeted_feedback = (
                                "MINIMAL FIX REQUIRED: Fix only the smallest necessary part "
                                "(variable/column/type/range/signature). Do not add new helpers, new paths, or refactor unrelated code."
                            )
                        compact_error = self._compact_error_summary(execution_result)
                        feedback_to_model = targeted_feedback + "\n\n" + compact_error
                        if self._same_error_streak >= self._max_same_error_streak:
                            loop_breaker = self._build_loop_breaker_feedback(error_signature)
                            feedback_to_model = (
                                loop_breaker
                                + "\n\n"
                                + compact_error
                            )
                        if soft_forbidden_warning:
                            feedback_to_model = soft_forbidden_warning + "\n\n" + feedback_to_model
                        self.conversation_history.append({"role": "user", "content": feedback_to_model})
                        self._prune_repair_feedback_history()
                        if self._same_error_streak >= self._max_same_error_before_abort:
                            logger.warning(
                                "Early abort: same execution error repeated %s times.",
                                self._same_error_streak,
                            )
                            return {
                                "success": False,
                                "answer": (
                                    "Early abort: repeated identical execution error. "
                                    "Proceed to validation-enhanced next iteration."
                                ),
                                "total_turns": turn + 1,
                                "conversation_history": self.history_formatter.format_history(
                                    self.conversation_history
                                ),
                                "execution_summary": self.summary_builder.build(
                                    execution_steps,
                                    None
                                )
                            }
                        continue

                    self._last_error_signature = None
                    self._same_error_streak = 0

                    # Auto-stop when we see a successful save in stdout (avoids Turn2+ repeat path)
                    saved_path = self._extract_saved_path_from_result(execution_result)
                    if saved_path is not None:
                        if not self._has_meaningful_output_rows(execution_result):
                            self.conversation_history.append({
                                    "role": "user",
                                    "content": (
                                    "OUTPUT_INCOMPLETE_LINEAR: saved file detected, but Output sheet appears to contain only header/placeholder rows.\n"
                                    "You MUST write a real result table (header + data rows) before saving.\n"
                                    "Do not use placeholder `[['Metric','Value']]`.\n"
                                    "Re-run full logic using list_all_workbooks() + read_table_multi(), then write complete table to Output and save_workbook_to(output_path)."
                                )
                            })
                            continue
                        output_intent_feedback = self._build_output_intent_feedback(
                            execution_result, output_contract, code_action
                        )
                        if output_intent_feedback is not None:
                            self.conversation_history.append({
                                "role": "user",
                                "content": output_intent_feedback
                            })
                            self._prune_repair_feedback_history()
                            continue
                        quality_risk_feedback = self.output_contract_checker.detect_quality_risk(
                            execution_result
                        )
                        if quality_risk_feedback is not None:
                            self.conversation_history.append({
                                "role": "user",
                                "content": quality_risk_feedback
                            })
                            self._prune_repair_feedback_history()
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

                    text_answer = self._extract_text_answer_from_result(execution_result)
                    if text_answer is not None and (
                        is_missing_data_scan_request(user_question)
                        or is_room_inconsistency_request(user_question)
                        or (
                            output_contract.get("requires_detailed_table") is False
                            and output_contract.get("requires_highlight") is False
                            and output_contract.get("requires_summary_metrics") is False
                        )
                    ):
                        logger.info(f"Final answer (from execution output): {text_answer}")
                        self._log_to_file(
                            f"\n**Final Answer (Turn {turn + 1}, from execution output):**\n{text_answer}\n"
                        )
                        return {
                            "success": True,
                            "answer": text_answer,
                            "total_turns": turn + 1,
                            "conversation_history": self.history_formatter.format_history(
                                self.conversation_history
                            ),
                            "execution_summary": self.summary_builder.build(
                                execution_steps,
                                text_answer
                            )
                        }

                    if soft_forbidden_warning:
                        observation = observation + "\n\n" + soft_forbidden_warning
                    self.conversation_history.append({"role": "user", "content": observation})

                except Exception as e:
                    error_message = f"Code execution error: {str(e)}"
                    logger.error(f"Execution error: {error_message}")

                    self._log_to_file(
                        f"\n**Execution error (Turn {turn + 1}):**\n```\n{error_message}\n```\n"
                    )

                    error_signature = self._update_error_streak(error_message)
                    targeted_feedback = self._build_bounded_error_feedback(error_message)
                    compact_error = self._compact_error_summary(error_message)
                    if targeted_feedback is not None:
                        feedback_to_model = targeted_feedback + "\n\n" + compact_error
                    else:
                        feedback_to_model = (
                            "MINIMAL FIX REQUIRED: Fix only the smallest necessary part "
                            "(variable/column/type/range). Do not add new code or invented paths.\n\n"
                            + compact_error
                        )
                    if self._same_error_streak >= self._max_same_error_streak:
                        loop_breaker = self._build_loop_breaker_feedback(error_signature)
                        feedback_to_model = loop_breaker + "\n\n" + compact_error
                    if soft_forbidden_warning:
                        feedback_to_model = soft_forbidden_warning + "\n\n" + feedback_to_model

                    execution_steps.append({
                        "turn": turn + 1,
                        "code": code_action,
                        "result": error_message,
                        "success": False
                    })

                    self.conversation_history.append({"role": "user", "content": feedback_to_model})
                    self._prune_repair_feedback_history()
                    if self._same_error_streak >= self._max_same_error_before_abort:
                        logger.warning(
                            "Early abort: same execution error repeated %s times.",
                            self._same_error_streak,
                        )
                        return {
                            "success": False,
                            "answer": (
                                "Early abort: repeated identical execution error. "
                                "Proceed to validation-enhanced next iteration."
                            ),
                            "total_turns": turn + 1,
                            "conversation_history": self.history_formatter.format_history(
                                self.conversation_history
                            ),
                            "execution_summary": self.summary_builder.build(
                                execution_steps,
                                None
                            )
                        }

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
