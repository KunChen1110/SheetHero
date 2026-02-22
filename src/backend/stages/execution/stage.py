"""Execution stage facade for multi-turn analysis."""

from typing import Any, Dict, Optional

from ..base.stage import Stage
from .runtime import ExecutionRuntime


class ExecutionStage(Stage):
    """
    Facade for multi-turn execution with code generation and execution.
    """

    def __init__(self, client, deployment: str, sandbox,
                 excel_context_execution: str,
                 output_instruction: Optional[str] = None, progress_log_file=None,
                 prompt_profile: str = "offline_strict"):
        self.runner = ExecutionRuntime(
            client,
            deployment,
            sandbox,
            excel_context_execution,
            output_instruction=output_instruction,
            progress_log_file=progress_log_file,
            prompt_profile=prompt_profile,
        )

    def run(self, understanding_output: str, user_question: str,
            max_turns: int = 20) -> Dict[str, Any]:
        return self.runner.run(understanding_output, user_question, max_turns=max_turns)
