"""Early validation short-circuits for obviously incomplete runs."""

from typing import TYPE_CHECKING, Any, Dict, Optional

from ....skills import get_helper_output_mode

if TYPE_CHECKING:
    from ..runtime import ValidationRuntime


class ValidationDeterministicAdvisor:
    """Short-circuit only obvious validation failures before the validation LLM."""

    def __init__(self, runtime: "ValidationRuntime"):
        self.runtime = runtime

    @staticmethod
    def _helper_expects_text_answer(helper) -> bool:
        if helper is None:
            return False
        return get_helper_output_mode(helper.name) == "text"

    def try_validate(
        self,
        *,
        execution_result: Dict[str, Any],
        user_question: str,
        run_success: bool,
        final_answer: str,
        steps: list[dict],
        successful_steps: list[dict],
        failed_steps: list[dict],
        latest_result: str,
        latest_code: str,
        all_results: str,
        all_code: str,
        need_detail: bool | None,
        need_summary: bool | None,
        need_highlight: bool | None,
        skill=None,
        helper=None,
    ) -> Optional[Dict[str, Any]]:
        runtime = self.runtime

        if successful_steps:
            return None

        issues = []
        if not run_success:
            issues.append("Execution result indicates failure (`success=false`).")
        if steps:
            issues.append(
                f"No successful execution step produced runtime output (failed code executions: {len(failed_steps)})."
            )
        else:
            issues.append(
                "No code execution occurred; all turns were blocked by preflight/forbidden/format checks."
            )
        if helper is not None and not self._helper_expects_text_answer(helper):
            issues.append(
                "Helper-driven workbook task never produced a saved workbook path, so validation cannot pass."
            )

        feedback = (
            "Get to one successful sandbox execution before calling validation again. "
            "Focus on satisfying preflight constraints first: runtime reads, verified headers, "
            "output contract compliance, and save via save_workbook_to(output_path)."
        )
        final_assessment = (
            "Validation was short-circuited because execution never produced a successful runnable result."
        )
        validation_result = {
            "validation_passed": False,
            "confidence_score": 0.0,
            "issues_found": issues,
            "improvement_feedback": feedback,
            "final_assessment": final_assessment,
            "verified_answer": "",
            "requires_reexecution": True,
        }
        rendered = (
            "VALIDATION_STATUS: FAILED\n"
            "CONFIDENCE_SCORE: 0.00\n"
            "ISSUES_FOUND:\n"
            + "\n".join(f"- {issue}" for issue in issues)
            + "\nIMPROVEMENT_FEEDBACK:\n"
            + feedback
            + "\nFINAL_ASSESSMENT:\n"
            + final_assessment
        )
        runtime._log_to_file(f"\n**Validation Analysis:**\n```\n{rendered}\n```\n")
        return validation_result
