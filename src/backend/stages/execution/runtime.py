"""Execution runtime loop for multi-turn analysis."""

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
                 use_bounded_execution: bool = False):
        super().__init__(progress_log_file)
        self.client = client
        self.deployment = deployment
        self.sandbox = sandbox
        self.excel_context_execution = excel_context_execution
        self.output_instruction = output_instruction or ""
        self.use_bounded_execution = use_bounded_execution

        self.llm_client = ExecutionLLMClient(client, deployment)
        self.parser = ExecutionResponseParser()
        self.executor = CodeExecutor(sandbox)
        self.history_formatter = ExecutionHistory()
        self.summary_builder = ExecutionSummary()

        self.conversation_history = []
        self._consecutive_forbidden = 0

    def _get_system_prompt(self) -> dict:
        system_content = PromptBuilder().build_execution_system_prompt(
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

    def _create_initial_user_prompt(self, understanding_output: str,
                                    user_question: str) -> dict:
        user_content = PromptBuilder().build_execution_user_prompt(
            self.excel_context_execution,
            understanding_output,
            user_question
        )
        return {"role": "user", "content": user_content}

    @staticmethod
    def _build_bounded_error_feedback(execution_result: str) -> Optional[str]:
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
                return (
                    "MINIMAL FIX REQUIRED: do not use unstable path-key dict lookup across turns.\n"
                    "- Avoid reading DataFrame from cached dict keys by absolute file path.\n"
                    "- Rebuild DataFrames in the same turn from all_files using inspector_multi(file_path, range_ref, sheet_name).\n"
                    "- Define all variables in this turn; do not rely on previous turn state."
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
            return (
                "MINIMAL FIX REQUIRED: undefined variable/function.\n"
                f"- Undefined name: '{missing_name}'\n"
                "- Define all variables in this turn before use.\n"
                "- Use all_files[0], all_files[1] directly for file paths; do not use placeholder names unless defined."
            )

        if "No module named 'common_functions'" in execution_result:
            return (
                "MINIMAL FIX REQUIRED: remove external helper imports.\n"
                "- Do NOT import common_functions.\n"
                "- Use runtime-injected helpers directly: list_all_workbooks, inspector_multi, create_output_sheet, write_dataframe_to_sheet, save_workbook_to."
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

        return None

    def run(self, understanding_output: str, user_question: str,
            max_turns: int = 20) -> Dict[str, Any]:
        logger.info(f"Starting multi-turn analysis for: '{user_question}'")
        self._consecutive_forbidden = 0

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
                max_tokens = 2048 if self.use_bounded_execution else None
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
                        format_msg = (
                            "FORMAT_ERROR_OFFLINE: executable code is required.\n"
                            "Reply with exactly one ```python ... ``` block.\n"
                            "Include complete task logic: read -> compute -> write Output -> save_workbook_to(output_path)."
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
                        if self._consecutive_forbidden >= 3:
                            hard_reset = (
                                "\nHARD RESET TEMPLATE (use this structure, no extra imports):\n"
                                "```python\n"
                                "import pandas as pd\n"
                                "all_files = list_all_workbooks()\n"
                                "data1 = inspector_multi(all_files[0], \"A1:D40\", \"Sheet1\")\n"
                                "data2 = inspector_multi(all_files[1], \"A1:D40\", \"Sheet1\")\n"
                                "df1 = pd.DataFrame(data1[1:], columns=data1[0])\n"
                                "df2 = pd.DataFrame(data2[1:], columns=data2[0])\n"
                                "df = pd.concat([df1, df2], ignore_index=True)\n"
                                "print(\"Columns:\", df.columns.tolist())\n"
                                "# compute metric here using real column names from printed columns\n"
                                "create_output_sheet(\"Output\")\n"
                                "out = [[\"Metric\", \"Value\"]]\n"
                                "write_dataframe_to_sheet(out, \"Output\", \"A1\")\n"
                                "saved_file = save_workbook_to(output_path)\n"
                                "print(\"SAVED_FILE:\", saved_file)\n"
                                "saved_file\n"
                                "```\n"
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
                        targeted_feedback = self._build_bounded_error_feedback(execution_result)
                        if targeted_feedback is None:
                            targeted_feedback = (
                                "MINIMAL FIX REQUIRED: Fix only the smallest necessary part "
                                "(variable/column/type/range/signature). Do not add new helpers, new paths, or refactor unrelated code."
                            )
                        feedback_to_model = targeted_feedback + "\n\n" + execution_result
                        self.conversation_history.append({"role": "user", "content": feedback_to_model})
                        continue

                    # Auto-stop when we see a successful save in stdout (avoids Turn2+ repeat path)
                    saved_path = self._extract_saved_path_from_result(execution_result)
                    if saved_path is not None:
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
                        targeted_feedback = self._build_bounded_error_feedback(error_message)
                        if targeted_feedback is not None:
                            feedback_to_model = targeted_feedback + "\n\n" + error_message
                        else:
                            feedback_to_model = (
                                "MINIMAL FIX REQUIRED: Fix only the smallest necessary part "
                                "(variable/column/type/range). Do not add new code or invented paths.\n\n"
                                + error_message
                            )

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
