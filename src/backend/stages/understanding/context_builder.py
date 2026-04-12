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
            workbook_count = len(workbooks)
            max_preview_rows, max_preview_cols = self._preview_limits(workbook_count, total_token_budget)
            header_only_mode = self._use_header_only_mode(workbook_count, total_token_budget)

            if workbook_count > 1:
                overview_parts.append(
                    f"📊 **Multiple Excel Files Overview ({workbook_count} files)**\n"
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

                    preview = self._get_sheet_preview(
                        sheet,
                        max_rows=max_preview_rows,
                        max_cols=min(sheet.max_column, max_preview_cols)
                    )

                    if preview["candidate_headers"]:
                        sheet_parts.append(
                            f"- Candidate headers: {', '.join(preview['candidate_headers'])}"
                        )
                    if not header_only_mode:
                        sheet_parts.append(
                            f"- Preview rows ({preview['rows_shown']} shown, {preview['cols_shown']} of {sheet.max_column} columns):"
                        )
                        if preview["rows"]:
                            for label, row_data in preview["rows"]:
                                sheet_parts.append(f"  - {label}: {' | '.join(row_data)}")
                        else:
                            sheet_parts.append("  (no data)")

                    file_parts.extend(sheet_parts)

                overview_parts.extend(file_parts)

            return "\n".join(overview_parts)

        except Exception as e:
            logger.error(f"Error generating Excel overview: {str(e)}")
            return f"❌ Error generating Excel overview: {str(e)}"

    @staticmethod
    def _preview_limits(workbook_count: int, total_token_budget: int) -> tuple[int, int]:
        if workbook_count >= 5 or total_token_budget <= 6000:
            return 0, 6
        if workbook_count >= 3:
            return 4, 10
        return 5, 12

    @staticmethod
    def _use_header_only_mode(workbook_count: int, total_token_budget: int) -> bool:
        return workbook_count >= 5 or total_token_budget <= 6000

    def _get_sheet_preview(self, sheet, max_rows: int = 4, max_cols: int = 10) -> Dict[str, Any]:
        """Return compact preview rows, preserving raw top-of-sheet structure."""
        max_data_cols = min(max_cols, sheet.max_column)
        rows = []
        candidate_headers = []

        if sheet.max_row < 1 or max_data_cols < 1:
            return {
                "candidate_headers": [],
                "rows": [],
                "rows_shown": 0,
                "cols_shown": 0,
            }

        first_row_values = []
        for col_idx in range(1, max_data_cols + 1):
            cell_value = sheet.cell(row=1, column=col_idx).value
            first_row_values.append(self._sanitize_cell(cell_value))
        candidate_headers = [value for value in first_row_values if value][:max_data_cols]

        rows_collected = 0
        for row_idx in range(1, sheet.max_row + 1):
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
            rows.append((f"r{row_idx}", row_cells))
            rows_collected += 1
            if rows_collected >= max_rows:
                break

        return {
            "candidate_headers": candidate_headers,
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
