"""Execution runtime loop for multi-turn analysis."""

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
                 output_instruction: Optional[str] = None, progress_log_file=None):
        super().__init__(progress_log_file)
        self.client = client
        self.deployment = deployment
        self.sandbox = sandbox
        self.output_instruction = output_instruction or ""

        self.llm_client = ExecutionLLMClient(client, deployment)
        self.parser = ExecutionResponseParser()
        self.executor = CodeExecutor(sandbox)
        self.history_formatter = ExecutionHistory()
        self.summary_builder = ExecutionSummary()

        self.conversation_history = []

    def _get_system_prompt(self) -> dict:
        system_content = PromptBuilder().build_execution_system_prompt(
            self.output_instruction
        )
        return {"role": "system", "content": system_content}

    @staticmethod
    def _truncate(value: str, limit: int = 300) -> str:
        if value is None:
            return ""
        text = str(value)
        if len(text) <= limit:
            return text
        return text[:limit] + "..."

    def _create_initial_user_prompt(self, execution_context: str,
                                    user_query: str,
                                    understanding_output: str) -> dict:
        user_content = PromptBuilder().build_execution_user_prompt(
            execution_context,
            user_query,
            understanding_output
        )
        return {"role": "user", "content": user_content}

    def run(self, user_query: str, execution_context: str,
            understanding_output: str,
            max_turns: int = 20) -> Dict[str, Any]:
        self._log_to_file(
            f"[EXECUTION] user_query={self._truncate(user_query)} "
            f"context_len={len(execution_context)}"
        )
        self._log_to_file(
            f"[EXECUTION] understanding_output={self._truncate(understanding_output)}"
        )

        self.conversation_history = [self._get_system_prompt()]
        initial_prompt = self._create_initial_user_prompt(
            execution_context,
            user_query,
            understanding_output
        )
        self.conversation_history.append(initial_prompt)

        execution_steps = []

        for turn in range(max_turns):
            logger.info(f"Execution turn {turn + 1}")
            self._log_to_file(f"\n---\n\n### Execution Turn {turn + 1}\n")

            try:
                response_message = self.llm_client.get_response(self.conversation_history)
                self.conversation_history.append(response_message)

                thought, code_action = self.parser.parse(response_message.content)

                if thought:
                    self._log_to_file(
                        f"\n**Thought (Turn {turn + 1}):**\n{thought}\n"
                    )

                if code_action is None:
                    final_answer = self.parser.extract_final_answer(response_message.content)
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

                    logger.warning("No valid action found, asking for clarification")
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

                    execution_steps.append({
                        "turn": turn + 1,
                        "code": code_action,
                        "result": execution_result,
                        "success": True
                    })

                    self.conversation_history.append({"role": "user", "content": observation})

                except Exception as e:
                    error_message = f"Code execution error: {str(e)}"
                    logger.error(f"Execution error: {error_message}")

                    self._log_to_file(
                        f"\n**Execution error (Turn {turn + 1}):**\n```\n{error_message}\n```\n"
                    )

                    execution_steps.append({
                        "turn": turn + 1,
                        "code": code_action,
                        "result": error_message,
                        "success": False
                    })

                    self.conversation_history.append({
                        "role": "user",
                        "content": "The previous code failed. Try a different approach.\n" + error_message
                    })

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
