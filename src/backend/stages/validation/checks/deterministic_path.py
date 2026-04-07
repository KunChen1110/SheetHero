"""Deterministic validation fast-paths."""

import os
from typing import TYPE_CHECKING, Any, Dict, Optional

from ....task_skills import get_helper_validation_mode

if TYPE_CHECKING:
    from ..runtime import ValidationRuntime


class ValidationDeterministicAdvisor:
    """Own deterministic validation fast-paths before any validation LLM call."""

    def __init__(self, runtime: "ValidationRuntime"):
        self.runtime = runtime

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

        if not successful_steps:
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
            if (skill is not None and skill.name == "schedule"):
                issues.append(
                    "Scheduling task never produced a saved workbook path, so validation cannot pass."
                )
            feedback = (
                "Get to one successful sandbox execution before calling validation again. "
                "Focus on satisfying preflight constraints first: runtime reads, verified headers, "
                "5-column schedule output, and save via save_workbook_to(output_path)."
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

        if (
            run_success
            and final_answer
            and not runtime._looks_like_file_path(final_answer)
            and not (skill is not None and skill.name == "schedule")
            and need_detail is False
            and need_highlight is False
            and need_summary is False
        ):
            deterministic_issues = []
            answer_lower = str(final_answer).strip().lower()
            if (helper is not None and helper.name == "build_missing_data_report"):
                if "missing" not in answer_lower:
                    deterministic_issues.append(
                        "Missing-data task ended with a scalar answer that does not mention missing values."
                    )
            if (helper is not None and helper.name == "build_room_format_report"):
                if "room" not in answer_lower:
                    deterministic_issues.append(
                        "Room-format task ended with a scalar answer that does not mention room identifiers."
                    )
            if not deterministic_issues:
                validation_result = {
                    "validation_passed": True,
                    "confidence_score": 1.0,
                    "issues_found": ["None identified."],
                    "improvement_feedback": "No improvement needed - scalar answer passed deterministic validation.",
                    "final_assessment": (
                        "Scalar response matched the output contract; no validation-LLM retry was needed."
                    ),
                    "verified_answer": final_answer,
                    "requires_reexecution": False,
                }
                runtime._log_to_file(
                    f"\n**Validation Analysis:**\n```\n{runtime._render_validation_result(validation_result)}\n```\n"
                )
                return validation_result

        if run_success and execution_result.get("_text_preview_only"):
            deterministic_issues: list[str] = []
            preview_headers = execution_result.get("_text_preview_headers") or []
            total_preview_rows = int(execution_result.get("_text_total_rows") or 0)
            extra_sheet_names = execution_result.get("_text_preview_extra_sheet_names") or []
            family_fast_path = execution_result.get("_family_fast_path")

            deterministic_issues.extend(
                runtime._inspect_text_preview_generic(
                    preview_headers,
                    total_preview_rows,
                    need_detail=need_detail,
                )
            )

            if helper is not None:
                validation_mode = get_helper_validation_mode(helper.name)
                if validation_mode == "temporal_aggregation":
                    deterministic_issues.extend(runtime._inspect_text_preview_temporal_aggregation(preview_headers, total_preview_rows))
                elif validation_mode == "grouped_aggregation":
                    deterministic_issues.extend(runtime._inspect_text_preview_grouped_aggregation(preview_headers, total_preview_rows))
                elif validation_mode == "relational_join":
                    deterministic_issues.extend(runtime._inspect_text_preview_relational_join(preview_headers, total_preview_rows))
                elif validation_mode == "allocation":
                    deterministic_issues.extend(runtime._inspect_text_preview_allocation(preview_headers, total_preview_rows))
                elif validation_mode == "dependency_schedule":
                    deterministic_issues.extend(runtime._inspect_text_preview_dependency_schedule(preview_headers, total_preview_rows))
                elif validation_mode == "relational_assignment":
                    deterministic_issues.extend(runtime._inspect_text_preview_assignment_schedule(preview_headers, total_preview_rows))
                elif validation_mode == "temporal_growth":
                    deterministic_issues.extend(runtime._inspect_text_preview_region_growth(preview_headers, total_preview_rows))
                elif validation_mode == "regression":
                    deterministic_issues.extend(runtime._inspect_text_preview_regression(preview_headers, total_preview_rows))
                elif validation_mode == "correlation":
                    deterministic_issues.extend(runtime._inspect_text_preview_correlation(preview_headers, total_preview_rows))
                elif validation_mode == "comparative_multi_sheet":
                    deterministic_issues.extend(
                        runtime._inspect_text_preview_comparative_multi_sheet(
                            preview_headers,
                            total_preview_rows,
                            extra_sheet_names,
                        )
                    )

            assessment = (
                "Text preview passed structural schedule checks in text mode; no workbook save was required."
                if family_fast_path == "dependency_constrained_schedule" and not deterministic_issues
                else "Text preview passed deterministic output-contract checks in text mode; no workbook save was required."
            )

            if not deterministic_issues:
                validation_result = {
                    "validation_passed": True,
                    "confidence_score": 1.0,
                    "issues_found": ["None identified."],
                    "improvement_feedback": "No improvement needed - text preview passed deterministic validation.",
                    "final_assessment": assessment,
                    "verified_answer": final_answer,
                    "requires_reexecution": False,
                }
                runtime._log_to_file(
                    f"\n**Validation Analysis:**\n```\n{runtime._render_validation_result(validation_result)}\n```\n"
                )
                return validation_result

        if (
            run_success
            and final_answer
            and runtime._looks_like_file_path(final_answer)
            and ("Workbook saved to:" in all_results or "SAVED_FILE:" in all_results)
            and not (skill is not None and skill.name == "schedule")
        ):
            deterministic_issues = []
            latest_rows = runtime._extract_rows_written(latest_result)
            latest_column_counts = runtime._extract_written_column_counts(latest_result)
            if need_detail is True and latest_rows and max(latest_rows) < 2:
                deterministic_issues.append(
                    "Saved workbook write evidence does not show a header plus at least one data row."
                )
            if need_detail is True and latest_column_counts and max(latest_column_counts) < 2:
                deterministic_issues.append(
                    "Saved workbook write evidence does not show a multi-column output table."
                )
            if (
                need_highlight is True
                and "highlighted row(s)" not in latest_result.lower()
                and "no_highlight_rows:" not in latest_result.lower()
            ):
                deterministic_issues.append(
                    "Output contract requires highlight, but no highlight evidence was found."
                )
            if (helper is not None and helper.name == "build_region_growth_analysis"):
                if "chart saved to" not in latest_result.lower():
                    deterministic_issues.append(
                        "Region-growth output requires an embedded chart, but no chart-save evidence was found."
                    )
                deterministic_issues.extend(runtime._inspect_saved_region_growth_workbook(final_answer))

            use_lightweight_validation = (
                runtime._is_large_workbook(final_answer)
                and need_summary is not True
                and need_highlight is not True
                and not (helper is not None and helper.name == "build_region_growth_analysis")
            )
            if use_lightweight_validation:
                if not os.path.exists(final_answer):
                    deterministic_issues.append(f"Saved output file not found: {final_answer}")
            else:
                deterministic_issues.extend(
                    runtime._inspect_saved_generic_workbook(
                        final_answer,
                        need_detail=need_detail,
                        need_summary=need_summary,
                    )
                )

            if helper is not None:
                validation_mode = get_helper_validation_mode(helper.name)
                if validation_mode == "temporal_aggregation":
                    deterministic_issues.extend(runtime._inspect_saved_temporal_aggregation_workbook(final_answer))
                elif validation_mode == "grouped_aggregation":
                    deterministic_issues.extend(runtime._inspect_saved_grouped_aggregation_workbook(final_answer))
                elif validation_mode == "relational_join":
                    deterministic_issues.extend(runtime._inspect_saved_relational_join_workbook(final_answer))
                elif validation_mode == "allocation":
                    deterministic_issues.extend(runtime._inspect_saved_allocation_workbook(final_answer))
                elif validation_mode == "dependency_schedule":
                    deterministic_issues.extend(runtime._inspect_saved_dependency_schedule_workbook(final_answer))
                elif validation_mode == "relational_assignment":
                    deterministic_issues.extend(runtime._inspect_saved_assignment_schedule_workbook(final_answer))
                elif validation_mode == "temporal_growth":
                    deterministic_issues.extend(runtime._inspect_saved_region_growth_workbook(final_answer))
                elif validation_mode == "regression":
                    deterministic_issues.extend(runtime._inspect_saved_regression_workbook(final_answer))
                elif validation_mode == "correlation":
                    deterministic_issues.extend(runtime._inspect_saved_correlation_workbook(final_answer))
                elif validation_mode == "comparative_multi_sheet":
                    deterministic_issues.extend(runtime._inspect_saved_comparative_multi_sheet_workbook(final_answer))

            if not deterministic_issues:
                assessment = (
                    "Saved workbook passed lightweight structural validation based on runtime write evidence; "
                    "the full workbook scan was skipped because the output file exceeded the large-file threshold."
                    if use_lightweight_validation
                    else "Saved workbook passed structural output-contract checks; no validation-LLM retry was needed."
                )
                validation_result = {
                    "validation_passed": True,
                    "confidence_score": 1.0,
                    "issues_found": ["None identified."],
                    "improvement_feedback": "No improvement needed - saved workbook passed deterministic validation.",
                    "final_assessment": assessment,
                    "verified_answer": final_answer,
                    "requires_reexecution": False,
                }
                runtime._log_to_file(
                    f"\n**Validation Analysis:**\n```\n{runtime._render_validation_result(validation_result)}\n```\n"
                )
                return validation_result

        if (
            (skill is not None and skill.name == "schedule")
            and run_success
            and final_answer
            and runtime._looks_like_file_path(final_answer)
            and ("Workbook saved to:" in all_results or "SAVED_FILE:" in all_results)
        ):
            family_fast_path = execution_result.get("_family_fast_path")
            deterministic_issues = []
            if family_fast_path != "dependency_constrained_schedule":
                deterministic_issues.extend(runtime._collect_schedule_code_issues(all_code))
            deterministic_issues.extend(runtime._inspect_saved_schedule_workbook(final_answer))
            if not deterministic_issues:
                validation_result = {
                    "validation_passed": True,
                    "confidence_score": 1.0,
                    "issues_found": ["None identified."],
                    "improvement_feedback": "No improvement needed - saved schedule passed deterministic validation.",
                    "final_assessment": (
                        "Saved schedule workbook passed structural, timing, and summary checks; "
                        "no validation-LLM retry was needed."
                    ),
                    "verified_answer": final_answer,
                    "requires_reexecution": False,
                }
                runtime._log_to_file(
                    f"\n**Validation Analysis:**\n```\n{runtime._render_validation_result(validation_result)}\n```\n"
                )
                return validation_result

        return None
