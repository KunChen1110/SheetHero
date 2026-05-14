import os
import sys
from types import SimpleNamespace
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from backend.skills.helper_metadata import get_helper_rule_inspector_name
from backend.stages.validation.checks.rule_checks import ValidationRuleCheckAdvisor


class _RuleCheckRuntimeStub:
    @staticmethod
    def _looks_like_file_path(value: str) -> bool:
        return value.endswith(".xlsx")

    @staticmethod
    def _extract_rows_written(_latest_result: str):
        return []

    @staticmethod
    def _extract_written_column_counts(_latest_result: str):
        return []

    @staticmethod
    def _extract_highlight_rows(_latest_result: str):
        return []

    @staticmethod
    def _extract_summary_rows(_latest_result: str):
        return []

    @staticmethod
    def _find_overlapping_write_ranges(_latest_result: str):
        return []

    @staticmethod
    def _has_summary_write_signal_from_code(_latest_code: str) -> bool:
        return False

    @staticmethod
    def _issues_only_reference_earlier_failures(_issues: list[str]) -> bool:
        return False

    @staticmethod
    def _extract_reported_columns(_all_results: str):
        return []

    @staticmethod
    def _expected_regression_predictors(_reported_columns):
        return []

    @staticmethod
    def _extract_feature_cols_from_code(_all_code: str):
        return []

    @staticmethod
    def _extract_weight_labels(_all_results: str):
        return []

    @staticmethod
    def _inspect_saved_generic_workbook(_output_path: str, need_detail=None, need_summary=None):
        return []

    @staticmethod
    def _collect_regression_feature_coverage_issues(_all_results: str, _all_code: str):
        return ["Regression feature coverage incomplete. Missing predictor(s): Study Hours"]


def test_workbook_helper_requires_saved_file_answer_even_without_schedule_skill():
    advisor = ValidationRuleCheckAdvisor(_RuleCheckRuntimeStub())

    result = advisor.apply(
        {
            "validation_passed": True,
            "issues_found": [],
            "improvement_feedback": "",
            "final_assessment": "",
        },
        execution_result={"success": True},
        user_question="Group the table by course and rank by average final score.",
        run_success=True,
        final_answer="Average final score by course computed successfully.",
        latest_result="FINAL_TEXT: Average final score by course computed successfully.",
        latest_code="DETERMINISTIC_SKILL_FAST_PATH",
        all_results="FINAL_TEXT: Average final score by course computed successfully.",
        all_code="DETERMINISTIC_SKILL_FAST_PATH",
        need_detail=False,
        need_summary=False,
        need_highlight=False,
    )

    assert result["validation_passed"] is False
    assert any("saved output workbook path" in issue for issue in result["issues_found"])


def test_regression_rule_check_uses_metadata_routed_inspector():
    advisor = ValidationRuleCheckAdvisor(_RuleCheckRuntimeStub())

    result = advisor.apply(
        {
            "validation_passed": True,
            "issues_found": [],
            "improvement_feedback": "",
            "final_assessment": "",
        },
        execution_result={"success": True},
        user_question="Find the regression coefficients for sales from all available predictors.",
        run_success=True,
        final_answer="/tmp/output.xlsx",
        latest_result="Workbook saved to: /tmp/output.xlsx",
        latest_code="feature_cols = ['TV', 'Radio']",
        all_results="Workbook saved to: /tmp/output.xlsx",
        all_code="feature_cols = ['TV', 'Radio']",
        need_detail=False,
        need_summary=False,
        need_highlight=False,
    )

    assert result["validation_passed"] is False
    assert any("Missing predictor(s): Study Hours" in issue for issue in result["issues_found"])


def test_regression_metadata_exposes_rule_inspector_hook():
    assert (
        get_helper_rule_inspector_name("fit_linear_regression_weights")
        == "_collect_regression_feature_coverage_issues"
    )


def test_summary_only_dashboard_counts_single_written_table_as_summary_signal():
    class _SummaryRuntimeStub(_RuleCheckRuntimeStub):
        @staticmethod
        def _extract_rows_written(_latest_result: str):
            return [7]

    advisor = ValidationRuleCheckAdvisor(_SummaryRuntimeStub())

    result = advisor.apply(
        {
            "validation_passed": True,
            "issues_found": [],
            "improvement_feedback": "",
            "final_assessment": "",
        },
        execution_result={"success": True},
        user_question="Build a consolidated dashboard comparing actuals to targets.",
        run_success=True,
        final_answer="/tmp/output.xlsx",
        latest_result="Wrote 7 rows to Output!A1:E7\nWorkbook saved to: /tmp/output.xlsx",
        latest_code="dashboard_result = build_financial_dashboard_report()\nwrite_dataframe_to_sheet(dashboard_result['detail_data'], 'Output', 'A1')",
        all_results="Wrote 7 rows to Output!A1:E7\nWorkbook saved to: /tmp/output.xlsx",
        all_code="dashboard_result = build_financial_dashboard_report()\nwrite_dataframe_to_sheet(dashboard_result['detail_data'], 'Output', 'A1')",
        need_detail=False,
        need_summary=True,
        need_highlight=False,
    )

    assert result["validation_passed"] is True
    assert not any("summary metrics" in issue for issue in result["issues_found"])


def test_embedded_summary_helper_satisfies_detail_plus_summary_contract(monkeypatch: pytest.MonkeyPatch):
    class _EmbeddedSummaryRuntimeStub(_RuleCheckRuntimeStub):
        @staticmethod
        def _extract_rows_written(_latest_result: str):
            return [10]

    monkeypatch.setattr(
        "backend.stages.validation.checks.rule_checks.detect_skill",
        lambda _question: SimpleNamespace(name="proportion"),
    )
    monkeypatch.setattr(
        "backend.stages.validation.checks.rule_checks.select_helper",
        lambda _skill, _question: SimpleNamespace(name="build_region_share_cost_report"),
    )

    advisor = ValidationRuleCheckAdvisor(_EmbeddedSummaryRuntimeStub())

    result = advisor.apply(
        {
            "validation_passed": True,
            "issues_found": [],
            "improvement_feedback": "",
            "final_assessment": "",
        },
        execution_result={"success": True},
        user_question="Calculate global share of obese population and include the total.",
        run_success=True,
        final_answer="/tmp/output.xlsx",
        latest_result="Wrote 10 rows to Output!A1:E10\nWorkbook saved to: /tmp/output.xlsx",
        latest_code="report = build_region_share_cost_report()\nwrite_dataframe_to_sheet(report['detail_data'], 'Output', 'A1')",
        all_results="Wrote 10 rows to Output!A1:E10\nWorkbook saved to: /tmp/output.xlsx",
        all_code="report = build_region_share_cost_report()\nwrite_dataframe_to_sheet(report['detail_data'], 'Output', 'A1')",
        need_detail=True,
        need_summary=True,
        need_highlight=False,
    )

    assert result["validation_passed"] is True
    assert not any("summary metrics" in issue for issue in result["issues_found"])
