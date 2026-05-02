"""Workbook grounding helpers for execution runtime."""

from __future__ import annotations

import os
import re
from typing import Optional

_PERCENT_HINT_PATTERN = re.compile(r"pct|percent(?:age)?|%", re.IGNORECASE)


class WorkbookGrounding:
    """Provide runtime schema/file grounding utilities."""

    def __init__(self, sandbox) -> None:
        self.sandbox = sandbox

    def available_workbook_basenames(self) -> list[str]:
        """Return loaded workbook base names for repair hints."""
        try:
            workbooks = self.sandbox.workbooks or {}
            return [os.path.basename(str(path)) for path in workbooks.keys()]
        except Exception:
            return []

    def build_schema_snapshot(self) -> str:
        """Build a compact schema snapshot (sheet + header row) from loaded workbooks."""
        try:
            workbooks = self.sandbox.workbooks or {}
            lines: list[str] = []
            for path, wb in workbooks.items():
                base = os.path.basename(str(path))
                sheet_name = wb.sheetnames[0] if getattr(wb, "sheetnames", None) else "(no_sheet)"
                headers: list[str] = []
                if getattr(wb, "sheetnames", None):
                    ws = wb[sheet_name]
                    # Use first non-empty row within first 5 rows as header candidate.
                    for row_idx in range(1, 6):
                        row_values = []
                        for c in range(1, 61):
                            value = ws.cell(row=row_idx, column=c).value
                            text = str(value).strip() if value is not None else ""
                            row_values.append(text)
                        candidate = [v for v in row_values if v != ""]
                        if candidate:
                            headers = candidate[:20]
                            break
                header_text = ", ".join(headers) if headers else "(no_detected_header)"
                lines.append(f"- `{base}` | sheet=`{sheet_name}` | columns={header_text}")
            unit_notes = self._sniff_percent_unit_columns()
            if unit_notes:
                lines.append("")
                lines.append("**UNIT NOTES (TRUST THIS):**")
                lines.extend(unit_notes)
            return "\n".join(lines)
        except Exception:
            return ""

    def _sniff_percent_unit_columns(self) -> list[str]:
        """Flag numeric columns whose name suggests percent units AND whose sample values exceed 1.0.

        These columns are stored as 0..100 (percent), not 0..1 (fraction). Without this
        signal the LLM may follow the user's `(1 - col)` formula literally and produce
        nonsense (e.g. DiscountPct=5 → factor=-4 → revenue goes negative).
        """
        notes: list[str] = []
        try:
            workbooks = self.sandbox.workbooks or {}
            for path, wb in workbooks.items():
                base = os.path.basename(str(path))
                if not getattr(wb, "sheetnames", None):
                    continue
                for sheet_name in wb.sheetnames:
                    ws = wb[sheet_name]
                    headers: list[str] = []
                    header_row = 0
                    for row_idx in range(1, 6):
                        row_strs = []
                        for c in range(1, 61):
                            value = ws.cell(row=row_idx, column=c).value
                            row_strs.append(str(value).strip() if value is not None else "")
                        if any(row_strs):
                            headers = row_strs
                            header_row = row_idx
                            break
                    if not headers:
                        continue
                    last_data_row = min(getattr(ws, "max_row", header_row) or header_row, header_row + 100)
                    for col_idx, header in enumerate(headers, start=1):
                        if not header or not _PERCENT_HINT_PATTERN.search(header):
                            continue
                        samples: list[float] = []
                        for r in range(header_row + 1, last_data_row + 1):
                            value = ws.cell(row=r, column=col_idx).value
                            if value is None or value == "":
                                continue
                            try:
                                samples.append(float(value))
                            except (TypeError, ValueError):
                                continue
                        if not samples:
                            continue
                        mx = max(samples)
                        if mx <= 1.0:
                            continue
                        mn = min(samples)
                        notes.append(
                            f"- `{header}` in `{base}` looks like percent units "
                            f"(sample range {mn:g}..{mx:g}). For `(1 - col)` style formulas, "
                            f"divide by 100 first (e.g. `1 - {header}/100`)."
                        )
        except Exception:
            return notes
        return notes

    def observed_header_set(self) -> set[str]:
        """Collect observed header names from loaded workbooks for grounding checks."""
        headers: set[str] = set()
        try:
            workbooks = self.sandbox.workbooks or {}
            for wb in workbooks.values():
                if not getattr(wb, "sheetnames", None):
                    continue
                sheet_name = wb.sheetnames[0]
                ws = wb[sheet_name]
                for row_idx in range(1, 6):
                    row_values = []
                    for c in range(1, 61):
                        value = ws.cell(row=row_idx, column=c).value
                        text = str(value).strip() if value is not None else ""
                        row_values.append(text)
                    candidate = [v for v in row_values if v != ""]
                    if candidate:
                        headers.update(candidate)
                        break
        except Exception:
            return set()
        return headers

    def detect_unknown_filename_lookup(self, code_action: str) -> Optional[str]:
        """Detect literal input filename lookups that are not in loaded workbook names."""
        if not code_action or not code_action.strip():
            return None

        available = set(self.available_workbook_basenames())
        if not available:
            return None

        patterns = [
            r"file_by_name\[\s*['\"]([^'\"]+\.(?:csv|xlsx|xls))['\"]\s*\]",
            r"workbooks\[\s*['\"]([^'\"]+\.(?:csv|xlsx|xls))['\"]\s*\]",
            r"data_frames\[\s*['\"]([^'\"]+\.(?:csv|xlsx|xls))['\"]\s*\]",
            r"required_files\s*=\s*\[([^\]]+)\]",
            r"(?:read_csv|read_excel|read_table)\s*\(\s*['\"]([^'\"]+\.(?:csv|xlsx|xls))['\"]",
        ]

        referenced: list[str] = []
        for idx, pattern in enumerate(patterns):
            matches = re.findall(pattern, code_action, flags=re.IGNORECASE)
            if not matches:
                continue
            if idx == 3:
                for raw_list in matches:
                    referenced.extend(
                        re.findall(r"['\"]([^'\"]+\.(?:csv|xlsx|xls))['\"]", raw_list, flags=re.IGNORECASE)
                    )
            else:
                referenced.extend(matches)

        unknown = sorted({
            os.path.basename(name) for name in referenced
            if os.path.basename(name) not in available
        })
        if not unknown:
            return None

        available_str = ", ".join(sorted(available))
        unknown_str = ", ".join(unknown)
        return (
            "GROUNDING_VIOLATION_OFFLINE: code references input filename(s) not loaded in this task.\n"
            f"- Unknown referenced names: {unknown_str}\n"
            f"- Available input filenames: {available_str}\n"
            "- Fix by using: all_files = list_all_workbooks(); "
            "file_by_name = {p.split('/')[-1]: p for p in all_files}"
        )
