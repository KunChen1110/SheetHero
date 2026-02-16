"""Excel context builder for token-budgeted summaries."""

import os
from typing import Any, Dict

from ...log.logger_registry import LoggerRegistry

logger = LoggerRegistry.setup_logger(__name__)


class ExcelContextBuilder:
    """Builds markdown summaries of Excel workbooks under a token budget."""

    def __init__(self, excel_paths, workbooks: Dict[str, Any]):
        self.excel_paths = excel_paths
        self.workbooks = workbooks

    def build(self, total_token_budget: int = 50000) -> str:
        """
        Generate a markdown summary of Excel sheets for AI context.
        """
        try:
            workbooks = self.workbooks or {}
            overview_parts = []

            if len(workbooks) > 1:
                overview_parts.append(
                    f"📊 **Multiple Excel Files Overview ({len(workbooks)} files)**\n"
                )
            else:
                first_path = self.excel_paths[0] if self.excel_paths else "unknown"
                overview_parts.append(
                    f"📊 **Excel File Overview: {os.path.basename(first_path)}**\n"
                )

            for excel_path, workbook in workbooks.items():
                file_parts = []
                file_parts.append(f"\n{'=' * 60}")
                file_parts.append(f"📁 **File: {os.path.basename(excel_path)}**")
                file_parts.append(f"**Full Path:** {excel_path}")
                file_parts.append(f"**Total Sheets:** {len(workbook.sheetnames)}\n")

                for sheet_name in workbook.sheetnames:
                    sheet = workbook[sheet_name]
                    sheet_parts = []

                    sheet_parts.append(
                        f"\n**📄 Sheet: '{sheet_name}'** (in {os.path.basename(excel_path)})"
                    )
                    sheet_parts.append(
                        f"- Dimensions: {sheet.max_row} rows × {sheet.max_column} columns"
                    )

                    head_result = self._get_sheet_head(
                        sheet,
                        max_rows=5,
                        max_cols=min(sheet.max_column, 20)
                    )

                    sheet_parts.append(
                        f"- Columns (header row): {', '.join(head_result['headers'])}"
                    )
                    sheet_parts.append(
                        f"- Head ({head_result['rows_shown']} rows shown, "
                        f"{head_result['cols_shown']} of {sheet.max_column} columns):"
                    )

                    if head_result['rows_shown'] > 0 and head_result['headers']:
                        markdown_rows = []
                        markdown_rows.append(f"| {' | '.join(head_result['headers'])} |")
                        markdown_rows.append(
                            f"| {' | '.join(['---'] * len(head_result['headers']))} |"
                        )
                        for row_data in head_result['rows']:
                            markdown_rows.append(f"| {' | '.join(row_data)} |")
                        sheet_parts.append("  " + "\n".join(markdown_rows))
                    else:
                        sheet_parts.append("  (no data)")

                    file_parts.extend(sheet_parts)

                overview_parts.extend(file_parts)

            return "\n".join(overview_parts)

        except Exception as e:
            logger.error(f"Error generating Excel overview: {str(e)}")
            return f"❌ Error generating Excel overview: {str(e)}"

    def _get_sheet_head(self, sheet, max_rows: int = 5, max_cols: int = 20) -> Dict[str, Any]:
        """Return header row + first N data rows, trimmed to max cols."""
        max_data_cols = min(max_cols, sheet.max_column)
        headers = []
        rows = []

        if sheet.max_row < 1 or max_data_cols < 1:
            return {
                "headers": [],
                "rows": [],
                "rows_shown": 0,
                "cols_shown": 0,
            }

        for col_idx in range(1, max_data_cols + 1):
            cell_value = sheet.cell(row=1, column=col_idx).value
            headers.append(self._sanitize_cell(cell_value))

        rows_collected = 0
        for row_idx in range(2, sheet.max_row + 1):
            row_cells = []
            has_value = False
            for col_idx in range(1, max_data_cols + 1):
                cell_value = sheet.cell(row=row_idx, column=col_idx).value
                cell_text = self._sanitize_cell(cell_value)
                if cell_text.strip():
                    has_value = True
                row_cells.append(cell_text)
            if not has_value:
                continue
            rows.append(row_cells)
            rows_collected += 1
            if rows_collected >= max_rows:
                break

        return {
            "headers": headers,
            "rows": rows,
            "rows_shown": len(rows),
            "cols_shown": max_data_cols,
        }

    @staticmethod
    def _sanitize_cell(value: Any) -> str:
        if value is None:
            text = ""
        else:
            text = str(value)
        return (
            text.replace("|", "\\|")
            .replace("\n", " ")
            .replace("\r", " ")
        )
