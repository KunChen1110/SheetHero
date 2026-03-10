"""Task-specific loop-breaker templates for execution repair prompts."""

from __future__ import annotations

from ..analysis.task_intents import (
    is_candidate_screening_request,
    is_cash_flow_efficiency_request,
    is_correlation_matrix_request,
    is_cycle_detection_request,
    is_dependency_schedule_request,
    is_diabetes_region_request,
    is_ecommerce_merge_request,
    is_financial_dashboard_request,
    is_hospital_utilisation_request,
    is_inventory_eoq_request,
    is_market_share_shipment_request,
    is_missing_data_scan_request,
    is_mobile_reviews_summary_request,
    is_region_growth_chart_request,
    is_room_inconsistency_request,
    is_store_feature_analysis_request,
)


def build_schedule_loop_breaker() -> str:
    return (
        "\nSCHEDULING_LOOP_BREAKER_TEMPLATE:\n"
        "- Use the runtime helper path exactly:\n"
        "  `tables = load_all_tables()`\n"
        "  `task_table = find_table_by_headers(tables, required_headers=['Task ID'], preferred_headers=['Task Name', 'Duration (hours)', 'Priority'], forbidden_headers=['Depends on'])`\n"
        "  `dependency_table = find_table_by_headers(tables, required_headers=['Task ID', 'Depends on'])`\n"
        "  `schedule_result = build_dependency_schedule(task_table['df'], dependency_table['df'], start_time='08:00')`\n"
        "- Then write output exactly as:\n"
        "  `create_output_sheet('Output')`\n"
        "  `write_dataframe_to_sheet(schedule_result['detail_data'], 'Output', 'A1')`\n"
        "  `add_summary_row('Output', len(schedule_result['detail_data']) + 2, schedule_result['summary'])`\n"
        "  `print('TASK_ID_SET:', sorted(schedule_result['task_id_set']))`\n"
        "  `print('SCHEDULED_TASK_IDS:', schedule_result['scheduled_task_ids'])`\n"
        "  `saved_file = save_workbook_to(output_path)`\n"
        "  `print(f'SAVED_FILE: {saved_file}')`\n"
        "  `saved_file`\n"
        "- Do not rebuild adjacency, in_degree, or queue manually in scheduling tasks.\n"
        "- Do not infer file roles from filenames or list order."
    )


def build_region_growth_loop_breaker() -> str:
    return (
        "\nREGION_GROWTH_LOOP_BREAKER_TEMPLATE:\n"
        "- Use the runtime helper path exactly:\n"
        "  `all_files = list_all_workbooks()`\n"
        "  `analysis = build_region_growth_analysis(all_files[0], sheet_name='Data', start_year=2020, end_year=2024)`\n"
        "  `create_output_sheet('Output')`\n"
        "  `write_dataframe_to_sheet(analysis['output_df'], 'Output', 'A1')`\n"
        "  `highlight_rows('Output', analysis['fastest_growth_rows'], {'fill_color': 'red'})`\n"
        "  `add_summary_row('Output', len(analysis['detail_data']) + 2, analysis['summary'])`\n"
        "  `chart_df = analysis['chart_df']`\n"
        "  `for region in analysis['region_columns']:`\n"
        "      `plt.plot(chart_df['Year'], chart_df[region], label=region)`\n"
        "  `plt.xlabel('Year')`\n"
        "  `plt.ylabel('Penetration Rate')`\n"
        "  `plt.legend()`\n"
        "  `save_plot_to_excel('Output', 'F2')`\n"
        "  `saved_file = save_workbook_to(output_path)`\n"
        "  `print(f'SAVED_FILE: {saved_file}')`\n"
        "  `saved_file`\n"
        "- `plt` is already available in the sandbox.\n"
        "- Do not use `pd.read_excel`, `inspector`, `plotnine`, `seaborn`, or manual multi-row header parsing in this task."
    )


def build_correlation_matrix_loop_breaker() -> str:
    return (
        "\nCORRELATION_MATRIX_LOOP_BREAKER_TEMPLATE:\n"
        "- Use the runtime helper path exactly:\n"
        "  `tables = load_all_tables()`\n"
        "  `df = tables[0]['df']`\n"
        "  `matrix_result = build_correlation_matrix_table(df, numeric_columns=['sepal_length', 'sepal_width', 'petal_length', 'petal_width'], filter_column='species', filter_value='Iris-setosa')`\n"
        "  `create_output_sheet('Output')`\n"
        "  `write_dataframe_to_sheet(matrix_result['detail_data'], 'Output', 'A1')`\n"
        "  `saved_file = save_workbook_to(output_path)`\n"
        "  `print(f'SAVED_FILE: {saved_file}')`\n"
        "  `saved_file`\n"
        "- Do not use hard-coded paths or manual correlation-matrix reconstruction in this task."
    )


def build_cycle_detection_loop_breaker() -> str:
    return (
        "\nCYCLE_DETECTION_LOOP_BREAKER_TEMPLATE:\n"
        "- Use the runtime helper path exactly:\n"
        "  `tables = load_all_tables()`\n"
        "  `cycle_result = build_cycle_detection_report(tables, from_col='Node From', to_col='Node To')`\n"
        "  `create_output_sheet('Output')`\n"
        "  `write_dataframe_to_sheet(cycle_result['detail_data'], 'Output', 'A1')`\n"
        "  `saved_file = save_workbook_to(output_path)`\n"
        "  `print(f'SAVED_FILE: {saved_file}')`\n"
        "  `saved_file`\n"
        "- Do not use hard-coded CSV paths or manual cycle-detection code in this task."
    )


def build_financial_dashboard_loop_breaker() -> str:
    return (
        "\nFINANCIAL_DASHBOARD_LOOP_BREAKER_TEMPLATE:\n"
        "- Use the runtime helper path exactly:\n"
        "  `dashboard_result = build_financial_dashboard_report()`\n"
        "  `create_output_sheet('Output')`\n"
        "  `write_dataframe_to_sheet(dashboard_result['detail_data'], 'Output', 'A1')`\n"
        "  `saved_file = save_workbook_to(output_path)`\n"
        "  `print(f'SAVED_FILE: {saved_file}')`\n"
        "  `saved_file`\n"
        "- Do not hand-build merges, quarter aggregates, target joins, or assessment labels in this task."
    )


def build_candidate_screening_loop_breaker() -> str:
    return (
        "\nCANDIDATE_SCREENING_LOOP_BREAKER_TEMPLATE:\n"
        "- Use the runtime helper path exactly:\n"
        "  `screening_result = build_candidate_screening_report()`\n"
        "  `create_output_sheet('Output')`\n"
        "  `write_dataframe_to_sheet(screening_result['detail_data'], 'Output', 'A1')`\n"
        "  `saved_file = save_workbook_to(output_path)`\n"
        "  `print(f'SAVED_FILE: {saved_file}')`\n"
        "  `saved_file`\n"
        "- Do not hand-build file loops, score formulas, filtering, or ranking rows in this task."
    )


def build_inventory_eoq_loop_breaker() -> str:
    return (
        "\nINVENTORY_EOQ_LOOP_BREAKER_TEMPLATE:\n"
        "- Use the runtime helper path exactly:\n"
        "  `inventory_result = build_inventory_eoq_report()`\n"
        "  `create_output_sheet('Output')`\n"
        "  `write_dataframe_to_sheet(inventory_result['detail_data'], 'Output', 'A1')`\n"
        "  `saved_file = save_workbook_to(output_path)`\n"
        "  `print(f'SAVED_FILE: {saved_file}')`\n"
        "  `saved_file`\n"
        "- Do not hand-build EOQ formulas, sensitivity tables, or scenario tables in this task."
    )


def build_hospital_utilisation_loop_breaker() -> str:
    return (
        "\nHOSPITAL_UTILISATION_LOOP_BREAKER_TEMPLATE:\n"
        "- Use the runtime helper path exactly:\n"
        "  `report = build_hospital_utilisation_report()`\n"
        "  `create_output_sheet('Output')`\n"
        "  `write_dataframe_to_sheet(report['detail_data'], 'Output', 'A1')`\n"
        "  `if report['highlight_rows']:`\n"
        "      `highlight_rows('Output', report['highlight_rows'], {'fill_color': 'red'})`\n"
        "  `else:`\n"
        "      `print('NO_HIGHLIGHT_ROWS: threshold not reached')`\n"
        "  `saved_file = save_workbook_to(output_path)`\n"
        "  `print(f'SAVED_FILE: {saved_file}')`\n"
        "  `saved_file`\n"
        "- Do not hand-build grouped merges or utilisation formulas in this task."
    )


def build_market_share_shipment_loop_breaker() -> str:
    return (
        "\nMARKET_SHARE_SHIPMENT_LOOP_BREAKER_TEMPLATE:\n"
        "- Use the runtime helper path exactly:\n"
        "  `market_result = build_market_share_shipment_report()`\n"
        "  `create_output_sheet('Output')`\n"
        "  `write_dataframe_to_sheet(market_result['detail_data'], 'Output', 'A1')`\n"
        "  `saved_file = save_workbook_to(output_path)`\n"
        "  `print(f'SAVED_FILE: {saved_file}')`\n"
        "  `saved_file`\n"
        "- Do not read `Overview` sheets or hand-build quarter alignment in this task."
    )


def build_cash_flow_efficiency_loop_breaker() -> str:
    return (
        "\nCASH_FLOW_EFFICIENCY_LOOP_BREAKER_TEMPLATE:\n"
        "- Use the runtime helper path exactly:\n"
        "  `report = build_cash_flow_efficiency_report()`\n"
        "  `create_output_sheet('Output')`\n"
        "  `write_dataframe_to_sheet(report['detail_data'], 'Output', 'A1')`\n"
        "  `saved_file = save_workbook_to(output_path)`\n"
        "  `print(f'SAVED_FILE: {saved_file}')`\n"
        "  `saved_file`\n"
        "- Do not hand-locate rows or recompute cash-flow formulas manually."
    )


def build_diabetes_region_loop_breaker() -> str:
    return (
        "\nDIABETES_REGION_LOOP_BREAKER_TEMPLATE:\n"
        "- Use the runtime helper path exactly:\n"
        "  `report = build_diabetes_region_report()`\n"
        "  `create_output_sheet('Output')`\n"
        "  `write_dataframe_to_sheet(report['detail_data'], 'Output', 'A1')`\n"
        "  `saved_file = save_workbook_to(output_path)`\n"
        "  `print(f'SAVED_FILE: {saved_file}')`\n"
        "  `saved_file`\n"
        "- Do not hand-build region merges or share calculations."
    )


def build_mobile_reviews_loop_breaker() -> str:
    return (
        "\nMOBILE_REVIEWS_LOOP_BREAKER_TEMPLATE:\n"
        "- Use the runtime helper path exactly:\n"
        "  `report = build_mobile_reviews_summary_report()`\n"
        "  `create_output_sheet('Output')`\n"
        "  `write_dataframe_to_sheet(report['detail_data'], 'Output', 'A1')`\n"
        "  `saved_file = save_workbook_to(output_path)`\n"
        "  `print(f'SAVED_FILE: {saved_file}')`\n"
        "  `saved_file`\n"
        "- Exclude rows with missing ratings.\n"
        "- Do not hand-build groupby or aggregation code."
    )


def build_store_feature_analysis_loop_breaker() -> str:
    return (
        "\nSTORE_FEATURE_ANALYSIS_LOOP_BREAKER_TEMPLATE:\n"
        "- Use the runtime helper path exactly:\n"
        "  `report = build_store_feature_analysis_report()`\n"
        "  `create_output_sheet('AvgByStoreType')`\n"
        "  `write_dataframe_to_sheet(report['avg_by_type_detail_data'], 'AvgByStoreType', 'A1')`\n"
        "  `create_output_sheet('HolidayVsNonHoliday')`\n"
        "  `write_dataframe_to_sheet(report['holiday_detail_data'], 'HolidayVsNonHoliday', 'A1')`\n"
        "  `saved_file = save_workbook_to(output_path)`\n"
        "  `print(f'SAVED_FILE: {saved_file}')`\n"
        "  `saved_file`\n"
        "- Do not hand-build merge/groupby or multi-sheet output logic."
    )


def build_ecommerce_merge_loop_breaker() -> str:
    return (
        "\nECOMMERCE_MERGE_LOOP_BREAKER_TEMPLATE:\n"
        "- Use the runtime helper path exactly:\n"
        "  `report = build_ecommerce_merge_report()`\n"
        "  `create_output_sheet('Output')`\n"
        "  `write_dataframe_to_sheet(report['detail_data'], 'Output', 'A1')`\n"
        "  `saved_file = save_workbook_to(output_path)`\n"
        "  `print(f'SAVED_FILE: {saved_file}')`\n"
        "  `saved_file`\n"
        "- Do not hand-build multi-file joins or translation-table merges."
    )


def build_missing_data_loop_breaker() -> str:
    return (
        "\nMISSING_DATA_LOOP_BREAKER_TEMPLATE:\n"
        "- Use the runtime helper path exactly:\n"
        "  `report = build_missing_data_report()`\n"
        "  `final_text = report['answer']`\n"
        "  `print(f'FINAL_TEXT: {final_text}')`\n"
        "  `final_text`\n"
        "- Do not write or save any workbook in this task."
    )


def build_room_format_loop_breaker() -> str:
    return (
        "\nROOM_FORMAT_LOOP_BREAKER_TEMPLATE:\n"
        "- Use the runtime helper path exactly:\n"
        "  `report = build_room_format_report()`\n"
        "  `final_text = report['answer']`\n"
        "  `print(f'FINAL_TEXT: {final_text}')`\n"
        "  `final_text`\n"
        "- Do not modify or save any workbook in this task."
    )


def get_task_specific_loop_breaker(user_question: str) -> str:
    if is_dependency_schedule_request(user_question):
        return build_schedule_loop_breaker()
    if is_region_growth_chart_request(user_question):
        return build_region_growth_loop_breaker()
    if is_correlation_matrix_request(user_question):
        return build_correlation_matrix_loop_breaker()
    if is_cycle_detection_request(user_question):
        return build_cycle_detection_loop_breaker()
    if is_financial_dashboard_request(user_question):
        return build_financial_dashboard_loop_breaker()
    if is_candidate_screening_request(user_question):
        return build_candidate_screening_loop_breaker()
    if is_inventory_eoq_request(user_question):
        return build_inventory_eoq_loop_breaker()
    if is_hospital_utilisation_request(user_question):
        return build_hospital_utilisation_loop_breaker()
    if is_market_share_shipment_request(user_question):
        return build_market_share_shipment_loop_breaker()
    if is_cash_flow_efficiency_request(user_question):
        return build_cash_flow_efficiency_loop_breaker()
    if is_diabetes_region_request(user_question):
        return build_diabetes_region_loop_breaker()
    if is_mobile_reviews_summary_request(user_question):
        return build_mobile_reviews_loop_breaker()
    if is_store_feature_analysis_request(user_question):
        return build_store_feature_analysis_loop_breaker()
    if is_ecommerce_merge_request(user_question):
        return build_ecommerce_merge_loop_breaker()
    if is_missing_data_scan_request(user_question):
        return build_missing_data_loop_breaker()
    if is_room_inconsistency_request(user_question):
        return build_room_format_loop_breaker()
    return ""
