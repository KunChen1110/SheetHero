"""Spreadsheet domain world representation."""

from ..base.world import World


class SpreadsheetWorld(World):
    """Represents the spreadsheet domain data and metadata."""

    def __init__(self, workbooks: dict, output_path: str, primary_path: str):
        self.workbooks = workbooks
        self.output_path = output_path
        self.primary_path = primary_path

    @property
    def primary_workbook(self):
        return self.workbooks[self.primary_path]
