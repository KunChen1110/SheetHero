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
        lower_result = (execution_result or "").lower()

        if need_detail and max_rows < 6:
            return (
                "OUTPUT_INTENT_MISMATCH_OFFLINE: question requires detailed table output, "
                "but current saved output is too small (likely metric-only).\n"
                "- Rebuild output as: detailed merged table first, then summary metrics.\n"
                "- Do not output only `Metric|Value` for merge/combine table tasks."
            )

        if need_highlight and "highlighted row(s)" not in lower_result:
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
