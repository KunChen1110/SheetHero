"""Reporting utilities for diagnose stage."""

from __future__ import annotations

from typing import Dict, List, Tuple


def build_diagnose_report(sampled: Dict[str, Tuple[List[str], List[List[str]]]]) -> str:
    if not sampled:
        return "No scan results."

    lines: List[str] = []
    for sheet_key, (columns, rows) in sampled.items():
        lines.append(f"Sheet: {sheet_key}")
        if columns:
            lines.append("Columns: " + " | ".join(_format_text(col) for col in columns) + " |")
        else:
            lines.append("Columns: (none)")
        lines.append("")
        lines.append("Sample rows:")
        if not rows:
            lines.append("- (no rows)")
            lines.append("")
            continue
        for row in rows:
            row_text = " | ".join(_truncate(cell) for cell in row) + " |"
            lines.append(f"- {row_text}")
        lines.append("")
    return "\n".join(lines).strip()


def _truncate(value: str, limit: int = 2000) -> str:
    if len(value) <= limit:
        return value
    return value[:limit - 3] + "..."


def _format_text(value: str) -> str:
    text = "" if value is None else str(value)
    if not text:
        return "| |"
    return text
