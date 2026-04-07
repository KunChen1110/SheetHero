"""Execution runtime loop for multi-turn analysis."""

import os
import re
from typing import Dict, Any, Optional

from ...log.logger_registry import LoggerRegistry
from ...task_skills import detect_skill
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
from .family import (
    ExecutionFamilyFastPathRunner,
    ExecutionGenericPreflightAdvisor,
    ExecutionFamilyPreflightAdvisor,
    ExecutionFamilyPromptAdvisor,
    ExecutionQuestionInferenceAdvisor,
)
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
        self.family_fast_path_runner = ExecutionFamilyFastPathRunner(self)
        self.generic_preflight = ExecutionGenericPreflightAdvisor(self)
        self.family_preflight = ExecutionFamilyPreflightAdvisor(self)
        self.family_prompt = ExecutionFamilyPromptAdvisor(self)
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

    @staticmethod
    def _is_text_output_skill(user_question: str) -> bool:
        skill = detect_skill(user_question)
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

    def _regression_helper_guard(self, code_action: str, user_question: str) -> Optional[str]:
        return self.family_preflight.regression_helper_guard(code_action, user_question)

    def _merge_fill_helper_guard(self, code_action: str, user_question: str) -> Optional[str]:
        return self.family_preflight.merge_fill_helper_guard(code_action, user_question)

    def _regression_feature_guard(self, code_action: str, user_question: str) -> Optional[str]:
        return self.family_preflight.regression_feature_guard(code_action, user_question)

    def _scheduling_dependency_guard(self, code_action: str, user_question: str) -> Optional[str]:
        return self.family_preflight.scheduling_dependency_guard(code_action, user_question)

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
        user_content = self.family_prompt.augment_initial_prompt(user_content, user_question)
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
        self._last_error_signature = None
        self._same_error_streak = 0
        output_contract = self._extract_output_contract(understanding_output)

        deterministic_family_result = self.family_fast_path_runner.try_run(user_question)
        if deterministic_family_result is not None:
            family_name = deterministic_family_result.get("_family_fast_path", "unknown_family")
            self._log_to_file(
                "\n**Deterministic Family Fast-Path:**\n"
                f"- family: `{family_name}`\n"
                f"- answer: `{deterministic_family_result.get('answer', '')}`\n"
            )
            logger.info("Execution completed via deterministic family fast-path: %s", family_name)
            return deterministic_family_result

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
                preflight_issue = self.generic_preflight.offline_preflight_check(code_action, user_question)
                if preflight_issue is None:
                    preflight_issue = self._merge_fill_helper_guard(code_action, user_question)
                if preflight_issue is None:
                    preflight_issue = self._regression_helper_guard(code_action, user_question)
                if preflight_issue is None:
                    preflight_issue = self._regression_feature_guard(code_action, user_question)
                if preflight_issue is None:
                    preflight_issue = self.family_preflight.scheduling_dependency_guard(code_action, user_question)
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
