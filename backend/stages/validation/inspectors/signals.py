"""Validation parsing helpers for runtime signals and code snippets."""

import ast
import re
from typing import Any


class ValidationSignalParserMixin:
    @staticmethod
    def _parse_output_contract_flag(understanding_output: str, key: str) -> bool | None:
        if not understanding_output:
            return None
        pattern = rf"(?:\*\*)?\s*{re.escape(key)}\s*(?:\*\*)?\s*:\s*(YES|NO|TRUE|FALSE)"
        match = re.search(pattern, understanding_output, flags=re.IGNORECASE)
        if not match:
            return None
        return match.group(1).strip().upper() in {"YES", "TRUE"}

    @staticmethod
    def _extract_rows_written(text: str) -> list[int]:
        if not text:
            return []
        out: list[int] = []
        for raw in re.findall(r"Wrote\s+(\d+)\s+rows\s+to", text, flags=re.IGNORECASE):
            try:
                out.append(int(raw))
            except Exception:
                continue
        return out

    @staticmethod
    def _column_letters_to_index(col: str) -> int:
        total = 0
        for ch in (col or "").upper():
            if "A" <= ch <= "Z":
                total = total * 26 + (ord(ch) - ord("A") + 1)
        return total

    @classmethod
    def _extract_written_column_counts(cls, text: str) -> list[int]:
        if not text:
            return []
        counts: list[int] = []
        for start_col, end_col in re.findall(
            r"Wrote\s+\d+\s+rows\s+to\s+[A-Za-z0-9_ ]+!([A-Z]+)\d+:([A-Z]+)\d+",
            text,
            flags=re.IGNORECASE,
        ):
            start_idx = cls._column_letters_to_index(start_col)
            end_idx = cls._column_letters_to_index(end_col)
            if start_idx and end_idx and end_idx >= start_idx:
                counts.append(end_idx - start_idx + 1)
        return counts

    @classmethod
    def _extract_write_ranges(cls, text: str) -> list[tuple[str, int, int, int, int]]:
        if not text:
            return []
        ranges: list[tuple[str, int, int, int, int]] = []
        pattern = r"Wrote\s+\d+\s+rows\s+to\s+([^!\n]+)!([A-Z]+)(\d+):([A-Z]+)(\d+)"
        for sheet_name, start_col, start_row, end_col, end_row in re.findall(pattern, text, flags=re.IGNORECASE):
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
        text: str,
    ) -> list[tuple[tuple[str, int, int, int, int], tuple[str, int, int, int, int]]]:
        ranges = cls._extract_write_ranges(text)
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

    @staticmethod
    def _index_to_column_letters(index: int) -> str:
        letters: list[str] = []
        value = index
        while value > 0:
            value, remainder = divmod(value - 1, 26)
            letters.append(chr(ord("A") + remainder))
        return "".join(reversed(letters)) or "A"

    @classmethod
    def _format_write_range(cls, write_range: tuple[str, int, int, int, int]) -> str:
        sheet_name, start_row, start_col, end_row, end_col = write_range
        start_cell = f"{cls._index_to_column_letters(start_col)}{start_row}"
        end_cell = f"{cls._index_to_column_letters(end_col)}{end_row}"
        return f"{sheet_name}!{start_cell}:{end_cell}"

    @staticmethod
    def _extract_highlight_rows(text: str) -> list[int]:
        if not text:
            return []
        rows: list[int] = []
        blocks = re.findall(r"Highlighted row\(s\)\s*\[([^\]]*)\]", text, flags=re.IGNORECASE)
        for raw in blocks:
            for token in re.findall(r"-?\d+", raw):
                try:
                    rows.append(int(token))
                except Exception:
                    continue
        return rows

    @staticmethod
    def _extract_summary_rows(text: str) -> list[int]:
        if not text:
            return []
        rows: list[int] = []
        for raw in re.findall(r"Added summary row at row\s+(\d+)", text, flags=re.IGNORECASE):
            try:
                rows.append(int(raw))
            except Exception:
                continue
        return rows

    @staticmethod
    def _has_summary_write_signal_from_code(code_text: str) -> bool:
        if not code_text:
            return False
        lower_code = code_text.lower()
        if "add_summary_row(" in lower_code:
            return True
        if '["metric", "value"]' in lower_code or "['metric', 'value']" in lower_code:
            return True
        if "write_dataframe_to_sheet(" in lower_code and ("summary" in lower_code or "metric" in lower_code):
            return True
        return False

    @staticmethod
    def _extract_reported_columns(text: str) -> list[str]:
        if not text:
            return []
        matches = re.findall(r"Columns:\s*(\[[^\]]*\])", text)
        for raw in reversed(matches):
            try:
                parsed = ast.literal_eval(raw)
            except Exception:
                continue
            if isinstance(parsed, list):
                return [str(v).strip() for v in parsed if str(v).strip()]
        return []

    @staticmethod
    def _header_is_target_like(header: str) -> bool:
        lowered = (header or "").strip().lower()
        return any(marker in lowered for marker in ("sales", "target", "label", "outcome", "revenue", "y"))

    @staticmethod
    def _header_is_non_feature_like(header: str) -> bool:
        lowered = (header or "").strip().lower()
        return any(marker in lowered for marker in ("id", "date", "time", "timestamp", "note", "comment"))

    def _expected_regression_predictors(self, columns: list[str]) -> list[str]:
        predictors: list[str] = []
        for header in columns:
            if self._header_is_target_like(header):
                continue
            if self._header_is_non_feature_like(header):
                continue
            predictors.append(header)
        return predictors

    @staticmethod
    def _extract_feature_cols_from_code(code_text: str) -> list[str]:
        if not code_text:
            return []
        match = re.search(r"feature_cols\s*=\s*\[([^\]]*)\]", code_text, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            return []
        body = match.group(1)
        return [s.strip() for s in re.findall(r"['\"]([^'\"]+)['\"]", body)]

    @staticmethod
    def _extract_weight_labels(text: str) -> list[str]:
        if not text:
            return []
        match = re.search(r"Weights:\s*(\[\[.*\]\])", text, flags=re.IGNORECASE)
        if not match:
            return []
        try:
            parsed = ast.literal_eval(match.group(1).strip())
        except Exception:
            return []
        labels: list[str] = []
        for row in parsed[1:]:
            if isinstance(row, (list, tuple)) and row:
                labels.append(str(row[0]).strip())
        return labels

    @staticmethod
    def _code_uses_literal_xlsx_name(code_text: str) -> bool:
        if not code_text:
            return False
        return bool(re.search(r"['\"][^'\"]+\.xlsx['\"]", code_text, flags=re.IGNORECASE))

    @staticmethod
    def _issues_only_reference_earlier_failures(issues: list[str]) -> bool:
        if not issues:
            return False
        failure_markers = (
            "syntax error",
            "execution error",
            "nameerror",
            "typeerror",
            "attributeerror",
            "keyerror",
            "traceback",
        )
        normalized = [str(issue or "").strip().lower() for issue in issues if str(issue or "").strip()]
        if not normalized:
            return False
        return all(any(marker in issue for marker in failure_markers) for issue in normalized)
