"""Rule-based post-LLM validation checks."""

import inspect
from typing import TYPE_CHECKING, Any, Dict

from ....skills import (
    detect_skill,
    get_helper_code_inspector_name,
    get_helper_output_mode,
    get_helper_rule_inspector_name,
    get_helper_saved_workbook_inspector_name,
    helper_embeds_summary_in_primary_table,
    select_helper,
)

if TYPE_CHECKING:
    from ..runtime import ValidationRuntime


class ValidationRuleCheckAdvisor:
    """Apply deterministic rule-based checks after validation parsing."""

    def __init__(self, runtime: "ValidationRuntime"):
        self.runtime = runtime

    def _run_runtime_inspector(
        self,
        inspector_name: str | None,
        *args,
    ) -> list[str]:
        if not inspector_name:
            return []
        inspector = getattr(self.runtime, inspector_name, None)
        if not callable(inspector):
            return []
        positional_count = len(
            [
                parameter
                for parameter in inspect.signature(inspector).parameters.values()
                if parameter.kind in (
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                )
            ]
        )
        issues = inspector(*args[:positional_count])
        return list(issues or [])

    @staticmethod
    def _helper_expects_text_answer(helper) -> bool:
        if helper is None:
            return False
        return get_helper_output_mode(helper.name) == "text"

    def apply(
        self,
        validation_result: Dict[str, Any],
        *,
        execution_result: Dict[str, Any],
        user_question: str,
        run_success: bool,
        final_answer: str,
        latest_result: str,
        latest_code: str,
        all_results: str,
        all_code: str,
        need_detail: bool | None,
        need_summary: bool | None,
        need_highlight: bool | None,
    ) -> Dict[str, Any]:
        runtime = self.runtime
        hard_issues: list[str] = []
        _skill = detect_skill(user_question)
        _helper = select_helper(_skill, user_question) if _skill else None

        if not run_success:
            hard_issues.append("Execution result indicates failure (`success=false`).")

        if final_answer and runtime._looks_like_file_path(final_answer):
            if "Workbook saved to:" not in all_results:
                hard_issues.append(
                    "Final answer is a file path but no 'Workbook saved to:' line found in execution output. "
                    "Execution must use save_workbook_to(output_path) and produce save confirmation."
                )
            hard_issues.extend(
                runtime._inspect_saved_generic_workbook(
                    final_answer,
                    need_detail=need_detail,
                    need_summary=need_summary,
                )
            )
        elif _helper is not None and not self._helper_expects_text_answer(_helper):
            hard_issues.append(
                "Helper-driven workbook task did not finish with a saved output workbook path."
            )

        rows_written = runtime._extract_rows_written(latest_result)
        max_rows = max(rows_written) if rows_written else 0
        written_column_counts = runtime._extract_written_column_counts(latest_result)
        max_written_columns = max(written_column_counts) if written_column_counts else 0
        highlighted_rows = runtime._extract_highlight_rows(latest_result)
        summary_rows = runtime._extract_summary_rows(latest_result)
        overlapping_ranges = runtime._find_overlapping_write_ranges(latest_result)
        lower_results = latest_result.lower()

        if need_detail is True and max_rows < 2:
            hard_issues.append(
                "Output contract requires detailed table, but write evidence does not show a header plus at least one data row "
                f"(max rows written = {max_rows})."
            )

        if need_highlight is True:
            if "highlighted row(s)" not in lower_results and "no_highlight_rows:" not in lower_results:
                hard_issues.append("Output contract requires highlight, but no highlight evidence was found.")
            elif max_rows > 0 and highlighted_rows:
                invalid = [r for r in highlighted_rows if r < 2 or r > max_rows + 2]
                if invalid:
                    hard_issues.append(
                        "Highlight rows appear out of expected table range: "
                        + ", ".join(str(v) for v in invalid[:5])
                    )

        if need_summary is True:
            has_summary_signal = (
                ("added summary row" in lower_results)
                or (need_detail is not True and max_rows >= 2)
            )
            if not has_summary_signal and runtime._has_summary_write_signal_from_code(latest_code):
                has_summary_signal = True
            if (
                not has_summary_signal
                and _helper is not None
                and helper_embeds_summary_in_primary_table(_helper.name)
                and max_rows >= 2
            ):
                has_summary_signal = True
            if not has_summary_signal and need_detail is True and max_rows >= 20:
                has_summary_signal = True
            if not has_summary_signal:
                hard_issues.append("Output contract requires summary metrics, but summary write evidence is missing.")
            if need_detail is True and summary_rows and max_rows > 0:
                overlapping_summary_rows = [r for r in summary_rows if r <= max_rows]
                if overlapping_summary_rows:
                    hard_issues.append(
                        "Summary row overlaps the detailed table at row(s): "
                        + ", ".join(str(v) for v in overlapping_summary_rows[:5])
                    )

        if overlapping_ranges:
            previous, current = overlapping_ranges[0]
            hard_issues.append(
                "Output writes overlap in the same sheet: "
                f"{runtime._format_write_range(previous)} vs {runtime._format_write_range(current)}."
            )

        if _helper is not None:
            hard_issues.extend(
                self._run_runtime_inspector(
                    get_helper_rule_inspector_name(_helper.name),
                    all_results,
                    all_code,
                )
            )
            hard_issues.extend(
                self._run_runtime_inspector(
                    get_helper_code_inspector_name(_helper.name),
                    all_code,
                )
            )
            if final_answer and runtime._looks_like_file_path(final_answer):
                hard_issues.extend(
                    self._run_runtime_inspector(
                        get_helper_saved_workbook_inspector_name(_helper.name),
                        final_answer,
                    )
                )

        if validation_result.get("validation_passed") and validation_result.get("issues_found"):
            hard_issues.append("Validator marked PASSED but still reported issues_found.")

        if hard_issues:
            validation_result["validation_passed"] = False
            merged_issues = list(validation_result.get("issues_found") or [])
            merged_issues.extend(hard_issues)
            validation_result["issues_found"] = merged_issues
            feedback = (validation_result.get("improvement_feedback") or "").strip()
            if not feedback:
                validation_result["improvement_feedback"] = (
                    "Fix rule-based validation issues first: contract alignment, output shape, and save evidence."
                )
        elif (
            run_success
            and final_answer
            and runtime._looks_like_file_path(final_answer)
            and validation_result.get("validation_passed") is False
            and runtime._issues_only_reference_earlier_failures(validation_result.get("issues_found") or [])
        ):
            validation_result["validation_passed"] = True
            validation_result["issues_found"] = ["None identified."]
            validation_result["improvement_feedback"] = "No improvement needed - later execution turn corrected earlier failures."
            validation_result["final_assessment"] = (
                "Earlier execution errors were corrected in later turns; final saved output passed rule-based checks."
            )

        return validation_result
