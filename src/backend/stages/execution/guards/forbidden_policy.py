"""Forbidden-policy helpers for offline bounded execution."""

from __future__ import annotations

from typing import Dict


def is_immediate_hard_forbidden(forbidden_err: str) -> bool:
    """Hard-block only truly risky patterns."""
    if not forbidden_err:
        return False
    lower_msg = forbidden_err.lower()
    high_risk_markers = (
        "openpyxl",
        "load_workbook",
        "file i/o with open()",
        "file i/o open()",
        "with open()",
        "pd.read_excel",
        "pd.read_csv",
        "pd.read_table",
        "pd.excelfile",
        "placeholder input paths like /path/to/",
        "hard-coded absolute paths",
        "do not override all_files with literal list",
    )
    return any(marker in lower_msg for marker in high_risk_markers)


def forbidden_signature(forbidden_err: str) -> str:
    """Classify forbidden reason into a stable signature for memory/tracking."""
    lower = (forbidden_err or "").lower()
    if "do not hard-code save paths" in lower or "save_workbook_to(output_path) only" in lower:
        return "save_path_literal"
    if "hard-coded absolute paths" in lower or "/users/" in lower:
        return "absolute_path_literal"
    if "pd.read_excel" in lower or "pd.read_csv" in lower or "pd.read_table" in lower or "pd.excelfile" in lower:
        return "pandas_file_reader"
    if "to_excel" in lower or "to_csv" in lower:
        return "pandas_file_writer"
    if "openpyxl" in lower or "load_workbook" in lower:
        return "openpyxl_usage"
    if "open()" in lower or "file i/o" in lower:
        return "file_io_open"
    if "read_table_multi() requires at least 1 positional args" in lower:
        return "read_table_multi_missing_args"
    if "read_table_multi() does not accept keyword" in lower:
        return "read_table_multi_bad_kwargs"
    if "all_files = [" in lower:
        return "override_all_files"
    return "other"


def build_forbidden_repair_hint(forbidden_err: str) -> str:
    """Return a concise, executable repair hint for the next turn."""
    lower = (forbidden_err or "").lower()
    if "to_excel" in lower or "dataframe.to_excel" in lower or "to_csv" in lower:
        return (
            "Replacement pattern:\n"
            "create_output_sheet(\"Output\")\n"
            "write_dataframe_to_sheet(df, \"Output\", \"A1\")\n"
            "saved_file = save_workbook_to(output_path)\n"
            "print(\"SAVED_FILE:\", saved_file)\n"
        )
    if "read_csv" in lower or "read_table" in lower or "read_excel" in lower or "excelfile" in lower:
        return (
            "Do not load files via pandas readers.\n"
            "Use the runtime helper path instead:\n"
            "tables = load_all_tables()\n"
            "df = tables[0]['df']\n"
            "Then call the task-appropriate helper on `df` or on selected tables.\n"
            "Write the helper output to `Output` and save with `save_workbook_to(output_path)`.\n"
        )
    if "open()" in lower or "file i/o" in lower:
        return (
            "Do not write files with open(). Use write_dataframe_to_sheet(...)\n"
            "and save_workbook_to(output_path) instead.\n"
        )
    if "openpyxl" in lower or "load_workbook" in lower:
        return (
            "Do not import openpyxl or use load_workbook.\n"
            "Only allowed import is: import pandas as pd\n"
        )
    if "/users/" in lower or "hard-coded absolute paths" in lower:
        return (
            "Do not hard-code input paths or literal input filenames.\n"
            "Use runtime helpers instead:\n"
            "tables = load_all_tables()\n"
            "Select the needed DataFrame(s) from `tables` or via `find_table_by_headers(...)`.\n"
            "Never write '/Users/...', 'tc04_input01.xlsx', or any other literal input path/name in code.\n"
        )
    return (
        "Fix only the forbidden lines.\n"
        "Use allowed helpers: list_all_workbooks(), get_workbook(), read_table_multi(), "
        "load_all_tables(), find_table_by_headers(), build_dependency_schedule(), "
        "create_output_sheet(), write_dataframe_to_sheet(), save_workbook_to(output_path).\n"
    )


def forbidden_signature_lesson(signature: str) -> str:
    """Single-line lesson used in memory feedback."""
    lessons = {
        "save_path_literal": "Never call save_workbook_to with string literal path; always pass output_path.",
        "absolute_path_literal": "Never hard-code /Users/... paths; always resolve from list_all_workbooks().",
        "pandas_file_reader": "Never use pandas file readers; input must come from runtime helpers only.",
        "pandas_file_writer": "Never use pandas writers; output must use write_dataframe_to_sheet + save_workbook_to(output_path).",
        "openpyxl_usage": "Never use openpyxl/load_workbook directly in bounded mode.",
        "file_io_open": "Never use open(); output must be written via helper functions.",
        "read_table_multi_missing_args": "read_table_multi needs a file_path and optional sheet/range args.",
        "read_table_multi_bad_kwargs": "read_table_multi kwargs are invalid; use positional args.",
        "override_all_files": "Do not override all_files with literals; always use list_all_workbooks().",
        "other": "Patch forbidden lines minimally and keep helper-based pipeline.",
    }
    return lessons.get(signature, lessons["other"])


def build_forbidden_memory_block(signature_counts: Dict[str, int], latest_signature: str | None) -> str:
    """Build compact forbidden-memory notes to reduce repeated violations."""
    if not signature_counts:
        return ""
    ordered = sorted(signature_counts.items(), key=lambda item: (-item[1], item[0]))
    lines = []
    for signature, count in ordered[:3]:
        marker = " (latest)" if latest_signature == signature else ""
        lesson = forbidden_signature_lesson(signature)
        lines.append(f"- {signature} x{count}{marker}: {lesson}")
    if not lines:
        return ""
    return "FORBIDDEN_MEMORY:\n" + "\n".join(lines)
