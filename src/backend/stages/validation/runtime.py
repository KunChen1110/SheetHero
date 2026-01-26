"""Validation runtime for execution results."""

from typing import Any, Dict

from ...log.logger_registry import LoggerRegistry
from ..base.runtime import StageRuntime
from ...prompt.prompt_builder import PromptBuilder
from .history import ValidationHistory
from .llm_client import ValidationLLMClient
from .parser import ValidationResponseParser

logger = LoggerRegistry.setup_logger(__name__)


class ValidationRuntime(StageRuntime):
    """Runs validation steps to assess execution results."""

    def __init__(self, client, deployment: str, excel_context_understanding: str,
                 progress_log_file=None):
        super().__init__(progress_log_file)
        self.excel_context_understanding = excel_context_understanding
        self.history_formatter = ValidationHistory()
        self.llm_client = ValidationLLMClient(client, deployment)
        self.parser = ValidationResponseParser()

    def run(self, execution_result: Dict[str, Any], user_question: str,
            understanding_output: str) -> Dict[str, Any]:
        logger.info("Starting validation on execution results")

        conversation_history = execution_result.get("conversation_history", [])
        conversation_history_text = self.history_formatter.format(conversation_history)

        prompt_text = PromptBuilder().build_validation_prompt(
            user_question=user_question,
            excel_context_understanding=self.excel_context_understanding,
            execution_success=execution_result.get("success", False),
            total_turns=execution_result.get("total_turns", 0),
            final_answer=execution_result.get("answer", "No answer provided"),
            execution_summary=execution_result.get("execution_summary", {}),
            conversation_history_text=conversation_history_text
        )
        messages = [{"role": "user", "content": prompt_text}]

        try:
            validation_analysis = self.llm_client.get_response(messages)
            self._log_to_file(
                f"\n**Validation Analysis:**\n```\n{validation_analysis}\n```\n"
            )

            validation_result = self.parser.parse(validation_analysis)

            logger.info(
                f"Validation completed. Confidence: {validation_result['confidence_score']:.2f}"
            )
            logger.info(
                f"Validation: {'PASSED' if validation_result['validation_passed'] else 'FAILED'}"
            )

            if validation_result['validation_passed']:
                logger.info("Answer validated - ready for final output")
                validation_result['verified_answer'] = execution_result.get("answer", "")
                validation_result['requires_reexecution'] = False
            else:
                logger.warning("Issues found - recommending re-execution")
                validation_result['requires_reexecution'] = True

            return validation_result

        except Exception as e:
            logger.error(f"Error during validation: {str(e)}")
            return {
                "validation_passed": False,
                "confidence_score": 0.0,
                "issues_found": [f"Validation process failed: {str(e)}"],
                "improvement_feedback": (
                    "Unable to provide feedback due to validation error. "
                    "Please review the execution manually."
                ),
                "final_assessment": "Unable to validate due to validation error",
                "verified_answer": "",
                "requires_reexecution": False
            }
