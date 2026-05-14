"""Central helper capability metadata for execution, validation, and repair hints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class HelperRuntimeMetadata:
    runtime_mode: str
    output_mode: str = "workbook"
    validation_mode: Optional[str] = None
    grounding_mode: Optional[str] = None
    result_variable_name: Optional[str] = None
    preflight_guard_names: tuple[str, ...] = ()
    final_response_label: Optional[str] = None
    text_preview_inspector_name: Optional[str] = None
    saved_workbook_inspector_name: Optional[str] = None
    code_inspector_name: Optional[str] = None
    rule_inspector_name: Optional[str] = None
    bounded_error_signatures: tuple[str, ...] = ()
    bounded_error_task_label: Optional[str] = None
    bounded_error_extra_note: str = ""
    documented_result_keys: tuple[str, ...] = ()
    uses_post_table_summary_row: bool = False
    embeds_summary_in_primary_table: bool = False
    scalar_answer_keywords: tuple[str, ...] = ()
    requires_chart_embedding: bool = False
    supports_highlight_rows: bool = False


_HELPER_METADATA: dict[str, HelperRuntimeMetadata] = {
    "concat_tables_with_same_headers": HelperRuntimeMetadata(
        runtime_mode="schema_merge_summary",
        final_response_label="merged spreadsheet",
        uses_post_table_summary_row=True,
        preflight_guard_names=("same_schema_merge_summary_guard",),
    ),
    "fill_missing_from_reference": HelperRuntimeMetadata(
        runtime_mode="reference_completion",
        final_response_label="completed data table",
    ),
    "build_relational_join_enrichment_report": HelperRuntimeMetadata(
        runtime_mode="relational_join",
        validation_mode="relational_join",
        grounding_mode="single_key_join",
        final_response_label="join report",
        text_preview_inspector_name="_inspect_text_preview_relational_join",
        saved_workbook_inspector_name="_inspect_saved_relational_join_workbook",
    ),
    "build_multi_key_relational_join_report": HelperRuntimeMetadata(
        runtime_mode="composite_relational_join",
        validation_mode="relational_join",
        grounding_mode="multi_key_join",
        final_response_label="multi-key join report",
        text_preview_inspector_name="_inspect_text_preview_relational_join",
        saved_workbook_inspector_name="_inspect_saved_relational_join_workbook",
    ),
    "build_grouped_aggregation_ranking_report": HelperRuntimeMetadata(
        runtime_mode="grouped_aggregation",
        validation_mode="grouped_aggregation",
        grounding_mode="grouped_aggregation",
        final_response_label="grouped aggregation report",
        text_preview_inspector_name="_inspect_text_preview_grouped_aggregation",
        saved_workbook_inspector_name="_inspect_saved_grouped_aggregation_workbook",
    ),
    "build_two_dimension_mean_count_summary_report": HelperRuntimeMetadata(
        runtime_mode="zero_arg_helper",
        final_response_label="grouped summary report",
    ),
    "build_multi_source_group_comparison_report": HelperRuntimeMetadata(
        runtime_mode="zero_arg_helper",
        final_response_label="group comparison report",
    ),
    "build_multi_source_utilisation_summary_report": HelperRuntimeMetadata(
        runtime_mode="zero_arg_helper",
        final_response_label="utilisation summary report",
        supports_highlight_rows=True,
    ),
    "build_time_series_aggregation_report": HelperRuntimeMetadata(
        runtime_mode="temporal_aggregation",
        validation_mode="temporal_aggregation",
        grounding_mode="temporal_aggregation",
        final_response_label="time-series aggregation report",
        text_preview_inspector_name="_inspect_text_preview_temporal_aggregation",
        saved_workbook_inspector_name="_inspect_saved_temporal_aggregation_workbook",
    ),
    "fit_linear_regression_weights": HelperRuntimeMetadata(
        runtime_mode="regression",
        validation_mode="regression",
        result_variable_name="regression_result",
        preflight_guard_names=("regression_helper_guard", "regression_feature_guard"),
        final_response_label="regression report",
        text_preview_inspector_name="_inspect_text_preview_regression",
        saved_workbook_inspector_name="_inspect_saved_regression_workbook",
        rule_inspector_name="_collect_regression_feature_coverage_issues",
        documented_result_keys=("used_features", "output_df", "detail_data", "coefficients_df"),
    ),
    "build_correlation_matrix_table": HelperRuntimeMetadata(
        runtime_mode="correlation",
        validation_mode="correlation",
        final_response_label="correlation matrix",
        text_preview_inspector_name="_inspect_text_preview_correlation",
        saved_workbook_inspector_name="_inspect_saved_correlation_workbook",
    ),
    "compute_feature_correlations": HelperRuntimeMetadata(
        runtime_mode="feature_correlation",
        final_response_label="feature correlation report",
        preflight_guard_names=("feature_correlation_guard",),
        documented_result_keys=("target_col", "feature_cols", "correlations", "output_df", "detail_data"),
    ),
    "build_cycle_detection_report": HelperRuntimeMetadata(
        runtime_mode="graph_scan",
        final_response_label="cycle detection report",
    ),
    "build_dependency_schedule": HelperRuntimeMetadata(
        runtime_mode="dependency_schedule",
        validation_mode="dependency_schedule",
        output_mode="workbook",
        result_variable_name="schedule_result",
        preflight_guard_names=("scheduling_dependency_guard",),
        final_response_label="task schedule",
        text_preview_inspector_name="_inspect_text_preview_dependency_schedule",
        saved_workbook_inspector_name="_inspect_saved_schedule_workbook",
        code_inspector_name="_collect_schedule_code_issues",
        uses_post_table_summary_row=True,
    ),
    "build_capacity_constrained_allocation_report": HelperRuntimeMetadata(
        runtime_mode="zero_arg_helper",
        validation_mode="allocation",
        final_response_label="allocation report",
        text_preview_inspector_name="_inspect_text_preview_allocation",
        saved_workbook_inspector_name="_inspect_saved_allocation_workbook",
        uses_post_table_summary_row=True,
    ),
    "build_relational_assignment_schedule_report": HelperRuntimeMetadata(
        runtime_mode="relational_assignment",
        validation_mode="relational_assignment",
        preflight_guard_names=("relational_assignment_guard",),
        final_response_label="assignment schedule",
        text_preview_inspector_name="_inspect_text_preview_assignment_schedule",
        saved_workbook_inspector_name="_inspect_saved_assignment_schedule_workbook",
    ),
    "build_missing_data_report": HelperRuntimeMetadata(
        runtime_mode="text_scan",
        output_mode="text",
        final_response_label="missing data report",
        scalar_answer_keywords=("missing",),
    ),
    "build_room_format_report": HelperRuntimeMetadata(
        runtime_mode="text_scan",
        output_mode="text",
        final_response_label="format consistency report",
        scalar_answer_keywords=("identifier", "format", "inconsistent", "column"),
    ),
    "compute_ratio_column": HelperRuntimeMetadata(
        runtime_mode="atomic_transform",
        final_response_label="ratio analysis",
    ),
    "compute_weighted_score": HelperRuntimeMetadata(
        runtime_mode="atomic_transform",
        final_response_label="weighted ranking report",
    ),
    "compute_percentage_share": HelperRuntimeMetadata(
        runtime_mode="atomic_transform",
        final_response_label="percentage share report",
    ),
    "add_rank_column": HelperRuntimeMetadata(
        runtime_mode="atomic_transform",
        final_response_label="ranked spreadsheet",
    ),
    "build_weighted_share_value_report": HelperRuntimeMetadata(
        runtime_mode="zero_arg_helper",
        final_response_label="weighted share-value report",
        preflight_guard_names=("weighted_share_value_guard",),
        bounded_error_signatures=("Could not identify both market-share and shipment tables from the loaded workbooks.",),
        bounded_error_task_label="weighted share-and-total-value task",
        bounded_error_extra_note="- Do not manually rebuild the weighted share-versus-total-value comparison in code.",
    ),
    "build_region_share_cost_report": HelperRuntimeMetadata(
        runtime_mode="zero_arg_helper",
        final_response_label="regional share and expenditure report",
        embeds_summary_in_primary_table=True,
        bounded_error_signatures=("Could not identify both region-population and region-expenditure tables.",),
        bounded_error_task_label="regional share-and-cost task",
        bounded_error_extra_note="- Do not manually rebuild the regional share and expenditure-per-person calculations in code.",
    ),
    "build_cash_flow_efficiency_report": HelperRuntimeMetadata(
        runtime_mode="zero_arg_helper",
        final_response_label="cash-flow report",
        bounded_error_signatures=("No workbook available for cash-flow analysis.",),
        bounded_error_task_label="cash-flow task",
        bounded_error_extra_note="- Do not manually reconstruct the cash-flow analysis grid in code.",
    ),
    "build_financial_dashboard_report": HelperRuntimeMetadata(
        runtime_mode="zero_arg_helper",
        final_response_label="dashboard",
        embeds_summary_in_primary_table=True,
        bounded_error_signatures=("Could not identify the P&L, sales/marketing, and KPI target tables.",),
        bounded_error_task_label="financial dashboard task",
        bounded_error_extra_note="- Do not manually rebuild the cross-file dashboard joins and KPI calculations in code.",
    ),
    "build_inventory_eoq_report": HelperRuntimeMetadata(
        runtime_mode="zero_arg_helper",
        final_response_label="inventory report",
        bounded_error_signatures=("No inventory parameter table was loaded.",),
        bounded_error_task_label="inventory policy task",
        bounded_error_extra_note="- Do not manually reconstruct EOQ, reorder-point, or scenario tables in code.",
    ),
    "build_region_growth_analysis": HelperRuntimeMetadata(
        runtime_mode="temporal_growth",
        validation_mode="temporal_growth",
        result_variable_name="region_growth_result",
        preflight_guard_names=("region_growth_helper_guard",),
        final_response_label="regional growth report",
        text_preview_inspector_name="_inspect_text_preview_region_growth",
        saved_workbook_inspector_name="_inspect_saved_region_growth_workbook",
        documented_result_keys=(
            "output_df",
            "detail_data",
            "summary",
            "fastest_growth_region",
            "fastest_growth_rows",
            "start_year",
            "end_year",
            "used_years",
        ),
        uses_post_table_summary_row=True,
        requires_chart_embedding=True,
        supports_highlight_rows=True,
    ),
}


def all_helper_names() -> tuple[str, ...]:
    return tuple(_HELPER_METADATA.keys())


def get_helper_metadata(helper_name: str) -> Optional[HelperRuntimeMetadata]:
    return _HELPER_METADATA.get(helper_name)


def get_helper_runtime_mode(helper_name: str) -> Optional[str]:
    metadata = get_helper_metadata(helper_name)
    return metadata.runtime_mode if metadata is not None else None


def get_helper_output_mode(helper_name: str) -> Optional[str]:
    metadata = get_helper_metadata(helper_name)
    return metadata.output_mode if metadata is not None else None


def get_helper_validation_mode(helper_name: str) -> Optional[str]:
    metadata = get_helper_metadata(helper_name)
    return metadata.validation_mode if metadata is not None else None




def get_helper_grounding_mode(helper_name: str) -> Optional[str]:
    metadata = get_helper_metadata(helper_name)
    return metadata.grounding_mode if metadata is not None else None


def get_helper_preflight_guard_names(helper_name: str) -> tuple[str, ...]:
    metadata = get_helper_metadata(helper_name)
    return metadata.preflight_guard_names if metadata is not None else ()


def get_helper_final_response_label(helper_name: str) -> Optional[str]:
    metadata = get_helper_metadata(helper_name)
    return metadata.final_response_label if metadata is not None else None


def get_helper_text_preview_inspector_name(helper_name: str) -> Optional[str]:
    metadata = get_helper_metadata(helper_name)
    return metadata.text_preview_inspector_name if metadata is not None else None


def get_helper_saved_workbook_inspector_name(helper_name: str) -> Optional[str]:
    metadata = get_helper_metadata(helper_name)
    return metadata.saved_workbook_inspector_name if metadata is not None else None


def get_helper_code_inspector_name(helper_name: str) -> Optional[str]:
    metadata = get_helper_metadata(helper_name)
    return metadata.code_inspector_name if metadata is not None else None


def get_helper_rule_inspector_name(helper_name: str) -> Optional[str]:
    metadata = get_helper_metadata(helper_name)
    return metadata.rule_inspector_name if metadata is not None else None


def helper_uses_post_table_summary_row(helper_name: str) -> bool:
    metadata = get_helper_metadata(helper_name)
    return bool(metadata and metadata.uses_post_table_summary_row)


def helper_embeds_summary_in_primary_table(helper_name: str) -> bool:
    metadata = get_helper_metadata(helper_name)
    return bool(metadata and metadata.embeds_summary_in_primary_table)


def helper_scalar_answer_keywords(helper_name: str) -> tuple[str, ...]:
    metadata = get_helper_metadata(helper_name)
    return metadata.scalar_answer_keywords if metadata is not None else ()


def helper_requires_chart_embedding(helper_name: str) -> bool:
    metadata = get_helper_metadata(helper_name)
    return bool(metadata and metadata.requires_chart_embedding)


def helper_supports_highlight_rows(helper_name: str) -> bool:
    metadata = get_helper_metadata(helper_name)
    return bool(metadata and metadata.supports_highlight_rows)


def helper_bounded_error_signatures(helper_name: str) -> tuple[str, ...]:
    metadata = get_helper_metadata(helper_name)
    return metadata.bounded_error_signatures if metadata is not None else ()


def helper_bounded_error_task_label(helper_name: str) -> Optional[str]:
    metadata = get_helper_metadata(helper_name)
    return metadata.bounded_error_task_label if metadata is not None else None


def helper_bounded_error_extra_note(helper_name: str) -> str:
    metadata = get_helper_metadata(helper_name)
    return metadata.bounded_error_extra_note if metadata is not None else ""


def get_helper_documented_result_keys(helper_name: str) -> tuple[str, ...]:
    metadata = get_helper_metadata(helper_name)
    return metadata.documented_result_keys if metadata is not None else ()


def helper_name_for_bounded_error(execution_result: str) -> Optional[str]:
    for helper_name, metadata in _HELPER_METADATA.items():
        if metadata.bounded_error_signatures and any(
            signature in execution_result for signature in metadata.bounded_error_signatures
        ):
            return helper_name
    return None


def helper_result_variable_name(helper_name: str) -> str:
    metadata = get_helper_metadata(helper_name)
    if metadata is not None and metadata.result_variable_name:
        return metadata.result_variable_name
    variable = helper_name.removeprefix("build_").removeprefix("compute_").removeprefix("fit_")
    for suffix in ("_report", "_analysis", "_table", "_column"):
        if variable.endswith(suffix):
            variable = variable[: -len(suffix)]
            break
    variable = variable.strip("_") or "helper_result"
    return f"{variable}_result"
