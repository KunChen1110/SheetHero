"""Execution runtime loop for multi-turn analysis."""

import os
import re
from typing import Dict, Any, Optional

from ...log.logger_registry import LoggerRegistry
from ...skills import detect_skill, detect_skills, select_helper
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
from .core.summary import ExecutionSummary
from .guards.loop_breakers import get_task_specific_loop_breaker
from .analysis.workbook_grounding import WorkbookGrounding
from .skill import (
    ExecutionGenericPreflightAdvisor,
    ExecutionSkillPreflightAdvisor,
    ExecutionSkillPromptAdvisor,
    ExecutionQuestionInferenceAdvisor,
)
from ..base.runtime import StageRuntime
from ...prompt.prompt_builder import PromptBuilder

logger = LoggerRegistry.setup_logger(__name__)

_REPAIR_FEEDBACK_MARKERS = (
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


def _is_thinking_model(deployment: str) -> bool:
    return (deployment or "").lower().startswith("qwen3")


def _assistant_message_to_dict(message: Any) -> Dict[str, str]:
    if isinstance(message, dict):
        return {
            "role": message.get("role", "assistant"),
            "content": message.get("content", "") or "",
        }
    return {
        "role": "assistant",
        "content": getattr(message, "content", "") or "",
    }


def _resolve_initial_exec_max_tokens(deployment: str, bounded_exec_max_tokens: int) -> int:
    raw_value = os.getenv("SHEETHERO_INITIAL_EXEC_MAX_TOKENS")
    if raw_value is not None and raw_value.strip():
        try:
            return max(1, int(raw_value))
        except ValueError:
            pass
    if _is_thinking_model(deployment):
        return min(bounded_exec_max_tokens, 768)
    return 768


def _resolve_recovery_max_tokens(deployment: str, bounded_exec_max_tokens: int) -> int:
    raw_value = os.getenv("SHEETHERO_LLM_RECOVERY_MAX_TOKENS")
    if raw_value is not None and raw_value.strip():
        try:
            return max(1, int(raw_value))
        except ValueError:
            pass
    if _is_thinking_model(deployment):
        return min(bounded_exec_max_tokens, 768)
    return 768


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
        self.generic_preflight = ExecutionGenericPreflightAdvisor(self)
        self.skill_preflight = ExecutionSkillPreflightAdvisor(self)
        self.skill_prompt = ExecutionSkillPromptAdvisor(self)
        self.question_inference = ExecutionQuestionInferenceAdvisor(self)
        self.error_feedback = ExecutionErrorFeedbackBuilder(
            available_workbook_basenames_fn=self._available_workbook_basenames,
            observed_header_set_fn=self._observed_header_set,
            build_schema_snapshot_fn=self._build_schema_snapshot,
        )

        self.conversation_history = []
        self._consecutive_forbidden = 0
        self._consecutive_format_errors = 0
        self._bounded_exec_max_tokens = int(
            os.getenv("SHEETHERO_EXECUTION_MAX_TOKENS", "1536")
        )
        self._initial_exec_max_tokens = _resolve_initial_exec_max_tokens(
            deployment,
            self._bounded_exec_max_tokens,
        )
        self._llm_recovery_max_tokens = _resolve_recovery_max_tokens(
            deployment,
            self._bounded_exec_max_tokens,
        )
        self._max_llm_error_retries = int(
            os.getenv("SHEETHERO_MAX_LLM_ERROR_RETRIES", "2")
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
        self._max_same_preflight_streak = int(
            os.getenv("SHEETHERO_MAX_SAME_PREFLIGHT_STREAK", "2")
        )
        self._max_same_error_before_abort = int(
            os.getenv("SHEETHERO_MAX_SAME_ERROR_BEFORE_ABORT", "4")
        )
        self._last_error_signature: Optional[str] = None
        self._same_error_streak = 0
        self._last_preflight_signature: Optional[str] = None
        self._same_preflight_streak = 0
        self._forbidden_signature_counts: Dict[str, int] = {}
        self._last_forbidden_signature: Optional[str] = None
        self._same_forbidden_streak = 0
        self._llm_error_streak = 0
        self._active_understanding_output = ""

    def _build_helper_timeout_fallback_code(
        self,
        user_question: str,
        output_contract: Dict[str, Optional[bool]],
    ) -> Optional[str]:
        skill = detect_skill(user_question)
        helper = select_helper(skill, user_question) if skill else None
        helper_name = helper.name if helper else ""

        if helper_name == "build_relational_join_enrichment_report":
            return "\n".join(
                [
                    "report = build_relational_join_enrichment_report(key_header=None, how='inner')",
                    "create_output_sheet('Output')",
                    "write_dataframe_to_sheet(report['detail_data'], 'Output', 'A1')",
                    "saved_file = save_workbook_to(output_path)",
                    "print(f'SAVED_FILE: {saved_file}')",
                    "saved_file",
                ]
            )

        if helper_name == "build_grouped_aggregation_ranking_report":
            return "\n".join(
                [
                    "report = build_grouped_aggregation_ranking_report()",
                    "create_output_sheet('Output')",
                    "write_dataframe_to_sheet(report['detail_data'], 'Output', 'A1')",
                    "add_summary_row('Output', len(report['detail_data']) + 2, report['summary'])",
                    "saved_file = save_workbook_to(output_path)",
                    "print(f'SAVED_FILE: {saved_file}')",
                    "saved_file",
                ]
            )

        if helper_name == "build_time_series_aggregation_report":
            lines = [
                "report = build_time_series_aggregation_report(period='year', aggregate='sum', sort_desc=False)",
                "output_df = report['output_df'].copy()",
                "year_col = output_df.columns[0]",
                "value_col = output_df.columns[1]",
                "base_value_name = value_col.replace('Total ', '') if value_col.startswith('Total ') else value_col",
                "output_df = output_df.rename(columns={year_col: 'Year', value_col: base_value_name})",
                "output_df['YoY_Growth_pct'] = output_df[base_value_name].pct_change() * 100",
                "output_df['YoY_Growth_pct'] = output_df['YoY_Growth_pct'].round(2)",
                "output_df['High_Growth'] = output_df['YoY_Growth_pct'].apply(lambda v: 'YES' if pd.notna(v) and v > 10 else 'NO')",
                "create_output_sheet('Output')",
                "write_dataframe_to_sheet(output_df, 'Output', 'A1')",
                "summary_result = {'Rows Used': int(len(output_df)), 'Latest Year': str(output_df['Year'].iloc[-1]) if len(output_df) else ''}",
                "add_summary_row('Output', len(output_df) + 2, summary_result)",
            ]
            if output_contract.get("requires_highlight") is True:
                lines.extend(
                    [
                        "row_numbers = [i + 2 for i, value in enumerate(output_df['High_Growth'].tolist()) if str(value).strip().upper() == 'YES']",
                        "if row_numbers:",
                        "    highlight_rows('Output', row_numbers, {'fill_color': 'red'})",
                        "else:",
                        "    print('NO_HIGHLIGHT_ROWS: []')",
                    ]
                )
            lines.extend(
                [
                    "saved_file = save_workbook_to(output_path)",
                    "print(f'SAVED_FILE: {saved_file}')",
                    "saved_file",
                ]
            )
            return "\n".join(lines)

        return None

    def _try_timeout_helper_fallback(
        self,
        user_question: str,
        output_contract: Dict[str, Optional[bool]],
        execution_steps: list[Dict[str, Any]],
        turn_index: int,
    ) -> Optional[Dict[str, Any]]:
        if not self._is_offline_strict:
            return None
        fallback_code = self._build_helper_timeout_fallback_code(user_question, output_contract)
        if not fallback_code:
            return None

        self._log_to_file(
            f"\n**Helper timeout fallback (Turn {turn_index + 1}):**\n```python\n{fallback_code}\n```\n"
        )
        try:
            execution_result = self.executor.execute(fallback_code)
        except Exception as exc:
            self._log_to_file(
                f"\n**Helper timeout fallback error (Turn {turn_index + 1}):**\n```\n{str(exc)}\n```\n"
            )
            return None

        execution_steps.append({
            "turn": turn_index + 1,
            "code": fallback_code,
            "result": execution_result,
            "success": "Execution error:" not in execution_result and "Traceback:" not in execution_result,
        })
        self._log_to_file(
            f"\n**Helper timeout fallback result (Turn {turn_index + 1}):**\n```\n{execution_result}\n```\n"
        )

        saved_path = self._extract_saved_path_from_result(execution_result)
        if saved_path is None:
            return None
        if not self._has_meaningful_output_rows(execution_result):
            return None
        output_intent_feedback = self._build_output_intent_feedback(
            execution_result,
            output_contract,
            fallback_code,
        )
        if output_intent_feedback is not None:
            self._log_to_file(
                f"\n**Helper timeout fallback rejected (Turn {turn_index + 1}):**\n{output_intent_feedback}\n"
            )
            return None

        self._log_to_file(
            f"\n**Final Answer (Turn {turn_index + 1}, from helper timeout fallback):**\n{saved_path}\n"
        )
        return {
            "success": True,
            "answer": saved_path,
            "total_turns": turn_index + 1,
            "conversation_history": self.history_formatter.format_history(
                self.conversation_history
            ),
            "execution_summary": self.summary_builder.build(
                execution_steps,
                saved_path
            ),
        }

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

    @staticmethod
    def _is_text_output_skill(user_question: str) -> bool:
        skills = detect_skills(user_question)
        skill = skills[0] if skills else None
        return skill is not None and skill.output_mode == "text"

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

    @staticmethod
    def _offline_no_think_prefix() -> str:
        return (
            "/no_think\n"
            "Return exactly one runnable ```python ... ``` block. "
            "Do not include Thought, explanation, or hidden reasoning.\n"
        )

    @staticmethod
    def _compact_text_for_prompt(text: str, max_chars: int = 1200) -> str:
        """Keep repair prompts within small local-model context windows."""
        cleaned = re.sub(r"<think>.*?</think>", "", text or "", flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r"</?think>", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+\n", "\n", cleaned).strip()
        if len(cleaned) <= max_chars:
            return cleaned
        head = cleaned[: max_chars // 2].rstrip()
        tail = cleaned[-max_chars // 2 :].lstrip()
        return f"{head}\n...[truncated for context budget]...\n{tail}"

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
            user_content = (
                "OFFLINE_EXECUTION_START:\n"
                f"{self._offline_no_think_prefix()}"
                "Return ONE short complete ```python ... ``` block only.\n"
                "Skip the Thought section unless it is one short line and the code block follows immediately.\n"
                "Keep code under 60 lines.\n"
                "Start from runtime inputs only: `tables = load_all_tables()`.\n"
                "For multi-file tasks, select tables by verified headers, not filenames or file order.\n"
                "If uncertain, print columns first and branch from observed headers.\n"
                "Save with `save_workbook_to(output_path)`.\n\n"
                f"User Question:\n{user_question}\n\n"
            )
        else:
            user_content = self.prompt_builder.build_execution_user_prompt(
                self.excel_context_execution,
                understanding_output,
                user_question,
            )
        user_content = self.skill_prompt.augment_initial_prompt(user_content, user_question)
        return {"role": "user", "content": user_content}

    def _create_llm_recovery_prompt(self, user_question: str) -> dict:
        schema_snapshot = self._build_schema_snapshot()
        user_content = (
            "LLM_CONNECTION_RECOVERY: the previous response could not be generated.\n"
            f"{self._offline_no_think_prefix()}"
            "Return ONE short complete ```python ... ``` block only.\n"
            "Do not spend tokens on a standalone Thought section.\n"
            "Keep code under 60 lines.\n"
            "Start from runtime inputs only: `tables = load_all_tables()`.\n"
            "Print file names / headers before selecting or joining tables.\n"
            "Save with `save_workbook_to(output_path)`.\n\n"
            f"User Question:\n{user_question}\n"
        )
        if schema_snapshot:
            schema_snapshot = self._compact_text_for_prompt(schema_snapshot, max_chars=1200)
            user_content += (
                f"\nRuntime schema snapshot:\n{schema_snapshot}\n"
                "Use these exact files and headers.\n"
            )
        user_content = self.skill_prompt.augment_initial_prompt(user_content, user_question)
        return {"role": "user", "content": user_content}

    def _attempt_plan_to_code_recovery(
        self,
        thought: str,
        user_question: str,
    ) -> tuple[Optional[dict], Optional[str]]:
        if not self._is_offline_strict:
            return None, None
        plan_text = (thought or "").strip()
        if not plan_text:
            return None, None

        task_loop_breaker = get_task_specific_loop_breaker(user_question)
        schema_snapshot = self._compact_text_for_prompt(
            self._build_schema_snapshot(),
            max_chars=1200,
        )
        plan_text = self._compact_text_for_prompt(plan_text, max_chars=900)
        user_content = (
            "PLAN_TO_CODE_RECOVERY: your previous reply explained the solution but did not include executable code.\n"
            f"{self._offline_no_think_prefix()}"
            "Convert the plan below into exactly one runnable ```python ... ``` block.\n"
            "Start the very first line with ```python.\n"
            "Do not include Thought, explanation, or markdown outside the code block.\n"
            "Use only runtime helpers that are already allowed in this task.\n\n"
            f"User Question:\n{user_question}\n\n"
            f"Plan To Convert:\n{plan_text}\n"
        )
        if schema_snapshot:
            user_content += f"\nRuntime schema snapshot:\n{schema_snapshot}\n"
        if task_loop_breaker:
            user_content += f"\n{task_loop_breaker.strip()}\n"

        recovery_messages = [self._get_system_prompt(), {"role": "user", "content": user_content}]
        try:
            recovery_message = self.llm_client.get_response(
                recovery_messages,
                max_retries=1,
                max_tokens=self._llm_recovery_max_tokens,
            )
        except Exception:
            return None, None

        _recovery_thought, recovery_code = self.parser.parse(recovery_message.content)
        return recovery_message, recovery_code

    def _available_workbook_basenames(self) -> list[str]:
        return self.grounding.available_workbook_basenames()

    def _build_schema_snapshot(self) -> str:
        snapshot = self.grounding.build_schema_snapshot()
        if not self._is_offline_strict:
            return snapshot

        available_basenames = self._available_workbook_basenames()
        relevant = self._extract_relevant_basenames(
            self._active_understanding_output,
            available_basenames,
        )
        if not relevant:
            return snapshot

        filtered_lines = [
            line for line in snapshot.splitlines()
            if any(f"`{basename}`" in line for basename in relevant)
        ]
        if len(available_basenames) <= 5 and len(filtered_lines) < len(available_basenames):
            return snapshot
        return "\n".join(filtered_lines) if filtered_lines else snapshot

    @staticmethod
    def _extract_relevant_basenames(text: str, available_basenames: list[str]) -> list[str]:
        source_text = text or ""
        lines = [line.strip() for line in source_text.splitlines() if line.strip()]
        priority_markers = ("read", "schema", "join", "key header", "computation")
        priority_lines = [
            line for line in lines
            if any(marker in line.lower() for marker in priority_markers)
        ]

        def _collect(matches_from: list[str]) -> list[str]:
            collected: list[str] = []
            lowered_lines = "\n".join(matches_from).lower()
            for basename in available_basenames:
                if basename and basename.lower() in lowered_lines:
                    collected.append(basename)
            return collected

        prioritized = _collect(priority_lines)
        if prioritized:
            return prioritized
        return _collect(lines)

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
    def _preflight_signature(preflight_issue: str) -> str:
        first_line = (preflight_issue or "").strip().splitlines()[0] if preflight_issue else ""
        return first_line.strip().lower() or "unknown_preflight"

    def _update_preflight_streak(self, preflight_issue: str) -> str:
        signature = self._preflight_signature(preflight_issue)
        if signature == self._last_preflight_signature:
            self._same_preflight_streak += 1
        else:
            self._last_preflight_signature = signature
            self._same_preflight_streak = 1
        return signature

    @staticmethod
    def _build_preflight_loop_breaker_feedback(preflight_issue: str) -> str:
        signature = ExecutionRuntime._preflight_signature(preflight_issue)
        if signature.startswith("preflight_schema_merge_summary"):
            return (
                "REPEATED_PREFLIGHT_LOOP_BREAKER:\n"
                "- Rebuild from this exact helper-contract shape.\n"
                "- Keep these exact variable names and result keys:\n"
                "  `tables = load_all_tables()`\n"
                "  `concat_result = concat_tables_with_same_headers(tables)`\n"
                "  `combined_df = concat_result['output_df']`\n"
                "  `combined_df['Date'] = pd.to_datetime(combined_df['Date'], errors='coerce')`\n"
                "  `summary_df = combined_df[combined_df['Date'].dt.month == 11]`\n"
                "  `summary_result = summarize_numeric_column(summary_df, value_col='Daily Spending (£)')`\n"
                "  `create_output_sheet('Output')`\n"
                "  `write_dataframe_to_sheet(summary_df, 'Output', 'A1')`\n"
                "  `summary_row = len(summary_df) + 2`\n"
                "  `add_summary_row('Output', summary_row, summary_result['summary'])`\n"
                "  `row_numbers = summary_result['output_row_numbers']`\n"
                "  `highlight_rows('Output', row_numbers, {'fill_color': 'red'})`\n"
                "  `saved_file = save_workbook_to(output_path)`\n"
                "  `print(f'SAVED_FILE: {saved_file}')`\n"
                "  `saved_file`\n"
                "- Do NOT use `summary_result['row']`, `summary_result['total']`, or `summary_result['average']`.\n"
                "- Return one complete code block matching this contract."
            )
        return (
            "REPEATED_PREFLIGHT_LOOP_BREAKER:\n"
            "- The same preflight issue repeated.\n"
            "- Rewrite the code from the helper contract shown in the preflight message.\n"
            "- Keep exact documented result keys and remove any invented keys or helper return fields."
        )

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

    @staticmethod
    def _is_repair_feedback_content(content: str) -> bool:
        return any(marker in content for marker in _REPAIR_FEEDBACK_MARKERS)

    def _should_use_compact_repair_budget(self) -> bool:
        if not self._is_offline_strict or len(self.conversation_history) < 3:
            return False
        last_message = self.conversation_history[-1]
        return (
            self._message_role(last_message) == "user"
            and self._is_repair_feedback_content(self._message_content(last_message))
        )

    def _prune_repair_feedback_history(self) -> None:
        matched_indices = [
            idx for idx, msg in enumerate(self.conversation_history)
            if self._message_role(msg) == "user"
            and self._is_repair_feedback_content(self._message_content(msg))
        ]
        if not matched_indices:
            return
        keep_idx = matched_indices[-1]
        if self._is_offline_strict:
            self.conversation_history = (
                self.conversation_history[:2] + [self.conversation_history[keep_idx]]
            )
            return
        if len(matched_indices) <= 1:
            return
        self.conversation_history = [
            msg for idx, msg in enumerate(self.conversation_history)
            if idx == keep_idx or idx not in matched_indices[:-1]
        ]
        self._prune_old_execution_rounds()

    def _prune_old_execution_rounds(self, keep_rounds: int = 2) -> None:
        """Drop old code+result pairs when history grows large.

        Keeps the system prompt, the initial user prompt, and the last
        *keep_rounds* assistant/user pairs from execution so the total
        context stays within the offline model's context window.
        """
        # History layout: [system, initial_user, asst1, usr1, asst2, usr2, ...]
        # Index 0 = system, index 1 = initial user prompt — always preserved.
        if len(self.conversation_history) <= 2 + keep_rounds * 2:
            return
        preserved = self.conversation_history[:2]
        tail = self.conversation_history[2:]
        # Keep only the last keep_rounds * 2 messages (assistant + user pairs).
        self.conversation_history = preserved + tail[-(keep_rounds * 2):]

    def run(self, understanding_output: str, user_question: str,
            max_turns: int = 20) -> Dict[str, Any]:
        logger.info(f"Starting multi-turn analysis for: '{user_question}'")
        self._install_linear_io_guards()
        self._last_error_signature = None
        self._same_error_streak = 0
        self._last_preflight_signature = None
        self._same_preflight_streak = 0
        self._llm_error_streak = 0
        self._active_understanding_output = understanding_output or ""
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
                if turn == 0 and self._is_offline_strict:
                    max_tokens = min(max_tokens, self._initial_exec_max_tokens)
                elif self._should_use_compact_repair_budget():
                    max_tokens = min(max_tokens, self._llm_recovery_max_tokens)
                if self._llm_error_streak > 0:
                    max_tokens = min(max_tokens, self._llm_recovery_max_tokens)
                response_message = self.llm_client.get_response(
                    self.conversation_history,
                    max_tokens=max_tokens,
                )
                self._llm_error_streak = 0
                self.conversation_history.append(_assistant_message_to_dict(response_message))

                thought, code_action = self.parser.parse(response_message.content)

                if thought:
                    self._log_to_file(
                        f"\n**Thought (Turn {turn + 1}):**\n{thought}\n"
                    )

                if code_action is None:
                    recovery_message = None
                    if thought:
                        recovery_message, recovered_code = self._attempt_plan_to_code_recovery(
                            thought,
                            user_question,
                        )
                        if recovered_code is not None:
                            self.conversation_history[-1] = _assistant_message_to_dict(recovery_message)
                            code_action = recovered_code
                            self._log_to_file(
                                f"\n**Plan-to-code recovery (Turn {turn + 1}):** converted thought-only reply into executable code.\n"
                            )

                if code_action is None:
                    self._consecutive_format_errors += 1
                    raw_preview = (response_message.content or "").strip()
                    schema_snapshot = self._build_schema_snapshot()
                    if raw_preview:
                        preview = raw_preview[:1600]
                        self._log_to_file(
                            f"\n**Raw reply preview (Turn {turn + 1}):**\n```\n{preview}\n```\n"
                        )
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
                    if self._is_text_output_skill(user_question):
                        execution_shape = (
                            "Include complete task logic: read -> compute -> print `FINAL_TEXT:` -> return the final text."
                        )
                    else:
                        execution_shape = (
                            "Include complete task logic: read -> compute -> write Output -> save_workbook_to(output_path)."
                        )
                    format_msg = (
                        "FORMAT_ERROR_EXECUTION: executable code is required.\n"
                        f"{self._offline_no_think_prefix() if self._is_offline_strict else ''}"
                        "Reply with exactly one ```python ... ``` block.\n"
                        "Start the very first line with ```python.\n"
                        "Any Thought, explanation, or planning text will be discarded.\n"
                        "Do not return a standalone Thought section.\n"
                        f"{execution_shape}"
                        f"{strict_repair}"
                    )
                    if schema_snapshot:
                        if self._is_offline_strict:
                            schema_snapshot = self._compact_text_for_prompt(
                                schema_snapshot,
                                max_chars=1200,
                            )
                        format_msg += f"\nRuntime schema snapshot:\n{schema_snapshot}\nUse these exact files and headers.\n"
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
                preflight_issue = self.generic_preflight.offline_preflight_check(code_action, user_question)
                if preflight_issue is None:
                    preflight_issue = self.skill_preflight.metadata_routed_preflight_check(
                        code_action,
                        user_question,
                    )
                if preflight_issue is not None:
                    self._last_error_signature = None
                    self._same_error_streak = 0
                    self._update_preflight_streak(preflight_issue)
                    preflight_feedback = (
                        preflight_issue
                        + "\nReturn one full corrected ```python ... ``` block. "
                        "Keep minimal edits and preserve task logic."
                    )
                    if self._is_offline_strict:
                        preflight_feedback = self._offline_no_think_prefix() + preflight_feedback
                    task_loop_breaker = get_task_specific_loop_breaker(user_question)
                    if task_loop_breaker and (turn >= 1 or self._same_preflight_streak >= self._max_same_preflight_streak):
                        preflight_feedback += task_loop_breaker
                    if self._same_preflight_streak >= self._max_same_preflight_streak:
                        preflight_feedback = (
                            self._build_preflight_loop_breaker_feedback(preflight_issue)
                            + "\n\n"
                            + preflight_feedback
                        )
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
                        self._last_preflight_signature = None
                        self._same_preflight_streak = 0
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
                    self._last_preflight_signature = None
                    self._same_preflight_streak = 0

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
                        self._is_text_output_skill(user_question)
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
                    self._last_preflight_signature = None
                    self._same_preflight_streak = 0
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
                self._llm_error_streak += 1
                logger.error(f"LLM Error: {str(e)}")
                self._log_to_file(
                    f"\n**LLM error (Turn {turn + 1}):**\n{str(e)}\n"
                )
                if self._llm_error_streak <= self._max_llm_error_retries:
                    self.conversation_history = [
                        self._get_system_prompt(),
                        self._create_llm_recovery_prompt(user_question),
                    ]
                    continue
                fallback_result = self._try_timeout_helper_fallback(
                    user_question,
                    output_contract,
                    execution_steps,
                    turn,
                )
                if fallback_result is not None:
                    return fallback_result
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
