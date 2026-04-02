"""Validation runtime for execution results."""

import os
from typing import Any, Dict

from ...log.logger_registry import LoggerRegistry
from ...task_families import detect_task_family, get_task_family_validation_mode
from ..base.runtime import StageRuntime
from ...prompt.prompt_builder import PromptBuilder
from .core.history import ValidationHistory
from .core.llm_client import ValidationLLMClient
from .core.parser import ValidationResponseParser
from .checks.deterministic_path import ValidationDeterministicAdvisor
from .checks.rule_checks import ValidationRuleCheckAdvisor
from .checks.schedule_checks import ScheduleValidationInspectorMixin
from .inspectors.signals import ValidationSignalParserMixin
from .inspectors.text_preview import TextPreviewValidationInspectorMixin
from .inspectors.workbook import WorkbookValidationInspectorMixin

logger = LoggerRegistry.setup_logger(__name__)


class ValidationRuntime(
    WorkbookValidationInspectorMixin,
    TextPreviewValidationInspectorMixin,
    ValidationSignalParserMixin,
    ScheduleValidationInspectorMixin,
    StageRuntime,
):
    """Runs validation steps to assess execution results."""

    def __init__(self, client, deployment: str, excel_context_understanding: str,
                 progress_log_file=None, prompt_profile: str = "online_rich"):
        super().__init__(progress_log_file)
        self.excel_context_understanding = excel_context_understanding
        self.history_formatter = ValidationHistory()
        self.llm_client = ValidationLLMClient(client, deployment)
        self.parser = ValidationResponseParser()
        self.prompt_builder = PromptBuilder(profile=prompt_profile)
        self.deterministic = ValidationDeterministicAdvisor(self)
        self.rule_checks = ValidationRuleCheckAdvisor(self)

    @staticmethod
    def _large_workbook_threshold_bytes() -> int:
        return int(os.getenv("SHEETHERO_LARGE_WORKBOOK_THRESHOLD_BYTES", "10000000"))

    @classmethod
    def _is_large_workbook(cls, output_path: str) -> bool:
        if not output_path or not os.path.exists(output_path):
            return False
        try:
            return os.path.getsize(output_path) >= cls._large_workbook_threshold_bytes()
        except OSError:
            return False

    @staticmethod
    def _render_validation_result(validation_result: Dict[str, Any]) -> str:
        status = "PASSED" if validation_result.get("validation_passed") else "FAILED"
        confidence = float(validation_result.get("confidence_score", 0.0) or 0.0)
        issues = validation_result.get("issues_found") or ["None identified."]
        feedback = validation_result.get("improvement_feedback") or ""
        final_assessment = validation_result.get("final_assessment") or ""
        issue_lines = "\n".join(f"- {issue}" for issue in issues)
        return (
            f"VALIDATION_STATUS: {status}\n"
            f"CONFIDENCE_SCORE: {confidence:.2f}\n"
            "ISSUES_FOUND:\n"
            f"{issue_lines}\n"
            "IMPROVEMENT_FEEDBACK:\n"
            f"{feedback}\n"
            "FINAL_ASSESSMENT:\n"
            f"{final_assessment}"
        )

    @staticmethod
    def _detected_family_name(user_question: str) -> str:
        family = detect_task_family(user_question)
        return family.name if family is not None else ""

    @classmethod
    def _question_matches_family(cls, user_question: str, *family_names: str) -> bool:
        return cls._detected_family_name(user_question) in set(family_names)

    @staticmethod
    def _looks_like_file_path(s: str) -> bool:
        """True if s looks like a file path (e.g. ends with .xlsx or starts with / or contains \\)."""
        if not s or not isinstance(s, str):
            return False
        s = s.strip()
        if ".xlsx" in s or ".xls" in s or s.startswith("/") or "\\" in s or s.startswith("C:"):
            return True
        return False

    @classmethod
    def _resolve_contract_expectations(
        cls,
        user_question: str,
        need_detail: bool | None,
        need_summary: bool | None,
        need_highlight: bool | None,
    ) -> tuple[bool | None, bool | None, bool | None]:
        family = detect_task_family(user_question)
        if family is None:
            return need_detail, need_summary, need_highlight
        if need_detail is None:
            need_detail = family.requires_detailed_table
        if need_summary is None:
            need_summary = family.requires_summary_metrics
        if need_highlight is None:
            need_highlight = family.requires_highlight
        return need_detail, need_summary, need_highlight

    def run(self, execution_result: Dict[str, Any], user_question: str,
            understanding_output: str) -> Dict[str, Any]:
        logger.info("Starting validation on execution results")

        run_success = bool(execution_result.get("success", False))
        final_answer = execution_result.get("answer", "") or ""
        steps = execution_result.get("execution_summary", {}).get("execution_steps", [])
        successful_steps = [
            step for step in steps
            if bool(step.get("success"))
        ]
        failed_steps = [
            step for step in steps
            if not bool(step.get("success"))
        ]
        last_successful_step = successful_steps[-1] if successful_steps else {}
        latest_result = str(last_successful_step.get("result") or "")
        latest_code = str(last_successful_step.get("code") or "")
        all_results = " ".join(str(s.get("result") or "") for s in steps)
        all_code = "\n".join(str(s.get("code") or "") for s in steps)
        need_detail = self._parse_output_contract_flag(understanding_output, "requires_detailed_table")
        need_highlight = self._parse_output_contract_flag(understanding_output, "requires_highlight")
        need_summary = self._parse_output_contract_flag(understanding_output, "requires_summary_metrics")
        need_detail, need_summary, need_highlight = self._resolve_contract_expectations(
            user_question,
            need_detail,
            need_summary,
            need_highlight,
        )
        family = detect_task_family(user_question)

        deterministic_result = self.deterministic.try_validate(
            execution_result=execution_result,
            user_question=user_question,
            run_success=run_success,
            final_answer=final_answer,
            steps=steps,
            successful_steps=successful_steps,
            failed_steps=failed_steps,
            latest_result=latest_result,
            latest_code=latest_code,
            all_results=all_results,
            all_code=all_code,
            need_detail=need_detail,
            need_summary=need_summary,
            need_highlight=need_highlight,
            family=family,
        )
        if deterministic_result is not None:
            if not successful_steps:
                logger.info("Validation fast-failed: no successful execution steps.")
                logger.info("Validation: FAILED")
            elif execution_result.get("_text_preview_only"):
                logger.info("Validation: PASSED (deterministic text-preview fast-path)")
            elif self._question_matches_family(user_question, "dependency_constrained_schedule"):
                logger.info("Validation: PASSED (deterministic schedule fast-path)")
            elif final_answer and not self._looks_like_file_path(final_answer):
                logger.info("Validation: PASSED (deterministic scalar fast-path)")
            else:
                logger.info("Validation: PASSED (deterministic workbook fast-path)")
            return deterministic_result

        conversation_history = execution_result.get("conversation_history", [])
        conversation_history_text = self.history_formatter.format(conversation_history)

        prompt_text = self.prompt_builder.build_validation_prompt(
            user_query=user_question,
            excel_context_understanding=self.excel_context_understanding,
            execution_context=understanding_output,
            execution_success=execution_result.get("success", False),
            total_turns=execution_result.get("total_turns", 0),
            final_answer=execution_result.get("answer", "No answer provided"),
            execution_summary=execution_result.get("execution_summary", {}),
            conversation_history_text=conversation_history_text
        )
        messages = [{"role": "user", "content": prompt_text}]

        try:
            validation_analysis = self.llm_client.get_response(messages)

            validation_result = self.parser.parse(validation_analysis)

            validation_result = self.rule_checks.apply(
                validation_result,
                execution_result=execution_result,
                user_question=user_question,
                run_success=run_success,
                final_answer=final_answer,
                latest_result=latest_result,
                latest_code=latest_code,
                all_results=all_results,
                all_code=all_code,
                need_detail=need_detail,
                need_summary=need_summary,
                need_highlight=need_highlight,
            )

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

            self._log_to_file(
                f"\n**Validation Analysis:**\n```\n{self._render_validation_result(validation_result)}\n```\n"
            )

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
