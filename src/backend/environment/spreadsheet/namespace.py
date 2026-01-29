# environment/spreadsheet/namespace.py

from types import SimpleNamespace

from .world import SpreadsheetWorld
# import tools
from .tools import (
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

        return SimpleNamespace(
            # ----- read / inspect -----
            get_sheet=self.reader.get_sheet,
            get_sheet_as_dataframe=self.reader.get_sheet_as_dataframe,
            search=self.searcher.search,

            list_sheets=self.sheet_info.list_sheets,
            get_sheet_info=self.sheet_info.get_sheet_info,
            get_all_sheets_info=self.sheet_info.get_all_sheets_info,
            read_multiple_sheets=self.sheet_info.read_multiple_sheets,

            inspector=self.reader.inspector,
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
            save_workbook=self.output.save_workbook,
            create_output_sheet=self.output.create_output_sheet,
            write_dataframe_to_sheet=self.output.write_dataframe_to_sheet,
            highlight_rows=self.output.highlight_rows,
            save_workbook_to=self.output.save_workbook_to,
            add_summary_row=self.output.add_summary_row,

            # ----- cross-workbook helpers -----
            get_workbook=lambda fp: get_workbook(w, fp),
            list_all_workbooks=lambda: list_all_workbooks(w),
            get_sheet_from_workbook=lambda fp, sn: get_sheet_from_workbook(w, fp, sn),
            inspector_multi=lambda fp, rr, sn=None: inspector_multi(w, fp, rr, sn),
        )
