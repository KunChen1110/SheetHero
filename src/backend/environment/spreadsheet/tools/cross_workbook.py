"""Spreadsheet domain helper functions."""

import os

from ..world import SpreadsheetWorld


def get_workbook(world: SpreadsheetWorld, file_path: str):
    """Get a workbook by full path or by matching filename."""
    if file_path in world.workbooks:
        return world.workbooks[file_path]
    for path, wb in world.workbooks.items():
        if os.path.basename(path) == os.path.basename(file_path):
            return wb
    raise ValueError(
        f"Workbook not found: {file_path}. Available: {list(world.workbooks.keys())}"
    )


def list_all_workbooks(world: SpreadsheetWorld):
    """List all workbook paths."""
    return list(world.workbooks.keys())


def get_sheet_from_workbook(world: SpreadsheetWorld, file_path: str, sheet_name: str):
    """Get a sheet by workbook path and sheet name."""
    wb = get_workbook(world, file_path)
    if sheet_name in wb.sheetnames:
        return wb[sheet_name]
    raise ValueError(
        f"Sheet '{sheet_name}' not found in {file_path}. "
        f"Available: {wb.sheetnames}"
    )


def inspector_multi(world: SpreadsheetWorld, file_path: str, range_ref: str,
                    sheet_name: str | None = None):
    """Inspect a cell range from a specific workbook."""
    wb = get_workbook(world, file_path)
    if sheet_name is None:
        sheet = wb.active
    else:
        if sheet_name not in wb.sheetnames:
            raise ValueError(
                f"Sheet '{sheet_name}' not found in {os.path.basename(file_path)}. "
                f"Available sheets: {wb.sheetnames}"
            )
        sheet = wb[sheet_name]
    cell_range = sheet[range_ref]
    if hasattr(cell_range, 'value'):
        return [[cell_range.value]]
    return [[cell.value for cell in row] for row in cell_range]
