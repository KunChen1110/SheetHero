"""Execution stage facade for multi-turn analysis."""

from typing import Any, Dict, Optional

from ..base.stage import Stage
from .runtime import ExecutionRuntime


class ExecutionStage(Stage):
    """
    Facade for multi-turn execution with code generation and execution.
    """

    def __init__(self, client, deployment: str, sandbox,
                 output_instruction: Optional[str] = None, progress_log_file=None):
        self.runner = ExecutionRuntime(
            client,
            deployment,
            sandbox,
            output_instruction=output_instruction,
            progress_log_file=progress_log_file
        )

    def run(self, user_query: str, execution_context: str,
            understanding_output: str,
            max_turns: int = 20) -> Dict[str, Any]:
        return self.runner.run(user_query, execution_context, understanding_output, max_turns=max_turns)
