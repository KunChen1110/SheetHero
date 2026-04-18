import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from backend.skills.helper_metadata import (
    get_helper_documented_result_keys,
    get_helper_output_mode,
    get_helper_rule_inspector_name,
    get_helper_saved_workbook_inspector_name,
)
from backend.stages.validation.checks.deterministic_path import ValidationDeterministicAdvisor


class _ValidationRuntimeStub:
    def __init__(self) -> None:
        self.logged_messages: list[str] = []

    @staticmethod
    def _looks_like_file_path(value: str) -> bool:
        return value.endswith(".xlsx")

    @staticmethod
    def _render_validation_result(validation_result):
        return str(validation_result)

    def _log_to_file(self, message: str) -> None:
        self.logged_messages.append(message)


def test_dependency_schedule_metadata_uses_strict_saved_workbook_inspector():
    assert (
        get_helper_saved_workbook_inspector_name("build_dependency_schedule")
        == "_inspect_saved_schedule_workbook"
    )


def test_regression_metadata_exposes_rule_inspector():
    assert (
        get_helper_rule_inspector_name("fit_linear_regression_weights")
        == "_collect_regression_feature_coverage_issues"
    )


def test_regression_metadata_exposes_documented_result_keys():
    assert get_helper_documented_result_keys("fit_linear_regression_weights") == (
        "used_features",
        "output_df",
        "detail_data",
        "coefficients_df",
    )


def test_scan_helper_metadata_marks_text_output_mode():
    assert get_helper_output_mode("build_missing_data_report") == "text"


def test_successful_execution_does_not_short_circuit_validation():
    runtime = _ValidationRuntimeStub()
    advisor = ValidationDeterministicAdvisor(runtime)

    result = advisor.try_validate(
        execution_result={"success": True},
        user_question="Check this workbook for identifier format inconsistencies.",
        run_success=True,
        final_answer="The `Venue Code` column uses inconsistent identifier formatting.",
        steps=[{"success": True, "result": "FINAL_TEXT: The `Venue Code` column uses inconsistent identifier formatting."}],
        successful_steps=[{"success": True, "result": "FINAL_TEXT: The `Venue Code` column uses inconsistent identifier formatting."}],
        failed_steps=[],
        latest_result="FINAL_TEXT: The `Venue Code` column uses inconsistent identifier formatting.",
        latest_code="",
        all_results="FINAL_TEXT: The `Venue Code` column uses inconsistent identifier formatting.",
        all_code="",
        need_detail=False,
        need_summary=False,
        need_highlight=False,
        skill=None,
        helper=None,
    )

    assert result is None


def test_validation_short_circuit_fails_when_no_successful_steps():
    runtime = _ValidationRuntimeStub()
    advisor = ValidationDeterministicAdvisor(runtime)

    result = advisor.try_validate(
        execution_result={"success": False},
        user_question="Schedule tasks based on dependencies.",
        run_success=False,
        final_answer="",
        steps=[],
        successful_steps=[],
        failed_steps=[],
        latest_result="",
        latest_code="",
        all_results="",
        all_code="",
        need_detail=False,
        need_summary=False,
        need_highlight=False,
        skill=None,
        helper=None,
    )

    assert result is not None
    assert result["validation_passed"] is False
