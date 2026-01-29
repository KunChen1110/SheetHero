"""Excel search helpers."""

from typing import Any, Dict, List, Optional


class ExcelSearch:
    """Search helpers for worksheet values."""

    def __init__(self, workbook, reader):
        self.workbook = workbook
        self.reader = reader

    def search(self, value: Any, sheet_name: Optional[str] = None,
               case_sensitive: bool = False, search_type: str = "partial") -> List[Dict]:
        """
        Search for cells containing a specific value across the sheet.
        """
        sheet = self.reader.get_sheet(sheet_name)
        matches = []

        valid_search_types = ["partial", "whole", "strip"]
        if search_type not in valid_search_types:
            raise ValueError(
                f"Invalid search_type '{search_type}'. Valid options: {valid_search_types}"
            )

        search_value = str(value) if case_sensitive else str(value).lower()

        for row in sheet.iter_rows():
            for cell in row:
                if cell.value is not None:
                    cell_str = str(cell.value)

                    if not case_sensitive:
                        cell_str = cell_str.lower()

                    is_match = False

                    if search_type == "partial":
                        is_match = search_value in cell_str
                    elif search_type == "whole":
                        is_match = search_value == cell_str
                    elif search_type == "strip":
                        stripped_cell_str = cell_str.strip()
                        is_match = search_value == stripped_cell_str

                    if is_match:
                        matches.append({
                            'coordinate': cell.coordinate,
                            'value': cell.value,
                            'row': cell.row,
                            'column': cell.column
                        })

        return matches
