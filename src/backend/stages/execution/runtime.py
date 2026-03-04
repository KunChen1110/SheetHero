"""Execution runtime loop for multi-turn analysis."""

import os
import re
from typing import Dict, Any, Optional

from ...log.logger_registry import LoggerRegistry
from .executor import CodeExecutor
from .error_feedback import ExecutionErrorFeedbackBuilder
from .forbidden_policy import (
    build_forbidden_memory_block,
    build_forbidden_repair_hint,
    forbidden_signature,
    is_immediate_hard_forbidden,
)
from .history import ExecutionHistory
from .llm_client import ExecutionLLMClient
from .output_contract import OutputContractChecker
from .parser import ExecutionResponseParser
from .summary import ExecutionSummary
from .workbook_grounding import WorkbookGrounding
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
            "- For each file: wb = get_workbook(file_path); sheet_name = wb.sheetnames[0]; "
            "raw = inspector_multi(file_path, \"A1:Z200\", sheet_name).\n"
            "- Build DataFrame with explicit header handling: pd.DataFrame(raw[1:], columns=raw[0]).\n"
            "- Then run task-specific computation, write Output via write_dataframe_to_sheet, "
            "and save with save_workbook_to(output_path).\n"
            "- Do not use placeholder outputs; write real result rows."
        )

    def _handle_offline_forbidden(
        self,
        code_action: str,
        turn: int,
    ) -> tuple[bool, str]:
        """Handle bounded forbidden/grounding checks. Return (should_continue, soft_warning)."""
        if not self._is_offline_strict:
            return False, ""

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
                        "Allowed I/O helpers only: list_all_workbooks(), get_workbook(), inspector_multi(), "
                        "create_output_sheet(), write_dataframe_to_sheet(), save_workbook_to(output_path).\n"
                        f"{repair_hint}"
                        f"{hard_reset}"
                        f"{forbidden_memory}"
                        "Output a single ```python ... ``` block with the corrected full code."
                    )
                })
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
            return True, ""

        return False, soft_warning

    def _offline_preflight_check(self, code_action: str) -> Optional[str]:
        """Reject obviously drifting offline code before sandbox execution."""
        if not self._is_offline_strict:
            return None
        code = (code_action or "").strip()
        if not code:
            return "PREFLIGHT_OFFLINE: empty code block."
        lower = code.lower()
        if "list_all_workbooks(" not in lower:
            return (
                "PREFLIGHT_OFFLINE: code must read runtime inputs via list_all_workbooks().\n"
                "- Add: all_files = list_all_workbooks()\n"
                "- Resolve file_path from all_files or file_by_name mapping."
            )
        if not re.search(r"save_workbook_to\s*\(\s*output_path\s*\)", code, flags=re.IGNORECASE):
            return (
                "PREFLIGHT_OFFLINE: code must save with save_workbook_to(output_path).\n"
                "- End with:\n"
                "  saved_file = save_workbook_to(output_path)\n"
                "  print(\"SAVED_FILE:\", saved_file)\n"
                "  saved_file"
            )
        if "inspector_multi(" not in lower:
            return (
                "PREFLIGHT_OFFLINE: code must read sheet content via inspector_multi(...).\n"
                "- Use: raw = inspector_multi(file_path, \"A1:Z200\", sheet_name)"
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
        if self._is_offline_strict:
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

    def run(self, understanding_output: str, user_question: str,
            max_turns: int = 20) -> Dict[str, Any]:
        logger.info(f"Starting multi-turn analysis for: '{user_question}'")
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
                        if self._is_offline_strict:
                            strict_repair = (
                                "\nTRUNCATION/FORMAT RECOVERY (MANDATORY):\n"
                                "- Return ONLY one complete code block.\n"
                                "- Keep code under 120 lines and avoid long comments.\n"
                                "- Ensure closing triple backticks are present.\n"
                                "- Use list_all_workbooks()+inspector_multi(); do not use pandas file readers.\n"
                            )
                        else:
                            strict_repair = (
                                "\nTRUNCATION/FORMAT RECOVERY (MANDATORY):\n"
                                "- Return ONLY one complete code block.\n"
                                "- Keep code under 120 lines and avoid long comments.\n"
                                "- Ensure closing triple backticks are present.\n"
                            )
                    if self._is_offline_strict:
                        format_msg = (
                            "FORMAT_ERROR_OFFLINE: executable code is required.\n"
                            "Reply with exactly one ```python ... ``` block.\n"
                            "Include complete task logic: read -> compute -> write Output -> save_workbook_to(output_path)."
                            f"{strict_repair}"
                        )
                    else:
                        format_msg = (
                            "FORMAT_ERROR: executable code is required.\n"
                            "Reply with exactly one ```python ... ``` block.\n"
                            "Include complete task logic for this question and provide a final saved output file."
                            f"{strict_repair}"
                        )
                    logger.warning("No code block returned; executable code required")
                    self._log_to_file(f"\n**Format error (Turn {turn + 1}):** no code block.\n")
                    self.conversation_history.append({"role": "user", "content": format_msg})
                    continue
                self._consecutive_format_errors = 0

                should_continue, soft_forbidden_warning = self._handle_offline_forbidden(
                    code_action,
                    turn,
                )
                if should_continue:
                    continue
                preflight_issue = self._offline_preflight_check(code_action)
                if preflight_issue is not None:
                    self._log_to_file(
                        f"\n**Preflight blocked (Turn {turn + 1}):**\n{preflight_issue}\n"
                    )
                    self.conversation_history.append({
                        "role": "user",
                        "content": (
                            preflight_issue
                            + "\nReturn one full corrected ```python ... ``` block. "
                            "Keep minimal edits and preserve task logic."
                        )
                    })
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
                        if soft_forbidden_warning:
                            feedback_to_model = soft_forbidden_warning + "\n\n" + feedback_to_model
                        self.conversation_history.append({"role": "user", "content": feedback_to_model})
                        if (
                            self._is_offline_strict
                            and self._same_error_streak >= self._max_same_error_before_abort
                        ):
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
                                    "OUTPUT_INCOMPLETE_OFFLINE: saved file detected, but Output sheet appears to contain only header/placeholder rows.\n"
                                    "You MUST write a real result table (header + data rows) before saving.\n"
                                    "Do not use placeholder `[['Metric','Value']]`.\n"
                                    "Re-run full logic using list_all_workbooks() + inspector_multi(), then write complete table to Output and save_workbook_to(output_path)."
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
                            continue
                        quality_risk_feedback = self.output_contract_checker.detect_quality_risk(
                            execution_result
                        )
                        if quality_risk_feedback is not None:
                            self.conversation_history.append({
                                "role": "user",
                                "content": quality_risk_feedback
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
                    if soft_forbidden_warning:
                        feedback_to_model = soft_forbidden_warning + "\n\n" + feedback_to_model

                    execution_steps.append({
                        "turn": turn + 1,
                        "code": code_action,
                        "result": error_message,
                        "success": False
                    })

                    self.conversation_history.append({"role": "user", "content": feedback_to_model})
                    if (
                        self._is_offline_strict
                        and self._same_error_streak >= self._max_same_error_before_abort
                    ):
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
