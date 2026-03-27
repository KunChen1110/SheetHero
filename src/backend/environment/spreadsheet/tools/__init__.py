"""Spreadsheet tool exports for execution/runtime internals.

These exports are meant for the sandbox namespace and backend runtime.
They are not a stable frontend API. The helper workflows collected here are
the main mechanism for the current helper-first execution strategy: runtime
selects a task-appropriate helper, then the LLM only has to call it and write
the returned output.
"""

from .charts import ExcelChartManager
from .edit import ExcelEditor
from .format import ExcelFormatter
from .read import ExcelReader
from .search import ExcelSearch
from .sheet_info import ExcelSheetInfo
from .output import ExcelOutputWriter
from .cross_workbook import (
    get_workbook,
    list_all_workbooks,
    get_sheet_from_workbook,
    inspector_multi,
    read_table_multi,
)
from .diagnose import diagnose_format_inconsistencies
from .workflows import (
    load_all_tables,
    find_table_by_headers,
    infer_common_key,
    infer_common_keys,
    concat_tables_with_same_headers,
    build_relational_join_enrichment_report,
    build_multi_key_relational_join_report,
    build_dependency_schedule,
    build_cycle_detection_report,
    merge_tables_on_key,
    merge_tables_on_keys,
    fill_missing_from_reference,
    build_missing_data_report,
    build_room_format_report,
    build_capacity_constrained_allocation_report,
    build_relational_assignment_schedule_report,
    build_tutor_meeting_schedule_report,
    summarize_numeric_column,
    build_region_growth_analysis,
    build_market_share_shipment_report,
    build_cash_flow_efficiency_report,
    build_diabetes_region_report,
    build_mobile_reviews_summary_report,
    build_store_feature_analysis_report,
    build_ecommerce_merge_report,
    build_financial_dashboard_report,
    build_candidate_screening_report,
    build_inventory_eoq_report,
    build_hospital_utilisation_report,
    build_group_summary,
    build_grouped_aggregation_ranking_report,
    build_time_series_aggregation_report,
    compute_feature_correlations,
    build_correlation_matrix_table,
    fit_linear_regression_weights,
)

__all__ = [
    "ExcelChartManager",
    "ExcelEditor",
    "ExcelFormatter",
    "ExcelReader",
    "ExcelSearch",
    "ExcelSheetInfo",
    "ExcelOutputWriter",
    "get_workbook",
    "list_all_workbooks",
    "get_sheet_from_workbook",
    "inspector_multi",
    "read_table_multi",
    "load_all_tables",
    "find_table_by_headers",
    "infer_common_key",
    "infer_common_keys",
    "concat_tables_with_same_headers",
    "build_relational_join_enrichment_report",
    "build_multi_key_relational_join_report",
    "build_dependency_schedule",
    "build_cycle_detection_report",
    "merge_tables_on_key",
    "merge_tables_on_keys",
    "fill_missing_from_reference",
    "build_missing_data_report",
    "build_room_format_report",
    "build_capacity_constrained_allocation_report",
    "build_relational_assignment_schedule_report",
    "build_tutor_meeting_schedule_report",
    "summarize_numeric_column",
    "build_region_growth_analysis",
    "build_market_share_shipment_report",
    "build_cash_flow_efficiency_report",
    "build_diabetes_region_report",
    "build_mobile_reviews_summary_report",
    "build_store_feature_analysis_report",
    "build_ecommerce_merge_report",
    "build_financial_dashboard_report",
    "build_candidate_screening_report",
    "build_inventory_eoq_report",
    "build_hospital_utilisation_report",
    "build_group_summary",
    "build_grouped_aggregation_ranking_report",
    "build_time_series_aggregation_report",
    "compute_feature_correlations",
    "build_correlation_matrix_table",
    "fit_linear_regression_weights",
    "diagnose_format_inconsistencies",
]
