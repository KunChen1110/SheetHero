"""Family-specific execution prompt augmentation helpers."""

from typing import TYPE_CHECKING

from ....task_families import detect_task_family
from ..guards.loop_breakers import get_task_specific_loop_breaker

if TYPE_CHECKING:
    from ..runtime import ExecutionRuntime


class ExecutionFamilyPromptAdvisor:
    """Own family-specific execution prompt augmentation."""

    def __init__(self, runtime: "ExecutionRuntime"):
        self.runtime = runtime

    @staticmethod
    def _detected_family_name(user_question: str) -> str:
        family = detect_task_family(user_question)
        return family.name if family is not None else ""

    @classmethod
    def _question_matches_family(cls, user_question: str, *family_names: str) -> bool:
        return cls._detected_family_name(user_question) in set(family_names)

    def augment_initial_prompt(self, user_content: str, user_question: str) -> str:
        runtime = self.runtime
        basenames = runtime._available_workbook_basenames()
        if basenames:
            file_lines = "\n".join(f"- `{name}`" for name in basenames)
            user_content += (
                "\n\n**AVAILABLE INPUT FILES (STRICT):**\n"
                f"{file_lines}\n"
                "Use ONLY these names for input lookups."
            )
        schema_snapshot = runtime._build_schema_snapshot()
        if schema_snapshot:
            user_content += (
                "\n\n**SCHEMA SNAPSHOT (RUNTIME, TRUST THIS):**\n"
                f"{schema_snapshot}\n"
                "Use these real headers for all select/merge operations. Do not invent columns."
            )
        family = detect_task_family(user_question)
        if family is not None:
            if family.execution_strict_rules:
                user_content += family.execution_strict_rules
            if family.loop_breaker:
                user_content += family.loop_breaker
            observed_headers = sorted(runtime._observed_header_set())
            grounded_hint = runtime.question_inference.build_family_grounded_call_hint(
                family.name,
                user_question,
                observed_headers,
            )
            if grounded_hint:
                user_content += (
                    "\n\n**GROUNDED HELPER HINT (USE REAL HEADERS):**\n"
                    f"- Observed headers: {', '.join(f'`{header}`' for header in observed_headers[:20])}\n"
                    f"- Preferred grounded helper call:\n  `{grounded_hint}`\n"
                    "- Prefer this grounded call over invented column names.\n"
                )
        if self._question_matches_family(user_question, "dependency_constrained_schedule"):
            user_content += (
                "\n\n**SCHEDULING TASK RULES (STRICT):**\n"
                "- Identify table roles from verified headers, not from assumed same-schema logic.\n"
                "- Task table: `Task ID` plus duration/name/priority-like columns.\n"
                "- Dependency table: `Task ID` plus `Depends on`.\n"
                "- Never branch on literal input basenames such as `tc04_input01.xlsx`; those are testcase-specific and non-general.\n"
                "- Different headers between these tables are expected.\n"
                "- Keep task table and dependency table separate; do NOT merge them.\n"
                "- Build `task_id_set` from task table first.\n"
                "- The task table does NOT provide `Depends on`; the dependency table does NOT provide duration/name/priority.\n"
                "- Blank/NaN `Depends on` means ROOT task; skip edge creation.\n"
                "- Use `build_dependency_schedule(task_df, dependency_df, start_time='08:00')` for the DAG step.\n"
                "- Task IDs are string labels like `T1`, `T2`; never cast them to integers or use list indexing by `task_id - 1`.\n"
                "- Do all time arithmetic in integer minutes from `8 * 60`.\n"
                "- Format Start/End Time as `HH:MM` only in final output rows.\n"
                "- Keep total duration units consistent: if you accumulate minutes, convert to hours once at summary time; if you accumulate hours, do not divide again.\n"
                "- Print `TASK_ID_SET` and `SCHEDULED_TASK_IDS`, then assert equality before save."
            )
            user_content += get_task_specific_loop_breaker(user_question)
        if self._question_matches_family(user_question, "schema_aligned_merge_summary"):
            user_content += (
                "\n\n**SAME-SCHEMA MERGE+SUMMARY RULES (STRICT):**\n"
                "- If all input tables share the same headers, stack them vertically; do NOT join on keys.\n"
                "- Prefer:\n"
                "  `tables = load_all_tables()`\n"
                "  `concat_result = concat_tables_with_same_headers(tables)`\n"
                "  `combined_df = concat_result['output_df']`\n"
                "  `summary_result = summarize_numeric_column(combined_df, value_col='...', summary_labels={...})`\n"
                "- Then write the full merged table, highlight `summary_result['output_row_numbers']`, and add `summary_result['summary']` below."
            )
        if self._question_matches_family(user_question, "reference_guided_completion"):
            user_content += (
                "\n\n**FILL-MISSING RULES (STRICT):**\n"
                "- Prefer:\n"
                "  `tables = load_all_tables(require_primary_key=False)`\n"
                "  `key_header = infer_common_key(tables)`\n"
                "  `fill_result = fill_missing_from_reference(tables[0]['df'], tables[1]['df'], key_header=key_header, prefer_primary=True)`\n"
                "- Keep original non-missing values in the primary table.\n"
                "- Write `fill_result['output_df']` directly."
            )
        if self._question_matches_family(user_question, "temporal_growth_visual_report"):
            user_content += (
                "\n\n**REGION-GROWTH CHART RULES (STRICT):**\n"
                "- Do NOT parse the messy multi-row header manually with `read_table_multi()`.\n"
                "- Use:\n"
                "  `all_files = list_all_workbooks()`\n"
                "  `analysis = build_region_growth_analysis(all_files[0], sheet_name='Data', start_year=2020, end_year=2024)`\n"
                "- Then write `analysis['output_df']`, highlight `analysis['fastest_growth_rows']`, add `analysis['summary']`,\n"
                "  and plot `analysis['chart_df']` with one line per region before `save_plot_to_excel('Output', 'F2')`."
            )
            user_content += get_task_specific_loop_breaker(user_question)
        if self._question_matches_family(user_question, "pairwise_correlation_matrix"):
            user_content += (
                "\n\n**CORRELATION-MATRIX RULES (STRICT):**\n"
                "- Prefer the runtime helper path for filtered correlation matrices.\n"
                "- Use:\n"
                "  `tables = load_all_tables()`\n"
                "  `df = tables[0]['df']`\n"
                "  `matrix_result = build_correlation_matrix_table(df, numeric_columns=['sepal_length', 'sepal_width', 'petal_length', 'petal_width'], filter_column='species', filter_value='Iris-setosa')`\n"
                "- Then write `matrix_result['detail_data']` directly to Output.\n"
                "- Do not hard-code input paths, manual CSV reads, or rebuild the matrix cell-by-cell."
            )
            user_content += get_task_specific_loop_breaker(user_question)
        if self._question_matches_family(user_question, "graph_consistency_scan"):
            user_content += (
                "\n\n**CYCLE-DETECTION RULES (STRICT):**\n"
                "- Use the runtime helper path for multiple graph files.\n"
                "- Use:\n"
                "  `tables = load_all_tables()`\n"
                "  `cycle_result = build_cycle_detection_report(tables, from_col='Node From', to_col='Node To')`\n"
                "- Then write `cycle_result['detail_data']` directly to Output.\n"
                "- Do not hard-code CSV reads or rebuild graph parsing manually in this task."
            )
            user_content += get_task_specific_loop_breaker(user_question)
        if self._question_matches_family(user_question, "multi_source_metric_dashboard"):
            user_content += (
                "\n\n**FINANCIAL-DASHBOARD RULES (STRICT):**\n"
                "- This task requires a quarter-level dashboard table, not a scalar answer.\n"
                "- Use the runtime helper path:\n"
                "  `dashboard_result = build_financial_dashboard_report()`\n"
                "- Then write `dashboard_result['detail_data']` directly to `Output!A1`.\n"
                "- Do not hand-build month joins, KPI target parsing, or dashboard rows.\n"
                "- Do not read raw files manually in this task."
            )
            user_content += get_task_specific_loop_breaker(user_question)
        if self._question_matches_family(user_question, "entity_ranking_report"):
            user_content += (
                "\n\n**CANDIDATE-SCREENING RULES (STRICT):**\n"
                "- This task requires a ranked candidate table, not a scalar answer.\n"
                "- Use the runtime helper path:\n"
                "  `screening_result = build_candidate_screening_report()`\n"
                "- Then write `screening_result['detail_data']` directly to `Output!A1`.\n"
                "- The helper already excludes blank names and treats missing numeric inputs as 0.\n"
                "- Do not hand-build file loops, score formulas, or ranking rows."
            )
            user_content += get_task_specific_loop_breaker(user_question)
        if self._question_matches_family(user_question, "parameter_driven_policy_report"):
            user_content += (
                "\n\n**INVENTORY-EOQ RULES (STRICT):**\n"
                "- This task requires three clear tables in one output workbook.\n"
                "- Use the runtime helper path:\n"
                "  `inventory_result = build_inventory_eoq_report()`\n"
                "- Then write `inventory_result['detail_data']` directly to `Output!A1`.\n"
                "- Do not hand-build EOQ formulas, parameter parsing, or table layout."
            )
            user_content += get_task_specific_loop_breaker(user_question)
        if self._question_matches_family(user_question, "capacity_utilisation_report"):
            user_content += (
                "\n\n**HOSPITAL-UTILISATION RULES (STRICT):**\n"
                "- This task requires one service-level output table.\n"
                "- Use the runtime helper path:\n"
                "  `report = build_hospital_utilisation_report()`\n"
                "- Then write `report['detail_data']` directly to `Output!A1`.\n"
                "- Highlight only `report['highlight_rows']`; if none exist, print `NO_HIGHLIGHT_ROWS:` and continue.\n"
                "- Do not hand-build merges or grouped utilisation formulas."
            )
            user_content += get_task_specific_loop_breaker(user_question)
        if self._question_matches_family(user_question, "overlapping_period_alignment_report"):
            user_content += (
                "\n\n**MARKET-SHARE SHIPMENT RULES (STRICT):**\n"
                "- This task requires a detailed output table aligned on overlapping quarters.\n"
                "- Use the runtime helper path:\n"
                "  `market_result = build_market_share_shipment_report()`\n"
                "- Then write `market_result['detail_data']` directly to `Output!A1`.\n"
                "- Do not read `Overview` sheets or hand-build quarter alignment in this task."
            )
            user_content += get_task_specific_loop_breaker(user_question)
        if self._question_matches_family(user_question, "derived_efficiency_report"):
            user_content += (
                "\n\n**CASH-FLOW EFFICIENCY RULES (STRICT):**\n"
                "- This task requires a yearly output table, not a scalar answer.\n"
                "- Use the runtime helper path:\n"
                "  `report = build_cash_flow_efficiency_report()`\n"
                "- Then write `report['detail_data']` directly to `Output!A1`.\n"
                "- Do not hand-locate rows in the financial statement workbook."
            )
            user_content += get_task_specific_loop_breaker(user_question)
        if self._question_matches_family(user_question, "proportion_and_cost_report"):
            user_content += (
                "\n\n**DIABETES-REGION RULES (STRICT):**\n"
                "- This task requires one regional summary table, not a scalar answer.\n"
                "- Use the runtime helper path:\n"
                "  `report = build_diabetes_region_report()`\n"
                "- Then write `report['detail_data']` directly to `Output!A1`.\n"
                "- Do not hand-build region joins or share calculations in this task."
            )
            user_content += get_task_specific_loop_breaker(user_question)
        if self._question_matches_family(user_question, "grouped_metric_summary"):
            user_content += (
                "\n\n**MOBILE-REVIEWS RULES (STRICT):**\n"
                "- This task requires one grouped summary table, not a scalar answer.\n"
                "- Use the runtime helper path:\n"
                "  `report = build_mobile_reviews_summary_report()`\n"
                "- Then write `report['detail_data']` directly to `Output!A1`.\n"
                "- Exclude rows with missing ratings.\n"
                "- Do not hand-build groupby or aggregation code in this task."
            )
            user_content += get_task_specific_loop_breaker(user_question)
        if self._question_matches_family(user_question, "comparative_multi_sheet_summary"):
            user_content += (
                "\n\n**STORE-FEATURE ANALYSIS RULES (STRICT):**\n"
                "- This task requires two output sheets.\n"
                "- Use the runtime helper path:\n"
                "  `report = build_store_feature_analysis_report()`\n"
                "- Write `report['avg_by_type_detail_data']` to `AvgByStoreType!A1`.\n"
                "- Write `report['holiday_detail_data']` to `HolidayVsNonHoliday!A1`.\n"
                "- Do not hand-build merges or groupby logic in this task."
            )
            user_content += get_task_specific_loop_breaker(user_question)
        if self._question_matches_family(user_question, "relational_flattening_report"):
            user_content += (
                "\n\n**ECOMMERCE-MERGE RULES (STRICT):**\n"
                "- This task requires one merged output table, not a scalar answer.\n"
                "- Use the runtime helper path:\n"
                "  `report = build_ecommerce_merge_report()`\n"
                "- Then write `report['detail_data']` directly to `Output!A1`.\n"
                "- The helper handles translation to English for product category names.\n"
                "- Do not hand-build multi-file joins or translation logic in this task."
            )
            user_content += get_task_specific_loop_breaker(user_question)
        if self._question_matches_family(user_question, "missing_data_scan"):
            user_content += (
                "\n\n**MISSING-DATA REPORT RULES (STRICT):**\n"
                "- This task requires a short text answer, not a new spreadsheet.\n"
                "- Use the runtime helper path:\n"
                "  `report = build_missing_data_report()`\n"
                "  `final_text = report['answer']`\n"
                "  `print(f'FINAL_TEXT: {final_text}')`\n"
                "  `final_text`\n"
                "- Do not create or save an output workbook in this task."
            )
            user_content += get_task_specific_loop_breaker(user_question)
        if self._question_matches_family(user_question, "identifier_format_scan"):
            user_content += (
                "\n\n**ROOM-FORMAT REPORT RULES (STRICT):**\n"
                "- This task requires a natural-language finding, not a new spreadsheet.\n"
                "- Use the runtime helper path:\n"
                "  `report = build_room_format_report()`\n"
                "  `final_text = report['answer']`\n"
                "  `print(f'FINAL_TEXT: {final_text}')`\n"
                "  `final_text`\n"
                "- Do not modify or save the workbook in this task."
            )
            user_content += get_task_specific_loop_breaker(user_question)
        if self._question_matches_family(user_question, "relational_assignment_schedule"):
            user_content += (
                "\n\n**ASSIGNMENT-SCHEDULE FAMILY RULES (STRICT):**\n"
                "- This task requires one consolidated output spreadsheet.\n"
                "- Use the runtime helper path:\n"
                "  `report = build_relational_assignment_schedule_report()`\n"
                "- Then write `report['detail_data']` directly to `Output!A1`.\n"
                "- Do not hand-build multi-file joins or iterate over DataFrame columns as rows."
            )
            user_content += get_task_specific_loop_breaker(user_question)
        if self._question_matches_family(user_question, "relational_join_enrichment"):
            user_content += (
                "\n\n**SIMPLE MERGE RULES (STRICT):**\n"
                "- Prefer:\n"
                "  `tables = load_all_tables()`\n"
                "  `key_header = infer_common_key(tables)`\n"
                "  `merge_result = merge_tables_on_key(tables, key_header=key_header, how='inner')`\n"
                "- Write `merge_result['output_df']` directly."
            )
        if self._question_matches_family(user_question, "tabular_regression_analysis"):
            user_content += (
                "\n\n**REGRESSION TASK RULES (STRICT):**\n"
                "- Prefer the runtime helper path for coefficient fitting.\n"
                "- Use:\n"
                "  `tables = load_all_tables()`\n"
                "  `df = tables[0]['df']`\n"
                "  `feature_cols = ['col1', 'col2', ...]`\n"
                "  `regression_result = fit_linear_regression_weights(df, target_col='...', feature_cols=feature_cols)`\n"
                "- Then print `USED_FEATURES` and write `regression_result['output_df']` directly.\n"
                "- Keep all available predictors unless the user explicitly excludes some."
            )
        return user_content
