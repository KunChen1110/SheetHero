"""Spreadsheet domain loader."""

import csv
import os
from typing import Optional

from openpyxl import Workbook, load_workbook

from .world import SpreadsheetWorld
from ...log.logger_registry import LoggerRegistry


logger = LoggerRegistry.setup_logger(__name__)


def load_world(paths: list[str], output_path: str, progress_logger=None) -> SpreadsheetWorld:
    """Load spreadsheet files into a world object."""
    workbooks = {}
    for path in paths:
        logger.info(f"Loading spreadsheet file: {path}")
        workbook = ExcelLoader.load_workbook_from_path(path)
        workbooks[path] = workbook

    if progress_logger:
        progress_logger.log(
            f"📊 [Excel] Loaded {len(paths)} file(s)"
        )

    primary_path = paths[0] if paths else ""
    return SpreadsheetWorld(workbooks, output_path, primary_path)


class ExcelLoader:
    """Loads Excel and CSV files into openpyxl workbooks."""

    @staticmethod
    def load_workbook_from_path(excel_path: str):
        _, ext = os.path.splitext(excel_path)
        ext = ext.lower()
        excel_extensions = {".xlsx", ".xlsm", ".xltx", ".xltm"}

        if ext in excel_extensions:
            return load_workbook(excel_path, data_only=True)

        if ext == ".csv":
            return ExcelLoader.create_workbook_from_csv(excel_path)

        raise ValueError(
            f"Unsupported file extension '{ext}' for {excel_path}. "
            "Supported formats: .xlsx, .xlsm, .xltx, .xltm, .csv"
        )

    @staticmethod
    def create_workbook_from_csv(csv_path: str) -> Workbook:
        workbook = Workbook()
        sheet = workbook.active

        sheet_name = os.path.splitext(os.path.basename(csv_path))[0][:31] or "Sheet1"
        sheet.title = sheet_name

        with open(csv_path, newline="", encoding="utf-8-sig") as csv_file:
            reader = csv.reader(csv_file)
            for row in reader:
                processed_row = [ExcelLoader.infer_cell_value(value) for value in row]
                sheet.append(processed_row)

        return workbook

    @staticmethod
    def infer_cell_value(value: Optional[str]):
        if value is None:
            return value

        stripped = value.strip()
        if stripped == "":
            return ""

        try:
            if '.' not in stripped:
                return int(stripped)
            return float(stripped)
        except ValueError:
            return value
