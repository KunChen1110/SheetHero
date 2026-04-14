"""Excel reading helpers."""

from typing import Any, Dict, List, Optional


class ExcelReader:
    """Read-only helpers for workbook data access."""

    def __init__(self, workbook):
        self.workbook = workbook

    def get_sheet(self, sheet_name: Optional[str] = None):
        """Get worksheet by name, or active sheet if no name provided."""
        if sheet_name is None:
            return self.workbook.active
        if sheet_name in self.workbook.sheetnames:
            return self.workbook[sheet_name]
        raise ValueError(
            f"Sheet '{sheet_name}' not found. Available: {self.workbook.sheetnames}"
        )

    def inspector(self, range_ref: str, sheet_name: Optional[str] = None) -> List[List]:
        """
        Read cell values from a range and return as 2D list.
        """
        sheet = self.get_sheet(sheet_name)
        cell_range = sheet[range_ref]

        if hasattr(cell_range, 'value'):
            return [[cell_range.value]]

        result = []
        for row in cell_range:
            row_values = [cell.value for cell in row]
            result.append(row_values)
        return result

    def inspector_attribute(self, range_ref: str, attributes: List[str],
                            sheet_name: Optional[str] = None) -> Dict:
        """
        Read formatting attributes from a range of cells.
        """
        print(
            f"🔎 [read_range_attribute] Reading attributes {attributes} for range {range_ref} "
            f"in sheet '{sheet_name}'"
        )

        if not attributes:
            return {"error": "No attributes specified"}

        valid_attributes = ["color", "font", "formula"]
        invalid_attrs = [attr for attr in attributes if attr not in valid_attributes]
        if invalid_attrs:
            return {
                "error": f"Invalid attributes: {invalid_attrs}. Valid options: {valid_attributes}"
            }

        try:
            sheet = self.get_sheet(sheet_name)
            cell_range = sheet[range_ref]
        except (ValueError, KeyError) as e:
            return {"error": str(e)}

        if hasattr(cell_range, 'coordinate'):
            cells_to_process = [cell_range]
        else:
            cells_to_process = []
            for row in cell_range:
                if hasattr(row, '__iter__'):
                    cells_to_process.extend(row)
                else:
                    cells_to_process.append(row)

        result_attributes = {}

        for attr in attributes:
            result_attributes[attr] = {}

            for cell in cells_to_process:
                cell_coord = cell.coordinate
                attr_value = None

                if attr == "color":
                    if (
                        cell.fill
                        and cell.fill.fgColor
                        and cell.fill.fgColor.rgb != '00000000'
                    ):
                        attr_value = f"#{cell.fill.fgColor.rgb}"

                elif attr == "font":
                    font_details = []
                    if cell.font:
                        if cell.font.color and cell.font.color.rgb != '00000000':
                            font_details.append(f"color:#{cell.font.color.rgb}")
                        if cell.font.name:
                            font_details.append(f"name:{cell.font.name}")
                        if cell.font.size:
                            font_details.append(f"size:{cell.font.size}")
                        if cell.font.bold:
                            font_details.append("bold:True")
                        if cell.font.italic:
                            font_details.append("italic:True")
                        if cell.font.underline and cell.font.underline != 'none':
                            font_details.append(f"underline:{cell.font.underline}")

                    attr_value = "; ".join(font_details) if font_details else None

                elif attr == "formula":
                    if cell.data_type == 'f' and cell.value:
                        attr_value = str(cell.value)

                if attr_value is not None:
                    result_attributes[attr][cell_coord] = attr_value

        return {
            "range": range_ref,
            "sheet": sheet_name or sheet.title,
            "attributes": result_attributes,
            "total_cells_processed": len(cells_to_process)
        }

    def get_sheet_as_dataframe(self, sheet_name: Optional[str] = None,
                               header_row: int = 1, max_rows: Optional[int] = None):
        """
        Convert sheet to pandas DataFrame for data analysis.
        """
        import pandas as pd
        sheet = self.get_sheet(sheet_name)

        data = []
        for i, row in enumerate(sheet.iter_rows(values_only=True), 1):
            if max_rows and i > max_rows:
                break
            data.append(row)

        if not data:
            return pd.DataFrame()

        if header_row > 0 and len(data) >= header_row:
            headers = data[header_row - 1]
            data_rows = data[header_row:]
            df = pd.DataFrame(data_rows, columns=headers)
        else:
            df = pd.DataFrame(data)

        return df
