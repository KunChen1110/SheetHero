"""Validation stage facade for final QA."""

from typing import Any, Dict

from ..base.stage import Stage
from .runtime import ValidationRuntime


class ValidationStage(Stage):
    """Facade for validation runtime."""

    def __init__(self, client, deployment: str, excel_context_understanding: str,
                 progress_log_file=None, prompt_profile: str = "online_rich"):
        self.runner = ValidationRuntime(
            client,
            deployment,
            excel_context_understanding,
            progress_log_file=progress_log_file,
            prompt_profile=prompt_profile,
        )

    def run(self, execution_result: Dict[str, Any], user_question: str,
            understanding_output: str) -> Dict[str, Any]:
        return self.runner.run(execution_result, user_question, understanding_output)
