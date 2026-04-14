"""Central task-family registry for spreadsheet workflows.

This module keeps family detection and family-specific execution policy in one
place so stages can reason in terms of spreadsheet capability families instead
of scattering task-case conditionals.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, Optional, Sequence

from .stages.execution.analysis.task_intents import (
    is_candidate_screening_request,
    is_capacity_constrained_allocation_request,
    is_cash_flow_efficiency_request,
    is_correlation_matrix_request,
    is_cycle_detection_request,
    is_dependency_schedule_request,
    is_diabetes_region_request,
    is_ecommerce_merge_request,
    is_fill_missing_request,
    is_financial_dashboard_request,
    is_grouped_aggregation_request,
    is_hospital_utilisation_request,
    is_inventory_eoq_request,
    is_market_share_shipment_request,
    is_missing_data_scan_request,
    is_mobile_reviews_summary_request,
    is_multi_key_relational_join_request,
    is_relational_join_request,
    is_region_growth_chart_request,
    is_regression_request,
    is_relational_assignment_schedule_request,
    is_room_inconsistency_request,
    is_same_schema_merge_summary_request,
    is_simple_horizontal_merge_request,
    is_store_feature_analysis_request,
    is_time_series_aggregation_request,
)


@dataclass(frozen=True)
class TaskFamilySpec:
    name: str
    detector: Callable[[str], bool]
    helper_name: Optional[str] = None
    diagnose_skip: bool = False
    self_loading_helper: bool = False
    output_mode: str = "workbook"
    requires_detailed_table: Optional[bool] = None
    requires_summary_metrics: Optional[bool] = None
    requires_highlight: Optional[bool] = None
    understanding_plan: str = ""
    execution_strict_rules: str = ""
    loop_breaker: str = ""
    final_label: str = ""


@lru_cache(maxsize=1)
def _task_family_specs() -> tuple[TaskFamilySpec, ...]:
    return (
        TaskFamilySpec(
            name="capacity_constrained_allocation",
            detector=is_capacity_constrained_allocation_request,
            helper_name="build_capacity_constrained_allocation_report",
            diagnose_skip=True,
            self_loading_helper=True,
            output_mode="workbook",
            requires_detailed_table=True,
            requires_summary_metrics=False,
            requires_highlight=False,
            understanding_plan=(
                "### 1. Sheet Summary\n"
                "- One table lists entities to place and another table lists resources with capacities or available slots.\n\n"
                "### 2. Execution Plan (Offline Strict)\n"
                "- Use `report = build_capacity_constrained_allocation_report(...)`.\n"
                "- Let the helper infer the entity column, resource column, and capacity column when the exact headers vary.\n"
                "- Write `report['detail_data']` directly to `Output!A1` and add `report['summary']` below.\n"
                "- Do not hand-build greedy allocation loops or manual seat counters.\n"
            ),
            execution_strict_rules=(
                "\n\n**CAPACITY-CONSTRAINED ALLOCATION FAMILY RULES (STRICT):**\n"
                "- Use `build_capacity_constrained_allocation_report(...)` when entities must be assigned to resources with capacities or slots.\n"
                "- Let the helper infer the entity/resource/capacity headers if needed.\n"
                "- Do not hand-build manual loops for seat counting, room filling, or per-resource counters.\n"
            ),
            loop_breaker=(
                "\nCAPACITY-CONSTRAINED ALLOCATION LOOP BREAKER:\n"
                "- Use exactly this helper-first shape:\n"
                "  `report = build_capacity_constrained_allocation_report(range_ref='A1:Z200000')`\n"
                "  `create_output_sheet('Output')`\n"
                "  `write_dataframe_to_sheet(report['detail_data'], 'Output', 'A1')`\n"
                "  `add_summary_row('Output', len(report['detail_data']) + 2, report['summary'])`\n"
                "  `saved_file = save_workbook_to(output_path)`\n"
                "  `print(f'SAVED_FILE: {saved_file}')`\n"
                "  `saved_file`\n"
                "- Do not call `read_table_multi(...)`, `find_table_by_headers(...)`, or `load_all_tables(...)` anywhere in the code.\n"
            ),
            final_label="allocation report",
        ),
        TaskFamilySpec(
            name="schema_aligned_merge_summary",
            detector=is_same_schema_merge_summary_request,
            helper_name="concat_tables_with_same_headers",
            diagnose_skip=False,
            output_mode="workbook",
            requires_detailed_table=True,
            requires_summary_metrics=True,
            requires_highlight=True,
            understanding_plan=(
                "### 1. Sheet Summary\n"
                "- Multiple source tables share the same schema and should be stacked into one detailed table before computing summary metrics.\n\n"
                "### 2. Execution Plan (Offline Strict)\n"
                "- Use `tables = load_all_tables()`.\n"
                "- Use `concat_result = concat_tables_with_same_headers(tables)`.\n"
                "- Use `combined_df = concat_result['output_df']`.\n"
                "- Use `summary_result = summarize_numeric_column(combined_df, value_col='...', summary_labels={...})`.\n"
                "- Write `combined_df` to `Output!A1`, highlight `summary_result['output_row_numbers']`, and add `summary_result['summary']` below.\n"
                "- Do not join on keys when the schemas already match.\n"
            ),
            execution_strict_rules=(
                "\n\n**SAME-SCHEMA AGGREGATE-MERGE FAMILY RULES (STRICT):**\n"
                "- Stack same-schema tables row-wise with `concat_tables_with_same_headers(...)`.\n"
                "- Then derive summary metrics from the combined table with `summarize_numeric_column(...)`.\n"
                "- Do not use `pd.merge(...)` or key-based joins for this family.\n"
            ),
            loop_breaker=(
                "\nSAME-SCHEMA AGGREGATE-MERGE LOOP BREAKER:\n"
                "- Use `tables = load_all_tables()`.\n"
                "- Use `concat_result = concat_tables_with_same_headers(tables)`.\n"
                "- Use `combined_df = concat_result['output_df']`.\n"
                "- Use `summary_result = summarize_numeric_column(combined_df, value_col='...', summary_labels={...})`.\n"
                "- Write `combined_df` to `Output!A1`, highlight `summary_result['output_row_numbers']`, add `summary_result['summary']`, then save.\n"
            ),
            final_label="merged summary spreadsheet",
        ),
        TaskFamilySpec(
            name="reference_guided_completion",
            detector=is_fill_missing_request,
            helper_name="fill_missing_from_reference",
            diagnose_skip=False,
            output_mode="workbook",
            requires_detailed_table=True,
            requires_summary_metrics=False,
            requires_highlight=False,
            understanding_plan=(
                "### 1. Sheet Summary\n"
                "- One source table must be completed using a second reference table that shares a common key or entity identifier.\n\n"
                "### 2. Execution Plan (Offline Strict)\n"
                "- Use `tables = load_all_tables(require_primary_key=False)`.\n"
                "- Use `key_header = infer_common_key(tables)`.\n"
                "- Use `fill_result = fill_missing_from_reference(tables[0]['df'], tables[1]['df'], key_header=key_header, prefer_primary=True)`.\n"
                "- Write `fill_result['output_df']` directly to `Output!A1`.\n"
                "- Keep original non-missing values from the primary table.\n"
            ),
            execution_strict_rules=(
                "\n\n**REFERENCE-FILL COMPLETION FAMILY RULES (STRICT):**\n"
                "- Use `fill_missing_from_reference(...)` for key-based completion from a reference table.\n"
                "- Load with `require_primary_key=False` so partially missing key rows are preserved.\n"
                "- Do not hand-write per-cell fill loops.\n"
            ),
            loop_breaker=(
                "\nREFERENCE-FILL COMPLETION LOOP BREAKER:\n"
                "- Use `tables = load_all_tables(require_primary_key=False)`.\n"
                "- Use `key_header = infer_common_key(tables)`.\n"
                "- Use `fill_result = fill_missing_from_reference(tables[0]['df'], tables[1]['df'], key_header=key_header, prefer_primary=True)`.\n"
                "- Write `fill_result['output_df']` to `Output!A1`, then save.\n"
            ),
            final_label="completed data table",
        ),
        TaskFamilySpec(
            name="composite_key_relational_join",
            detector=is_multi_key_relational_join_request,
            helper_name="build_multi_key_relational_join_report",
            diagnose_skip=False,
            self_loading_helper=True,
            output_mode="workbook",
            requires_detailed_table=True,
            requires_summary_metrics=False,
            requires_highlight=False,
            understanding_plan=(
                "### 1. Sheet Summary\n"
                "- Multiple related source tables must be aligned horizontally using a composite entity key with two or more shared headers.\n\n"
                "### 2. Execution Plan (Offline Strict)\n"
                "- Use `report = build_multi_key_relational_join_report(...)`.\n"
                "- If the composite key headers are obvious but the exact spellings vary, prefer `key_headers=None` and let the helper infer the shared key set.\n"
                "- Write `report['detail_data']` directly to `Output!A1`.\n"
                "- Do not hand-build repeated merge loops or ad-hoc join chains.\n"
            ),
            execution_strict_rules=(
                "\n\n**COMPOSITE-KEY RELATIONAL-JOIN FAMILY RULES (STRICT):**\n"
                "- Use `build_multi_key_relational_join_report(...)` for multi-table joins that depend on two or more shared key headers.\n"
                "- Prefer `key_headers=None` when the composite key is conceptually clear but exact header spellings may vary across files.\n"
                "- Do not hand-build repeated `pd.merge(...)` chains or manual file loops when this family is detected.\n"
            ),
            loop_breaker=(
                "\nCOMPOSITE-KEY RELATIONAL-JOIN LOOP BREAKER:\n"
                "- Use exactly this helper-first shape:\n"
                "  `report = build_multi_key_relational_join_report(range_ref='A1:Z200000', key_headers=None, how='inner')`\n"
                "  `create_output_sheet('Output')`\n"
                "  `write_dataframe_to_sheet(report['detail_data'], 'Output', 'A1')`\n"
                "  `saved_file = save_workbook_to(output_path)`\n"
                "  `print(f'SAVED_FILE: {saved_file}')`\n"
                "  `saved_file`\n"
                "- Do not call `read_table_multi(...)`, `find_table_by_headers(...)`, or `load_all_tables(...)` anywhere in the code.\n"
            ),
            final_label="merged spreadsheet",
        ),
        TaskFamilySpec(
            name="relational_join_enrichment",
            detector=is_relational_join_request,
            helper_name="build_relational_join_enrichment_report",
            diagnose_skip=False,
            self_loading_helper=True,
            output_mode="workbook",
            requires_detailed_table=True,
            requires_summary_metrics=False,
            requires_highlight=False,
            understanding_plan=(
                "### 1. Sheet Summary\n"
                "- Multiple related source tables must be aligned horizontally using a shared entity key.\n\n"
                "### 2. Execution Plan (Offline Strict)\n"
                "- Use `report = build_relational_join_enrichment_report(...)`.\n"
                "- If the shared entity key is obvious but the exact header is uncertain, prefer `key_header=None` and let the helper infer the common key.\n"
                "- Write `report['detail_data']` directly to `Output!A1`.\n"
                "- Do not hand-build repeated merge loops or ad-hoc join chains.\n"
            ),
            execution_strict_rules=(
                "\n\n**RELATIONAL-JOIN-ENRICHMENT FAMILY RULES (STRICT):**\n"
                "- Use `build_relational_join_enrichment_report(...)` for multi-table entity-key joins.\n"
                "- Prefer `key_header=None` when the entity key is conceptually obvious but the exact header may vary across files.\n"
                "- Do not hand-build repeated `pd.merge(...)` chains or manual file loops when this family is detected.\n"
            ),
            loop_breaker=(
                "\nRELATIONAL-JOIN-ENRICHMENT LOOP BREAKER:\n"
                "- Use exactly this helper-first shape:\n"
                "  `report = build_relational_join_enrichment_report(range_ref='A1:Z200000', key_header=None, how='inner')`\n"
                "  `create_output_sheet('Output')`\n"
                "  `write_dataframe_to_sheet(report['detail_data'], 'Output', 'A1')`\n"
                "  `saved_file = save_workbook_to(output_path)`\n"
                "  `print(f'SAVED_FILE: {saved_file}')`\n"
                "  `saved_file`\n"
                "- Do not call `read_table_multi(...)`, `find_table_by_headers(...)`, or `load_all_tables(...)` anywhere in the code.\n"
            ),
            final_label="merged spreadsheet",
        ),
        TaskFamilySpec(
            name="tabular_regression_analysis",
            detector=is_regression_request,
            helper_name="fit_linear_regression_weights",
            diagnose_skip=False,
            output_mode="workbook",
            requires_detailed_table=True,
            requires_summary_metrics=False,
            requires_highlight=False,
            understanding_plan=(
                "### 1. Sheet Summary\n"
                "- One dataset contains a target column and several predictor columns for a regression-style weight or coefficient analysis.\n\n"
                "### 2. Execution Plan (Offline Strict)\n"
                "- Use `tables = load_all_tables()` and `df = tables[0]['df']`.\n"
                "- Define `feature_cols = ['col1', 'col2', ...]` explicitly.\n"
                "- Use `regression_result = fit_linear_regression_weights(df, target_col='...', feature_cols=feature_cols)`.\n"
                "- Print `USED_FEATURES` and write `regression_result['output_df']` directly to `Output!A1`.\n"
                "- Keep all available predictors unless the task explicitly excludes some.\n"
            ),
            execution_strict_rules=(
                "\n\n**REGRESSION-WEIGHT ANALYSIS FAMILY RULES (STRICT):**\n"
                "- Use `fit_linear_regression_weights(...)` for coefficient fitting.\n"
                "- Define `feature_cols` explicitly as string literals.\n"
                "- Do not omit available predictors without an explicit task reason.\n"
            ),
            loop_breaker=(
                "\nREGRESSION-WEIGHT ANALYSIS LOOP BREAKER:\n"
                "- Use `tables = load_all_tables()` and `df = tables[0]['df']`.\n"
                "- Define `feature_cols = ['col1', 'col2', ...]`.\n"
                "- Use `regression_result = fit_linear_regression_weights(df, target_col='...', feature_cols=feature_cols)`.\n"
                "- Print `USED_FEATURES`, write `regression_result['output_df']` to `Output!A1`, then save.\n"
            ),
            final_label="regression report",
        ),
        TaskFamilySpec(
            name="dependency_constrained_schedule",
            detector=is_dependency_schedule_request,
            helper_name="build_dependency_schedule",
            diagnose_skip=False,
            output_mode="workbook",
            requires_detailed_table=True,
            requires_summary_metrics=True,
            requires_highlight=False,
            understanding_plan=(
                "### 1. Sheet Summary\n"
                "- Multiple input tables describe entities with durations/priority and dependency edges.\n\n"
                "### 2. Execution Plan (Offline Strict)\n"
                "- Use `tables = load_all_tables()`.\n"
                "- Select the activity table with `find_table_by_headers(...)` using `Task ID` and duration/name/priority-like headers.\n"
                "- Select the dependency table with `find_table_by_headers(...)` using `Task ID` and `Depends on`.\n"
                "- Use `schedule_result = build_dependency_schedule(task_table['df'], dependency_table['df'], start_time='08:00')`.\n"
                "- Write `schedule_result['detail_data']` to `Output!A1` and add `schedule_result['summary']` below.\n"
                "- Do not rebuild adjacency or topological logic manually.\n"
            ),
            execution_strict_rules=(
                "\n\n**DEPENDENCY-SCHEDULE FAMILY RULES (STRICT):**\n"
                "- Treat this as dependency-constrained scheduling, not as a generic merge.\n"
                "- Keep the activity table and dependency table separate.\n"
                "- Blank `Depends on` means a root task with no incoming edge.\n"
                "- Use `build_dependency_schedule(...)` for ordering and time calculation.\n"
                "- Final rows must expose human-readable `Start Time` and `End Time`.\n"
            ),
            loop_breaker=(
                "\nDEPENDENCY-SCHEDULE LOOP BREAKER:\n"
                "- Use the helper path exactly:\n"
                "  `tables = load_all_tables()`\n"
                "  `task_table = find_table_by_headers(tables, required_headers=['Task ID'], preferred_headers=['Task Name', 'Duration (hours)', 'Priority'], forbidden_headers=['Depends on'])`\n"
                "  `dependency_table = find_table_by_headers(tables, required_headers=['Task ID', 'Depends on'])`\n"
                "  `schedule_result = build_dependency_schedule(task_table['df'], dependency_table['df'], start_time='08:00')`\n"
                "  `create_output_sheet('Output')`\n"
                "  `write_dataframe_to_sheet(schedule_result['detail_data'], 'Output', 'A1')`\n"
                "  `add_summary_row('Output', len(schedule_result['detail_data']) + 2, schedule_result['summary'])`\n"
                "  `saved_file = save_workbook_to(output_path)`\n"
                "  `print(f'SAVED_FILE: {saved_file}')`\n"
                "  `saved_file`\n"
            ),
            final_label="task scheduling table",
        ),
        TaskFamilySpec(
            name="temporal_growth_visual_report",
            detector=is_region_growth_chart_request,
            helper_name="build_region_growth_analysis",
            diagnose_skip=True,
            output_mode="workbook",
            requires_detailed_table=True,
            requires_summary_metrics=True,
            requires_highlight=True,
            understanding_plan=(
                "### 1. Sheet Summary\n"
                "- The workbook contains a messy multi-row header time series table describing regional trends.\n\n"
                "### 2. Execution Plan (Offline Strict)\n"
                "- Use `all_files = list_all_workbooks()`.\n"
                "- Use `analysis = build_region_growth_analysis(all_files[0], sheet_name='Data', start_year=2020, end_year=2024)`.\n"
                "- Write `analysis['output_df']` to `Output!A1`, highlight `analysis['fastest_growth_rows']`, add `analysis['summary']`, and save the chart with `save_plot_to_excel('Output', 'F2')`.\n"
                "- Do not parse the multi-row header manually.\n"
            ),
            execution_strict_rules=(
                "\n\n**REGION-GROWTH FAMILY RULES (STRICT):**\n"
                "- Use `build_region_growth_analysis(...)` instead of manually parsing the multi-row header.\n"
                "- Write the detail table, summary row, and chart in one pass.\n"
                "- Use the injected `plt`; do not import extra plotting libraries.\n"
            ),
            loop_breaker=(
                "\nREGION-GROWTH LOOP BREAKER:\n"
                "- Use `all_files = list_all_workbooks()` and `analysis = build_region_growth_analysis(all_files[0], sheet_name='Data', start_year=2020, end_year=2024)`.\n"
                "- Then write `analysis['output_df']`, highlight `analysis['fastest_growth_rows']`, add `analysis['summary']`, and save the plot to `Output!F2`.\n"
            ),
            final_label="regional growth report",
        ),
        TaskFamilySpec(
            name="pairwise_correlation_matrix",
            detector=is_correlation_matrix_request,
            helper_name="build_correlation_matrix_table",
            diagnose_skip=False,
            output_mode="workbook",
            requires_detailed_table=True,
            requires_summary_metrics=False,
            requires_highlight=False,
            understanding_plan=(
                "### 1. Sheet Summary\n"
                "- The task requires a filtered numeric relationship matrix.\n\n"
                "### 2. Execution Plan (Offline Strict)\n"
                "- Use `tables = load_all_tables()` and `df = tables[0]['df']`.\n"
                "- Use `build_correlation_matrix_table(df, numeric_columns=[...], filter_column='...', filter_value='...')`.\n"
                "- Write the returned matrix directly to `Output!A1`.\n"
            ),
            execution_strict_rules=(
                "\n\n**CORRELATION-MATRIX FAMILY RULES (STRICT):**\n"
                "- Use `build_correlation_matrix_table(...)` and write the returned 2D table directly.\n"
                "- Do not rebuild the matrix cell-by-cell or hard-code file reads.\n"
            ),
            loop_breaker=(
                "\nCORRELATION-MATRIX LOOP BREAKER:\n"
                "- Use `tables = load_all_tables()`, `df = tables[0]['df']`, `matrix_result = build_correlation_matrix_table(...)`, then write `matrix_result['detail_data']` to `Output!A1`.\n"
            ),
            final_label="correlation matrix",
        ),
        TaskFamilySpec(
            name="graph_consistency_scan",
            detector=is_cycle_detection_request,
            helper_name="build_cycle_detection_report",
            diagnose_skip=False,
            output_mode="workbook",
            requires_detailed_table=True,
            requires_summary_metrics=False,
            requires_highlight=False,
            understanding_plan=(
                "### 1. Sheet Summary\n"
                "- Multiple files each describe one directed graph using source and target columns.\n\n"
                "### 2. Execution Plan (Offline Strict)\n"
                "- Use `tables = load_all_tables()`.\n"
                "- Use `build_cycle_detection_report(tables, from_col='Node From', to_col='Node To')`.\n"
                "- Write the returned report directly to `Output!A1`.\n"
            ),
            execution_strict_rules=(
                "\n\n**GRAPH-CYCLE FAMILY RULES (STRICT):**\n"
                "- Use `build_cycle_detection_report(...)` for graph analysis across files.\n"
                "- Do not manually rebuild graph parsing or hard-code CSV paths.\n"
            ),
            loop_breaker=(
                "\nGRAPH-CYCLE LOOP BREAKER:\n"
                "- Use `tables = load_all_tables()`, `cycle_result = build_cycle_detection_report(tables, from_col='Node From', to_col='Node To')`, and write `cycle_result['detail_data']` to `Output!A1`.\n"
            ),
            final_label="cycle detection report",
        ),
        TaskFamilySpec(
            name="multi_source_metric_dashboard",
            detector=is_financial_dashboard_request,
            helper_name="build_financial_dashboard_report",
            diagnose_skip=False,
            self_loading_helper=True,
            output_mode="workbook",
            requires_detailed_table=True,
            requires_summary_metrics=False,
            requires_highlight=False,
            understanding_plan=(
                "### 1. Sheet Summary\n"
                "- Multiple sources must be reconciled into one period-level dashboard.\n\n"
                "### 2. Execution Plan (Offline Strict)\n"
                "- Use `dashboard_result = build_financial_dashboard_report()`.\n"
                "- Write `dashboard_result['detail_data']` directly to `Output!A1`.\n"
                "- Do not hand-build joins, KPI parsing, or derived rows.\n"
            ),
            execution_strict_rules=(
                "\n\n**MULTI-SOURCE DASHBOARD FAMILY RULES (STRICT):**\n"
                "- Use `build_financial_dashboard_report()` for the consolidated dashboard.\n"
                "- Do not manually join month tables or recompute dashboard metrics row-by-row.\n"
            ),
            loop_breaker=(
                "\nMULTI-SOURCE DASHBOARD LOOP BREAKER:\n"
                "- Use `dashboard_result = build_financial_dashboard_report()`, then write `dashboard_result['detail_data']` to `Output!A1`.\n"
            ),
            final_label="dashboard",
        ),
        TaskFamilySpec(
            name="entity_ranking_report",
            detector=is_candidate_screening_request,
            helper_name="build_candidate_screening_report",
            diagnose_skip=False,
            self_loading_helper=True,
            output_mode="workbook",
            requires_detailed_table=True,
            requires_summary_metrics=False,
            requires_highlight=False,
            understanding_plan=(
                "### 1. Sheet Summary\n"
                "- Several similarly structured records must be normalized into a ranked screening table.\n\n"
                "### 2. Execution Plan (Offline Strict)\n"
                "- Use `screening_result = build_candidate_screening_report()`.\n"
                "- Write `screening_result['detail_data']` directly to `Output!A1`.\n"
                "- Do not hand-build ranking formulas, file loops, or manual filtering.\n"
            ),
            execution_strict_rules=(
                "\n\n**RANKED-SCREENING FAMILY RULES (STRICT):**\n"
                "- Use `build_candidate_screening_report()` for normalization and ranking.\n"
                "- Do not hand-build score formulas or ranking tables.\n"
            ),
            loop_breaker=(
                "\nRANKED-SCREENING LOOP BREAKER:\n"
                "- Use `screening_result = build_candidate_screening_report()`, then write `screening_result['detail_data']` to `Output!A1`.\n"
            ),
            final_label="candidate screening report",
        ),
        TaskFamilySpec(
            name="parameter_driven_policy_report",
            detector=is_inventory_eoq_request,
            helper_name="build_inventory_eoq_report",
            diagnose_skip=False,
            self_loading_helper=True,
            output_mode="workbook",
            requires_detailed_table=True,
            requires_summary_metrics=False,
            requires_highlight=False,
            understanding_plan=(
                "### 1. Sheet Summary\n"
                "- One parameter table must be transformed into a structured policy workbook.\n\n"
                "### 2. Execution Plan (Offline Strict)\n"
                "- Use `inventory_result = build_inventory_eoq_report()`.\n"
                "- Write `inventory_result['detail_data']` directly to `Output!A1`.\n"
                "- Do not hand-build EOQ formulas or scenario tables.\n"
            ),
            execution_strict_rules=(
                "\n\n**INVENTORY-POLICY FAMILY RULES (STRICT):**\n"
                "- Use `build_inventory_eoq_report()` for EOQ/reorder-point style policy output.\n"
                "- Keep execution focused on writing the helper output, not rebuilding formulas.\n"
            ),
            loop_breaker=(
                "\nINVENTORY-POLICY LOOP BREAKER:\n"
                "- Use `inventory_result = build_inventory_eoq_report()`, then write `inventory_result['detail_data']` to `Output!A1`.\n"
            ),
            final_label="inventory report",
        ),
        TaskFamilySpec(
            name="capacity_utilisation_report",
            detector=is_hospital_utilisation_request,
            helper_name="build_hospital_utilisation_report",
            diagnose_skip=False,
            self_loading_helper=True,
            output_mode="workbook",
            requires_detailed_table=True,
            requires_summary_metrics=False,
            requires_highlight=True,
            understanding_plan=(
                "### 1. Sheet Summary\n"
                "- Multiple operational tables must be aggregated into a resource-utilisation summary by service or unit.\n\n"
                "### 2. Execution Plan (Offline Strict)\n"
                "- Use `report = build_hospital_utilisation_report()`.\n"
                "- Write `report['detail_data']` directly to `Output!A1`.\n"
                "- If `report['highlight_rows']` is non-empty, highlight those rows in red; otherwise print `NO_HIGHLIGHT_ROWS:` and continue.\n"
            ),
            execution_strict_rules=(
                "\n\n**RESOURCE-UTILISATION FAMILY RULES (STRICT):**\n"
                "- Use `build_hospital_utilisation_report()` for grouped capacity/utilisation output.\n"
                "- Only highlight rows explicitly returned by the helper.\n"
                "- If there are no rows above the threshold, print `NO_HIGHLIGHT_ROWS: threshold not reached` before saving.\n"
            ),
            loop_breaker=(
                "\nRESOURCE-UTILISATION LOOP BREAKER:\n"
                "- Use `report = build_hospital_utilisation_report()`, write `report['detail_data']`, and:\n"
                "  `if report['highlight_rows']:` highlight them in red\n"
                "  `else:` print `NO_HIGHLIGHT_ROWS: threshold not reached`\n"
            ),
            final_label="resource utilisation report",
        ),
        TaskFamilySpec(
            name="overlapping_period_alignment_report",
            detector=is_market_share_shipment_request,
            helper_name="build_market_share_shipment_report",
            diagnose_skip=False,
            self_loading_helper=True,
            output_mode="workbook",
            requires_detailed_table=True,
            requires_summary_metrics=False,
            requires_highlight=False,
            understanding_plan=(
                "### 1. Sheet Summary\n"
                "- Separate sources must be aligned over an overlapping time range and combined into one output table.\n\n"
                "### 2. Execution Plan (Offline Strict)\n"
                "- Use `market_result = build_market_share_shipment_report()`.\n"
                "- Write `market_result['detail_data']` directly to `Output!A1`.\n"
                "- Do not hand-build time-range alignment or multiplication logic.\n"
            ),
            execution_strict_rules=(
                "\n\n**TIME-SERIES ALIGNMENT FAMILY RULES (STRICT):**\n"
                "- Use `build_market_share_shipment_report()` for overlapping-period alignment and derived measures.\n"
                "- Avoid manual quarter/range joins.\n"
            ),
            loop_breaker=(
                "\nTIME-SERIES ALIGNMENT LOOP BREAKER:\n"
                "- Use `market_result = build_market_share_shipment_report()`, then write `market_result['detail_data']` to `Output!A1`.\n"
            ),
            final_label="market share and shipment report",
        ),
        TaskFamilySpec(
            name="temporal_aggregation_ranking",
            detector=is_time_series_aggregation_request,
            helper_name="build_time_series_aggregation_report",
            diagnose_skip=False,
            self_loading_helper=True,
            output_mode="workbook",
            requires_detailed_table=True,
            requires_summary_metrics=False,
            requires_highlight=False,
            understanding_plan=(
                "### 1. Sheet Summary\n"
                "- One time-indexed table must be filtered to a recent window, aggregated by a temporal grain, and ranked by the resulting metric.\n\n"
                "### 2. Execution Plan (Offline Strict)\n"
                "- Use `report = build_time_series_aggregation_report(...)`.\n"
                "- Pass an explicit `date_col`, `period`, `aggregate`, and `window_years` when the task provides them.\n"
                "- If the metric column is obvious but its exact header is uncertain, use `value_col=None` and let the helper infer the strongest numeric measure column.\n"
                "- For monthly ranking tasks, prefer `period='month'` and `period_mode='year_month'` unless the user explicitly asks to combine all Januaries/Februarys across years.\n"
                "- Write `report['detail_data']` directly to `Output!A1`.\n"
                "- Do not hand-build date parsing, rolling-window filtering, or manual groupby code.\n"
            ),
            execution_strict_rules=(
                "\n\n**TEMPORAL-AGGREGATION-RANKING FAMILY RULES (STRICT):**\n"
                "- Use `build_time_series_aggregation_report(...)` for time filtering, temporal grouping, aggregation, and ranking.\n"
                "- Make the temporal grain explicit with `period='month'|'quarter'|'year'`.\n"
                "- Prefer `value_col=None` over inventing placeholder headers such as `Value` when the real metric header is uncertain.\n"
                "- Use `period_mode='year_month'` for YYYY-MM style output and `period_mode='month_of_year'` only when the task explicitly wants calendar-month buckets across years.\n"
                "- Do not manually rebuild date parsing and period grouping with ad-hoc pandas code.\n"
            ),
            loop_breaker=(
                "\nTEMPORAL-AGGREGATION-RANKING LOOP BREAKER:\n"
                "- Use exactly this helper-first shape:\n"
                "  `report = build_time_series_aggregation_report(file_path=None, date_col='Date', value_col=None, period='month', aggregate='mean', window_years=5, period_mode='year_month', sort_desc=True)`\n"
                "  `create_output_sheet('Output')`\n"
                "  `write_dataframe_to_sheet(report['detail_data'], 'Output', 'A1')`\n"
                "  `saved_file = save_workbook_to(output_path)`\n"
                "  `print(f'SAVED_FILE: {saved_file}')`\n"
                "  `saved_file`\n"
                "- Do not call `read_table_multi(...)`, `find_table_by_headers(...)`, or `load_all_tables(...)` anywhere in the code.\n"
            ),
            final_label="time-series summary report",
        ),
        TaskFamilySpec(
            name="grouped_aggregation_ranking",
            detector=is_grouped_aggregation_request,
            helper_name="build_grouped_aggregation_ranking_report",
            diagnose_skip=False,
            self_loading_helper=True,
            output_mode="workbook",
            requires_detailed_table=True,
            requires_summary_metrics=False,
            requires_highlight=False,
            understanding_plan=(
                "### 1. Sheet Summary\n"
                "- One structured table must be grouped by one or more categorical columns, aggregated over a numeric measure, and ranked into a summary table.\n\n"
                "### 2. Execution Plan (Offline Strict)\n"
                "- Use `report = build_grouped_aggregation_ranking_report(...)`.\n"
                "- Pass explicit `group_cols`, `value_col`, and `aggregate` when the task clearly names them.\n"
                "- If the grouping or measure column is obvious but the exact header is uncertain, prefer `group_cols=None` or `value_col=None` and let the helper infer a plausible column.\n"
                "- Write `report['detail_data']` directly to `Output!A1`.\n"
                "- Do not hand-build pandas groupby/sort code when this family is detected.\n"
            ),
            execution_strict_rules=(
                "\n\n**GROUPED-AGGREGATION-RANKING FAMILY RULES (STRICT):**\n"
                "- Use `build_grouped_aggregation_ranking_report(...)` for grouped summary output.\n"
                "- Make the aggregation explicit with `aggregate='mean'|'sum'|'count'|'median'|'min'|'max'`.\n"
                "- Use `group_cols=['...']` when the grouping column is known.\n"
                "- Use `value_col=None` only when the primary numeric measure must be inferred.\n"
                "- Do not manually rebuild groupby/sort logic with ad-hoc pandas code.\n"
            ),
            loop_breaker=(
                "\nGROUPED-AGGREGATION-RANKING LOOP BREAKER:\n"
                "- Use exactly this helper-first shape:\n"
                "  `report = build_grouped_aggregation_ranking_report(file_path=None, group_cols=None, value_col=None, aggregate='mean', top_n=None, sort_desc=True)`\n"
                "  `create_output_sheet('Output')`\n"
                "  `write_dataframe_to_sheet(report['detail_data'], 'Output', 'A1')`\n"
                "  `saved_file = save_workbook_to(output_path)`\n"
                "  `print(f'SAVED_FILE: {saved_file}')`\n"
                "  `saved_file`\n"
                "- Do not call `read_table_multi(...)`, `find_table_by_headers(...)`, or `load_all_tables(...)` anywhere in the code.\n"
            ),
            final_label="grouped summary report",
        ),
        TaskFamilySpec(
            name="derived_efficiency_report",
            detector=is_cash_flow_efficiency_request,
            helper_name="build_cash_flow_efficiency_report",
            diagnose_skip=False,
            self_loading_helper=True,
            output_mode="workbook",
            requires_detailed_table=True,
            requires_summary_metrics=False,
            requires_highlight=False,
            understanding_plan=(
                "### 1. Sheet Summary\n"
                "- One statement workbook must be converted into a year-by-year cash-flow efficiency table.\n\n"
                "### 2. Execution Plan (Offline Strict)\n"
                "- Use `report = build_cash_flow_efficiency_report()`.\n"
                "- Write `report['detail_data']` directly to `Output!A1`.\n"
                "- Do not hand-locate statement rows or recompute ratios manually.\n"
            ),
            execution_strict_rules=(
                "\n\n**CASH-FLOW REPORT FAMILY RULES (STRICT):**\n"
                "- Use `build_cash_flow_efficiency_report()` for statement row extraction and ratio calculation.\n"
                "- Avoid manual row matching and formula rebuilds.\n"
            ),
            loop_breaker=(
                "\nCASH-FLOW REPORT LOOP BREAKER:\n"
                "- Use `report = build_cash_flow_efficiency_report()`, then write `report['detail_data']` to `Output!A1`.\n"
            ),
            final_label="financial report",
        ),
        TaskFamilySpec(
            name="proportion_and_cost_report",
            detector=is_diabetes_region_request,
            helper_name="build_diabetes_region_report",
            diagnose_skip=False,
            self_loading_helper=True,
            output_mode="workbook",
            requires_detailed_table=True,
            requires_summary_metrics=False,
            requires_highlight=False,
            understanding_plan=(
                "### 1. Sheet Summary\n"
                "- Regional count and expenditure sources must be merged into a share-and-cost summary.\n\n"
                "### 2. Execution Plan (Offline Strict)\n"
                "- Use `report = build_diabetes_region_report()`.\n"
                "- Write `report['detail_data']` directly to `Output!A1`.\n"
                "- Do not hand-build regional joins or percentage calculations.\n"
            ),
            execution_strict_rules=(
                "\n\n**REGIONAL-SHARE FAMILY RULES (STRICT):**\n"
                "- Use `build_diabetes_region_report()` for regional merge and share computation.\n"
                "- Avoid manual joins and denominator handling.\n"
            ),
            loop_breaker=(
                "\nREGIONAL-SHARE LOOP BREAKER:\n"
                "- Use `report = build_diabetes_region_report()`, then write `report['detail_data']` to `Output!A1`.\n"
            ),
            final_label="regional report",
        ),
        TaskFamilySpec(
            name="grouped_metric_summary",
            detector=is_mobile_reviews_summary_request,
            helper_name="build_mobile_reviews_summary_report",
            diagnose_skip=False,
            self_loading_helper=True,
            output_mode="workbook",
            requires_detailed_table=True,
            requires_summary_metrics=False,
            requires_highlight=False,
            understanding_plan=(
                "### 1. Sheet Summary\n"
                "- One review dataset must be grouped into a country-brand summary table.\n\n"
                "### 2. Execution Plan (Offline Strict)\n"
                "- Use `report = build_mobile_reviews_summary_report()`.\n"
                "- Write `report['detail_data']` directly to `Output!A1`.\n"
                "- Exclude records with missing ratings.\n"
            ),
            execution_strict_rules=(
                "\n\n**GROUPED-REVIEW SUMMARY FAMILY RULES (STRICT):**\n"
                "- Use `build_mobile_reviews_summary_report()` for grouping and aggregation.\n"
                "- Do not hand-build groupby logic.\n"
            ),
            loop_breaker=(
                "\nGROUPED-REVIEW SUMMARY LOOP BREAKER:\n"
                "- Use `report = build_mobile_reviews_summary_report()`, then write `report['detail_data']` to `Output!A1`.\n"
            ),
            final_label="review summary",
        ),
        TaskFamilySpec(
            name="comparative_multi_sheet_summary",
            detector=is_store_feature_analysis_request,
            helper_name="build_store_feature_analysis_report",
            diagnose_skip=False,
            self_loading_helper=True,
            output_mode="workbook",
            requires_detailed_table=True,
            requires_summary_metrics=False,
            requires_highlight=False,
            understanding_plan=(
                "### 1. Sheet Summary\n"
                "- Operational metrics and metadata must be merged into structured comparative summaries.\n\n"
                "### 2. Execution Plan (Offline Strict)\n"
                "- Use `report = build_store_feature_analysis_report()`.\n"
                "- Write `report['avg_by_type_detail_data']` to `AvgByStoreType!A1`.\n"
                "- Write `report['holiday_detail_data']` to `HolidayVsNonHoliday!A1`.\n"
                "- Do not hand-build merge/groupby or multi-sheet output logic.\n"
            ),
            execution_strict_rules=(
                "\n\n**COMPARATIVE-FEATURE FAMILY RULES (STRICT):**\n"
                "- Use `build_store_feature_analysis_report()` for joined multi-sheet comparative output.\n"
                "- Keep the helper output structure intact.\n"
            ),
            loop_breaker=(
                "\nCOMPARATIVE-FEATURE LOOP BREAKER:\n"
                "- Use `report = build_store_feature_analysis_report()`, write `report['avg_by_type_detail_data']` to `AvgByStoreType!A1`, and write `report['holiday_detail_data']` to `HolidayVsNonHoliday!A1`.\n"
            ),
            final_label="comparative analysis report",
        ),
        TaskFamilySpec(
            name="relational_flattening_report",
            detector=is_ecommerce_merge_request,
            helper_name="build_ecommerce_merge_report",
            diagnose_skip=True,
            self_loading_helper=True,
            output_mode="workbook",
            requires_detailed_table=True,
            requires_summary_metrics=False,
            requires_highlight=False,
            understanding_plan=(
                "### 1. Sheet Summary\n"
                "- Multiple relational source tables must be combined into one denormalized output table.\n\n"
                "### 2. Execution Plan (Offline Strict)\n"
                "- Use `report = build_ecommerce_merge_report()`.\n"
                "- Write `report['detail_data']` directly to `Output!A1`.\n"
                "- Do not hand-build multi-file joins or translation logic.\n"
            ),
            execution_strict_rules=(
                "\n\n**MULTI-TABLE DENORMALIZATION FAMILY RULES (STRICT):**\n"
                "- Use `build_ecommerce_merge_report()` for multi-source relational flattening.\n"
                "- Avoid manual multi-file join plans.\n"
            ),
            loop_breaker=(
                "\nMULTI-TABLE DENORMALIZATION LOOP BREAKER:\n"
                "- Use `report = build_ecommerce_merge_report()`, then write `report['detail_data']` to `Output!A1`.\n"
            ),
            final_label="merged spreadsheet",
        ),
        TaskFamilySpec(
            name="missing_data_scan",
            detector=is_missing_data_scan_request,
            helper_name="build_missing_data_report",
            diagnose_skip=False,
            self_loading_helper=True,
            output_mode="text",
            requires_detailed_table=False,
            requires_summary_metrics=False,
            requires_highlight=False,
            understanding_plan=(
                "### 1. Sheet Summary\n"
                "- The task is a text-only data-quality scan focused on missing values.\n\n"
                "### 2. Execution Plan (Offline Strict)\n"
                "- Use `report = build_missing_data_report()`.\n"
                "- Return `report['answer']` directly.\n"
                "- Do not save an output workbook.\n"
            ),
            execution_strict_rules=(
                "\n\n**MISSING-DATA SCAN FAMILY RULES (STRICT):**\n"
                "- Use `build_missing_data_report()` and return the text answer directly.\n"
                "- Do not create or save a workbook.\n"
            ),
            loop_breaker=(
                "\nMISSING-DATA SCAN LOOP BREAKER:\n"
                "- Use `report = build_missing_data_report()`, `final_text = report['answer']`, `print(f'FINAL_TEXT: {final_text}')`, `final_text`.\n"
            ),
            final_label="missing data report",
        ),
        TaskFamilySpec(
            name="identifier_format_scan",
            detector=is_room_inconsistency_request,
            helper_name="build_room_format_report",
            diagnose_skip=False,
            self_loading_helper=True,
            output_mode="text",
            requires_detailed_table=False,
            requires_summary_metrics=False,
            requires_highlight=False,
            understanding_plan=(
                "### 1. Sheet Summary\n"
                "- The task is a text-only consistency scan over identifier formatting.\n\n"
                "### 2. Execution Plan (Offline Strict)\n"
                "- Use `report = build_room_format_report()`.\n"
                "- Return `report['answer']` directly.\n"
                "- Do not modify or save the workbook.\n"
            ),
            execution_strict_rules=(
                "\n\n**FORMAT-INCONSISTENCY SCAN FAMILY RULES (STRICT):**\n"
                "- Use `build_room_format_report()` and return the text answer directly.\n"
                "- Do not write a workbook.\n"
            ),
            loop_breaker=(
                "\nFORMAT-INCONSISTENCY SCAN LOOP BREAKER:\n"
                "- Use `report = build_room_format_report()`, `final_text = report['answer']`, `print(f'FINAL_TEXT: {final_text}')`, `final_text`.\n"
            ),
            final_label="format inconsistency report",
        ),
        TaskFamilySpec(
            name="relational_assignment_schedule",
            detector=is_relational_assignment_schedule_request,
            helper_name="build_relational_assignment_schedule_report",
            diagnose_skip=True,
            self_loading_helper=True,
            output_mode="workbook",
            requires_detailed_table=True,
            requires_summary_metrics=False,
            requires_highlight=False,
            understanding_plan=(
                "### 1. Sheet Summary\n"
                "- Multiple assignment and scheduling tables must be combined into one entity-to-session schedule.\n\n"
                "### 2. Execution Plan (Offline Strict)\n"
                "- Use `report = build_relational_assignment_schedule_report()`.\n"
                "- Write `report['detail_data']` directly to `Output!A1`.\n"
                "- Do not hand-build multi-file joins or manual row loops.\n"
            ),
            execution_strict_rules=(
                "\n\n**ENTITY-ASSIGNMENT SCHEDULE FAMILY RULES (STRICT):**\n"
                "- Use `build_relational_assignment_schedule_report()` for assignment-to-session scheduling output.\n"
                "- Do not manually reconstruct relationship joins.\n"
            ),
            loop_breaker=(
                "\nENTITY-ASSIGNMENT SCHEDULE LOOP BREAKER:\n"
                "- Use `report = build_relational_assignment_schedule_report()`, then write `report['detail_data']` to `Output!A1`.\n"
            ),
            final_label="assignment schedule",
        ),
    )


def all_task_families() -> Sequence[TaskFamilySpec]:
    return _task_family_specs()


def detect_task_family(user_question: str) -> Optional[TaskFamilySpec]:
    for family in all_task_families():
        if family.detector(user_question):
            return family
    return None


def should_skip_diagnose(user_question: str) -> bool:
    family = detect_task_family(user_question)
    return bool(family and family.diagnose_skip)


_TASK_FAMILY_RUNTIME_MODES = {
    "capacity_constrained_allocation": "zero_arg_helper",
    "schema_aligned_merge_summary": "schema_merge_summary",
    "reference_guided_completion": "reference_completion",
    "grouped_aggregation_ranking": "grouped_aggregation",
    "temporal_aggregation_ranking": "temporal_aggregation",
    "composite_key_relational_join": "composite_relational_join",
    "relational_join_enrichment": "relational_join",
    "tabular_regression_analysis": "regression",
    "pairwise_correlation_matrix": "correlation",
    "dependency_constrained_schedule": "dependency_schedule",
    "temporal_growth_visual_report": "temporal_growth",
    "graph_consistency_scan": "graph_scan",
    "multi_source_metric_dashboard": "zero_arg_helper",
    "entity_ranking_report": "zero_arg_helper",
    "parameter_driven_policy_report": "zero_arg_helper",
    "capacity_utilisation_report": "zero_arg_helper",
    "overlapping_period_alignment_report": "zero_arg_helper",
    "derived_efficiency_report": "zero_arg_helper",
    "proportion_and_cost_report": "zero_arg_helper",
    "grouped_metric_summary": "zero_arg_helper",
    "comparative_multi_sheet_summary": "comparative_multi_sheet",
    "relational_flattening_report": "zero_arg_helper",
    "missing_data_scan": "text_scan",
    "identifier_format_scan": "text_scan",
    "relational_assignment_schedule": "relational_assignment",
}

_TASK_FAMILY_VALIDATION_MODES = {
    "capacity_constrained_allocation": "allocation",
    "dependency_constrained_schedule": "dependency_schedule",
    "grouped_aggregation_ranking": "grouped_aggregation",
    "temporal_aggregation_ranking": "temporal_aggregation",
    "composite_key_relational_join": "relational_join",
    "relational_join_enrichment": "relational_join",
    "relational_assignment_schedule": "relational_assignment",
    "temporal_growth_visual_report": "temporal_growth",
    "tabular_regression_analysis": "regression",
    "pairwise_correlation_matrix": "correlation",
    "comparative_multi_sheet_summary": "comparative_multi_sheet",
}

_TASK_FAMILY_POST_TABLE_SUMMARY_ROW = {
    "capacity_constrained_allocation",
    "schema_aligned_merge_summary",
    "dependency_constrained_schedule",
    "temporal_growth_visual_report",
}


def get_task_family_runtime_mode(family_name: str) -> Optional[str]:
    return _TASK_FAMILY_RUNTIME_MODES.get(family_name)


def get_task_family_validation_mode(family_name: str) -> Optional[str]:
    return _TASK_FAMILY_VALIDATION_MODES.get(family_name)


def task_family_uses_post_table_summary_row(family_name: str) -> bool:
    return family_name in _TASK_FAMILY_POST_TABLE_SUMMARY_ROW
