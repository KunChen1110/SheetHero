# environment/spreadsheet/namespace.py

import os
from types import SimpleNamespace

from ..spreadsheet.world import SpreadsheetWorld
# import tools
from ..spreadsheet.tools import (
    ExcelChartManager,
    ExcelEditor,
    ExcelFormatter,
    ExcelReader,
    ExcelSearch,
    ExcelSheetInfo,
    ExcelOutputWriter,
    get_workbook,
    list_all_workbooks,
    get_sheet_from_workbook,
    inspector_multi,
    read_table_multi,
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
    diagnose_format_inconsistencies,
)


class SpreadsheetNamespace:
    """
    Spreadsheet capabilities exposed to Data Analysis Agent.
    """

    def __init__(self, world: SpreadsheetWorld):
        self.world = world
        self.temp_files = []

        wb = world.primary_workbook

        self.reader = ExcelReader(wb)
        self.searcher = ExcelSearch(wb, self.reader)
        self.sheet_info = ExcelSheetInfo(wb, self.reader)
        self.editor = ExcelEditor(wb, self.reader)
        self.formatter = ExcelFormatter(wb, self.reader)
        self.charts = ExcelChartManager(wb, self.reader, self.temp_files)
        self.output = ExcelOutputWriter(
            wb,
            world.primary_path,
            world.output_path,
            self.temp_files
        )

    def build(self) -> SimpleNamespace:
        w = self.world
        workbook_paths = list_all_workbooks(w)
        file_by_name = {
            os.path.basename(path): path
            for path in workbook_paths
        }

        def _read_table_multi(
            file_path,
            sheet_name=None,
            range_ref="A1:Z200",
            require_primary_key=True,
            stop_at_note_row=True,
            **kwargs,
        ):
            if "sn" in kwargs and sheet_name is None:
                sheet_name = kwargs.pop("sn")
            if "rr" in kwargs and range_ref == "A1:Z200":
                range_ref = kwargs.pop("rr")
            if "pk" in kwargs:
                require_primary_key = kwargs.pop("pk")
            if "stop_note" in kwargs:
                stop_at_note_row = kwargs.pop("stop_note")
            if kwargs:
                unknown = ", ".join(sorted(kwargs.keys()))
                raise TypeError(
                    "read_table_multi() got unexpected keyword argument(s): "
                    f"{unknown}"
                )
            return read_table_multi(
                w,
                file_path,
                sheet_name,
                range_ref,
                require_primary_key,
                stop_at_note_row,
            )

        return SimpleNamespace(
            # ----- read / inspect -----
            get_sheet=self.reader.get_sheet,
            search=self.searcher.search,

            list_sheets=self.sheet_info.list_sheets,
            get_sheet_info=self.sheet_info.get_sheet_info,
            get_all_sheets_info=self.sheet_info.get_all_sheets_info,
            inspector_attribute=self.reader.inspector_attribute,

            # ----- edit / transform -----
            insert_rows=self.editor.insert_rows,
            insert_columns=self.editor.insert_columns,
            delete_rows=self.editor.delete_rows,
            delete_columns=self.editor.delete_columns,
            set_cell_value=self.editor.set_cell_value,
            set_range_values=self.editor.set_range_values,
            copy_range=self.editor.copy_range,
            add_formula=self.editor.add_formula,

            # ----- format / chart -----
            apply_formatting=self.formatter.apply_formatting,
            create_chart=self.charts.create_chart,
            save_plot_to_excel=self.charts.save_plot_to_excel,

            # ----- output -----
            create_output_sheet=self.output.create_output_sheet,
            write_dataframe_to_sheet=self.output.write_dataframe_to_sheet,
            highlight_rows=self.output.highlight_rows,
            save_workbook_to=self.output.save_workbook_to,
            add_summary_row=self.output.add_summary_row,
            write_summary_row=self.output.add_summary_row,

            # ----- cross-workbook helpers -----
            get_workbook=lambda fp: get_workbook(w, fp),
            list_all_workbooks=lambda: list_all_workbooks(w),
            file_by_name=file_by_name,
            get_sheet_from_workbook=lambda fp, sn: get_sheet_from_workbook(w, fp, sn),
            inspector_multi=lambda fp, rr, sn=None: inspector_multi(w, fp, rr, sn),
            read_table_multi=_read_table_multi,
            load_all_tables=lambda range_ref="A1:Z200", require_primary_key=True, stop_at_note_row=True: load_all_tables(
                w,
                range_ref,
                require_primary_key,
                stop_at_note_row,
            ),
            find_table_by_headers=find_table_by_headers,
            infer_common_key=infer_common_key,
            find_common_key=infer_common_key,
            infer_common_keys=infer_common_keys,
            concat_tables_with_same_headers=concat_tables_with_same_headers,
            build_relational_join_enrichment_report=lambda range_ref="A1:Z200000", key_header=None, how="inner": build_relational_join_enrichment_report(
                w,
                range_ref=range_ref,
                key_header=key_header,
                how=how,
            ),
            build_multi_key_relational_join_report=lambda range_ref="A1:Z200000", key_headers=None, how="inner": build_multi_key_relational_join_report(
                w,
                range_ref=range_ref,
                key_headers=key_headers,
                how=how,
            ),
            build_dependency_schedule=build_dependency_schedule,
            build_cycle_detection_report=build_cycle_detection_report,
            merge_tables_on_key=merge_tables_on_key,
            merge_tables_on_keys=merge_tables_on_keys,
            fill_missing_from_reference=fill_missing_from_reference,
            build_missing_data_report=lambda range_ref="A1:Z200": build_missing_data_report(
                w, range_ref=range_ref
            ),
            build_room_format_report=lambda range_ref="A1:Z200": build_room_format_report(
                w, range_ref=range_ref
            ),
            build_capacity_constrained_allocation_report=lambda range_ref="A1:Z200000": build_capacity_constrained_allocation_report(
                w, range_ref=range_ref
            ),
            build_relational_assignment_schedule_report=lambda range_ref="A1:Z200": build_relational_assignment_schedule_report(
                w, range_ref=range_ref
            ),
            summarize_numeric_column=summarize_numeric_column,
            build_region_growth_analysis=lambda file_path, sheet_name="Data", start_year=2020, end_year=2024: build_region_growth_analysis(
                w, file_path, sheet_name, start_year, end_year
            ),
            build_market_share_shipment_report=lambda range_ref="A1:Z300": build_market_share_shipment_report(
                w, range_ref=range_ref
            ),
            build_cash_flow_efficiency_report=lambda file_path=None: build_cash_flow_efficiency_report(
                w, file_path=file_path
            ),
            build_diabetes_region_report=lambda range_ref="A1:Z200": build_diabetes_region_report(
                w, range_ref=range_ref
            ),
            build_mobile_reviews_summary_report=lambda range_ref="A1:Y50000": build_mobile_reviews_summary_report(
                w, range_ref=range_ref
            ),
            build_store_feature_analysis_report=lambda range_ref="A1:Z100000": build_store_feature_analysis_report(
                w, range_ref=range_ref
            ),
            build_ecommerce_merge_report=lambda range_ref="A1:Z200000": build_ecommerce_merge_report(
                w, range_ref=range_ref
            ),
            build_financial_dashboard_report=lambda range_ref="A1:Z200": build_financial_dashboard_report(
                w, range_ref=range_ref
            ),
            build_candidate_screening_report=lambda range_ref="A1:Z50": build_candidate_screening_report(
                w, range_ref=range_ref
            ),
            build_inventory_eoq_report=lambda range_ref="A1:Z50": build_inventory_eoq_report(
                w, range_ref=range_ref
            ),
            build_hospital_utilisation_report=lambda range_ref="A1:Z10000": build_hospital_utilisation_report(
                w, range_ref=range_ref
            ),
            build_group_summary=build_group_summary,
            build_grouped_aggregation_ranking_report=lambda file_path=None, sheet_name=None, range_ref="A1:Z200000", group_cols=None, value_col=None, aggregate="mean", top_n=None, sort_desc=True, round_digits=4: build_grouped_aggregation_ranking_report(
                w,
                file_path=file_path,
                sheet_name=sheet_name,
                range_ref=range_ref,
                group_cols=group_cols,
                value_col=value_col,
                aggregate=aggregate,
                top_n=top_n,
                sort_desc=sort_desc,
                round_digits=round_digits,
            ),
            build_time_series_aggregation_report=lambda file_path=None, sheet_name=None, range_ref="A1:Z200000", date_col="Date", value_col=None, period="month", aggregate="mean", window_years=None, period_mode="year_month", sort_desc=True: build_time_series_aggregation_report(
                w,
                file_path=file_path,
                sheet_name=sheet_name,
                range_ref=range_ref,
                date_col=date_col,
                value_col=value_col,
                period=period,
                aggregate=aggregate,
                window_years=window_years,
                period_mode=period_mode,
                sort_desc=sort_desc,
            ),
            compute_feature_correlations=compute_feature_correlations,
            build_correlation_matrix_table=build_correlation_matrix_table,
            fit_linear_regression_weights=fit_linear_regression_weights,

            # ----- diagnose -----
            diagnose_format_inconsistencies=diagnose_format_inconsistencies,
        )
