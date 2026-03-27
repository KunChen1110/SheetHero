"""Output contract parsing and saved-result checks."""

from __future__ import annotations

import re
from typing import Dict, Optional


class OutputContractChecker:
    """Parse contract flags and validate execution output signals."""

    @staticmethod
    def extract_saved_path_from_result(execution_result: str) -> Optional[str]:
        """Extract saved file path from executor stdout."""
        if not execution_result:
            return None
        # Match with or without emoji/prefix: "Workbook saved to: /path".
        m = re.search(r"Workbook saved to:\s*(.+?)(?:\n|$)", execution_result)
        if m:
            path = m.group(1).strip()
            if path and not path.startswith("("):
                return path
        m = re.search(r"SAVED_FILE:\s*(.+?)(?:\n|$)", execution_result)
        if m:
            path = m.group(1).strip()
            if path:
                return path
        return None

    @staticmethod
    def _extract_rows_written(execution_result: str) -> list[int]:
        """Parse row counts from helper logs like 'Wrote N rows to Output!A1:B10'."""
        if not execution_result:
            return []
        matches = re.findall(r"Wrote\s+(\d+)\s+rows\s+to", execution_result, flags=re.IGNORECASE)
        rows = []
        for m in matches:
            try:
                rows.append(int(m))
            except Exception:
                continue
        return rows

    @staticmethod
    def _column_letters_to_index(col: str) -> int:
        total = 0
        for ch in (col or "").upper():
            if "A" <= ch <= "Z":
                total = total * 26 + (ord(ch) - ord("A") + 1)
        return total

    @staticmethod
    def _index_to_column_letters(index: int) -> str:
        letters = []
        value = index
        while value > 0:
            value, remainder = divmod(value - 1, 26)
            letters.append(chr(ord("A") + remainder))
        return "".join(reversed(letters)) or "A"

    @classmethod
    def _extract_write_ranges(cls, execution_result: str) -> list[tuple[str, int, int, int, int]]:
        """Parse helper write rectangles like 'Wrote 7 rows to Output!A1:E7'."""
        if not execution_result:
            return []
        ranges: list[tuple[str, int, int, int, int]] = []
        pattern = r"Wrote\s+\d+\s+rows\s+to\s+([^!\n]+)!([A-Z]+)(\d+):([A-Z]+)(\d+)"
        for sheet_name, start_col, start_row, end_col, end_row in re.findall(
            pattern,
            execution_result,
            flags=re.IGNORECASE,
        ):
            start_idx = cls._column_letters_to_index(start_col)
            end_idx = cls._column_letters_to_index(end_col)
            try:
                start_row_int = int(start_row)
                end_row_int = int(end_row)
            except Exception:
                continue
            if not start_idx or not end_idx:
                continue
            ranges.append((sheet_name.strip(), start_row_int, start_idx, end_row_int, end_idx))
        return ranges

    @staticmethod
    def _ranges_overlap(
        start_row: int,
        start_col: int,
        end_row: int,
        end_col: int,
        other_start_row: int,
        other_start_col: int,
        other_end_row: int,
        other_end_col: int,
    ) -> bool:
        rows_overlap = not (end_row < other_start_row or other_end_row < start_row)
        cols_overlap = not (end_col < other_start_col or other_end_col < start_col)
        return rows_overlap and cols_overlap

    @classmethod
    def _find_overlapping_write_ranges(
        cls,
        execution_result: str,
    ) -> list[tuple[tuple[str, int, int, int, int], tuple[str, int, int, int, int]]]:
        ranges = cls._extract_write_ranges(execution_result)
        overlaps: list[tuple[tuple[str, int, int, int, int], tuple[str, int, int, int, int]]] = []
        for idx, current in enumerate(ranges):
            current_sheet, current_start_row, current_start_col, current_end_row, current_end_col = current
            for previous in ranges[:idx]:
                prev_sheet, prev_start_row, prev_start_col, prev_end_row, prev_end_col = previous
                if current_sheet != prev_sheet:
                    continue
                if cls._ranges_overlap(
                    current_start_row,
                    current_start_col,
                    current_end_row,
                    current_end_col,
                    prev_start_row,
                    prev_start_col,
                    prev_end_row,
                    prev_end_col,
                ):
                    overlaps.append((previous, current))
        return overlaps

    @classmethod
    def _format_write_range(cls, write_range: tuple[str, int, int, int, int]) -> str:
        sheet_name, start_row, start_col, end_row, end_col = write_range
        start_cell = f"{cls._index_to_column_letters(start_col)}{start_row}"
        end_cell = f"{cls._index_to_column_letters(end_col)}{end_row}"
        return f"{sheet_name}!{start_cell}:{end_cell}"

    @staticmethod
    def _extract_highlight_rows(execution_result: str) -> list[int]:
        """Parse highlighted row numbers from helper logs."""
        if not execution_result:
            return []
        matches = re.findall(
            r"Highlighted row\(s\)\s*\[([^\]]*)\]",
            execution_result,
            flags=re.IGNORECASE,
        )
        parsed: list[int] = []
        for raw in matches:
            for token in re.findall(r"-?\d+", raw):
                try:
                    parsed.append(int(token))
                except Exception:
                    continue
        return parsed

    @staticmethod
    def _extract_summary_rows(execution_result: str) -> list[int]:
        """Parse summary row positions from helper logs."""
        if not execution_result:
            return []
        rows: list[int] = []
        for raw in re.findall(r"Added summary row at row\s+(\d+)", execution_result, flags=re.IGNORECASE):
            try:
                rows.append(int(raw))
            except Exception:
                continue
        return rows

    @classmethod
    def has_meaningful_output_rows(cls, execution_result: str) -> bool:
        """Require at least 2 written rows (header + >=1 data row)."""
        rows = cls._extract_rows_written(execution_result)
        if not rows:
            return False
        return max(rows) >= 2

    @staticmethod
    def _parse_flag(understanding_output: str, key: str) -> Optional[bool]:
        """Parse YES/NO contract flags from understanding output."""
        if not understanding_output:
            return None
        pattern = rf"(?:\*\*)?\s*{re.escape(key)}\s*(?:\*\*)?\s*:\s*(YES|NO|TRUE|FALSE)"
        m = re.search(pattern, understanding_output, flags=re.IGNORECASE)
        if not m:
            return None
        value = m.group(1).strip().upper()
        return value in {"YES", "TRUE"}

    @classmethod
    def extract_output_contract(cls, understanding_output: str) -> Dict[str, Optional[bool]]:
        """Extract structured output intent contract from understanding stage text."""
        return {
            "requires_detailed_table": cls._parse_flag(understanding_output, "requires_detailed_table"),
            "requires_highlight": cls._parse_flag(understanding_output, "requires_highlight"),
            "requires_summary_metrics": cls._parse_flag(understanding_output, "requires_summary_metrics"),
        }

    @staticmethod
    def _has_summary_write_signal_from_code(code_action: str) -> bool:
        """Detect summary-write intent in generated code when runtime logs are sparse."""
        if not code_action:
            return False
        lower_code = code_action.lower()
        if "add_summary_row(" in lower_code:
            return True
        if '["metric", "value"]' in lower_code or "['metric', 'value']" in lower_code:
            return True
        if "write_dataframe_to_sheet(" in lower_code and ("summary" in lower_code or "metric" in lower_code):
            return True
        return False

    @classmethod
    def build_output_intent_feedback(
        cls,
        execution_result: str,
        output_contract: Dict[str, Optional[bool]],
        code_action: str = "",
    ) -> Optional[str]:
        """Validate that saved output matches question intent."""
        need_detail = output_contract.get("requires_detailed_table") is True
        need_highlight = output_contract.get("requires_highlight") is True
        need_summary = output_contract.get("requires_summary_metrics") is True

        rows = cls._extract_rows_written(execution_result)
        max_rows = max(rows) if rows else 0
        highlight_rows = cls._extract_highlight_rows(execution_result)
        summary_rows = cls._extract_summary_rows(execution_result)
        overlapping_ranges = cls._find_overlapping_write_ranges(execution_result)
        lower_result = (execution_result or "").lower()

        if overlapping_ranges:
            previous, current = overlapping_ranges[0]
            return (
                "OUTPUT_INTENT_MISMATCH_OFFLINE: output writes overlap in the same sheet.\n"
                f"- Existing range: {cls._format_write_range(previous)}\n"
                f"- Overlapping later range: {cls._format_write_range(current)}\n"
                "- Do not write summary or secondary blocks inside an existing detailed-table range.\n"
                "- Place later blocks strictly below or to the right of earlier output."
            )

        if need_detail and max_rows < 2:
            return (
                "OUTPUT_INTENT_MISMATCH_OFFLINE: question requires detailed table output, "
                "but current saved output does not show a header plus at least one data row.\n"
                "- Rebuild output as: detailed table first, then summary metrics if needed.\n"
                "- Do not output only a metric block without real table rows."
            )

        if need_highlight and "highlighted row(s)" not in lower_result and "no_highlight_rows:" not in lower_result:
            return (
                "OUTPUT_INTENT_MISMATCH_OFFLINE: question requires highlighting (for example max day in red), "
                "but no highlight evidence found.\n"
                "- After writing detailed table, call:\n"
                "  highlight_rows(\"Output\", row_numbers, {\"fill_color\": \"red\"})\n"
                "- Do not use HTML tags for highlighting."
            )

        if need_highlight and highlight_rows and max_rows > 0:
            invalid_rows = [r for r in highlight_rows if r < 2 or r > max_rows + 2]
            if invalid_rows:
                invalid_str = ", ".join(str(v) for v in invalid_rows[:5])
                return (
                    "OUTPUT_INTENT_MISMATCH_OFFLINE: highlighted row numbers are out of expected table range.\n"
                    f"- Invalid highlighted rows: {invalid_str}\n"
                    f"- Output table rows appear to be around 1..{max_rows}\n"
                    "- Convert DataFrame indices to Output row numbers with header offset:\n"
                    "  row_numbers = [i + 2 for i in idx_list]\n"
                    "- Pass a flat list of ints to highlight_rows(...)."
                )

        if need_summary:
            has_summary_signal = (
                "added summary row" in lower_result
                or len(rows) >= 2
                or cls._has_summary_write_signal_from_code(code_action)
                or (need_detail and max_rows >= 20)
            )
            if not has_summary_signal:
                return (
                    "OUTPUT_INTENT_MISMATCH_OFFLINE: summary metrics are required but no summary write evidence found.\n"
                    "- Add a summary block (Total / Average etc.) after detailed table.\n"
                    "- Use write_dataframe_to_sheet(summary_data, \"Output\", start_cell) or add_summary_row(...)."
                )
            if need_detail and summary_rows and max_rows > 0:
                overlapping = [r for r in summary_rows if r <= max_rows]
                if overlapping:
                    bad = ", ".join(str(v) for v in overlapping[:5])
                    return (
                        "OUTPUT_INTENT_MISMATCH_OFFLINE: summary row overlaps the detailed table.\n"
                        f"- Overlapping summary row(s): {bad}\n"
                        f"- Detailed table currently appears to end around row {max_rows}.\n"
                        "- Write summary strictly below the detailed table, for example at `len(detail_data) + 2`."
                    )

        return None

    @staticmethod
    def detect_quality_risk(execution_result: str) -> Optional[str]:
        """Catch suspicious 'saved successfully but logic still wrong' signals."""
        if not execution_result:
            return None
        lower_result = execution_result.lower()

        has_missing_dependency_tasks = (
            "missing tasks in dependencies" in lower_result
            or "in dependencies is not found in tasks" in lower_result
            or "unknown dependency" in lower_result
        )
        if has_missing_dependency_tasks:
            return (
                "OUTPUT_QUALITY_RISK_OFFLINE: schedule/dependency consistency warning detected in execution output.\n"
                "- Some dependency rows reference task IDs not present in task table.\n"
                "- Do NOT finalize yet; clean/normalize dependency rows first (strip suffix markers, drop notes/examples, ignore NaN predecessor).\n"
                "- Rebuild DAG and ensure every dependency endpoint exists in task_id_set before saving."
            )

        if "cycle detected" in lower_result and "not a dag" in lower_result:
            return (
                "OUTPUT_QUALITY_RISK_OFFLINE: graph cycle warning still exists.\n"
                "- Do not finalize output until DAG build and topological sort pass."
            )

        return None
