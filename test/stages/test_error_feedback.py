import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from src.backend.stages.execution.guards.error_feedback import ExecutionErrorFeedbackBuilder


def test_market_share_shipment_feedback_uses_helper_metadata_mapping():
    builder = ExecutionErrorFeedbackBuilder(
        available_workbook_basenames_fn=lambda: [],
        observed_header_set_fn=lambda: set(),
        build_schema_snapshot_fn=lambda: "",
    )

    feedback = builder.build_bounded_error_feedback(
        "Execution error: Could not identify both market-share and shipment tables from the loaded workbooks."
    )

    assert feedback is not None
    assert "build_market_share_shipment_report()" in feedback
    assert "market_share_shipment_result['detail_data']" in feedback
    assert "Do not manually rebuild the shipment-versus-market-share comparison in code." in feedback


def test_regression_coef_feedback_uses_documented_helper_result_keys():
    builder = ExecutionErrorFeedbackBuilder(
        available_workbook_basenames_fn=lambda: [],
        observed_header_set_fn=lambda: set(),
        build_schema_snapshot_fn=lambda: "",
    )

    feedback = builder.build_bounded_error_feedback("Execution error: KeyError: 'coef'")

    assert feedback is not None
    assert "regression helper does not return a `coef` key" in feedback
    assert "regression_result['used_features']" in feedback
    assert "regression_result['output_df']" in feedback
    assert "regression_result['detail_data']" in feedback
    assert "regression_result['coefficients_df']" in feedback


def test_weighted_period_feedback_explains_time_and_shipment_normalization():
    builder = ExecutionErrorFeedbackBuilder(
        available_workbook_basenames_fn=lambda: [],
        observed_header_set_fn=lambda: {"Year", "Units", "Vivo", "Samsung"},
        build_schema_snapshot_fn=lambda: "",
    )

    feedback = builder.build_bounded_error_feedback(
        "Execution error: KeyError: 'Time'\nTraceback:\n  File \"<string>\", line 11, in <module>\n"
        "  File \"workflows.py\", line 231, in merge_on_shared_period\n"
    )

    assert feedback is not None
    assert "shared period column was not normalized" in feedback
    assert "rename(columns={'Year': 'Time'" in feedback
    assert "Units': 'Shipment" in feedback
    assert "merge_on_shared_period" in feedback


def test_string_indices_feedback_explains_dataframe_row_number_fix():
    builder = ExecutionErrorFeedbackBuilder(
        available_workbook_basenames_fn=lambda: [],
        observed_header_set_fn=lambda: {"Date", "Daily Spending (£)"},
        build_schema_snapshot_fn=lambda: "",
    )

    feedback = builder.build_bounded_error_feedback(
        "Execution error: string indices must be integers, not 'str'"
    )

    assert feedback is not None
    assert "iterating a DataFrame yields column labels" in feedback
    assert "summary_result['output_row_numbers']" in feedback
    assert ".index.tolist()" in feedback


def test_merge_summary_feedback_explains_unsupported_max_result_key():
    builder = ExecutionErrorFeedbackBuilder(
        available_workbook_basenames_fn=lambda: [],
        observed_header_set_fn=lambda: {"Date", "Daily Spending (£)"},
        build_schema_snapshot_fn=lambda: "",
    )

    feedback = builder.build_bounded_error_feedback(
        "Execution error: 'max'\nTraceback:\n  File \"<string>\", line 11, in <module>\nKeyError: 'max'"
    )

    assert feedback is not None
    assert "does not return a `max` key" in feedback
    assert "summary_result['output_row_numbers']" in feedback
    assert "summary_result['summary']" in feedback
