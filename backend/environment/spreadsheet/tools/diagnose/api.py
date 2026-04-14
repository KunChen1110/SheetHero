"""Public API for spreadsheet format diagnosis."""

from __future__ import annotations

from .iterators import iter_string_columns
from .rules import detect_inconsistencies
from .signature import extract_format_signature
from .types import DiagnosisItem


_ISSUE_TEMPLATES = {
    "TITLE_INCONSISTENT": (
        "Column '{column}' mixes titled and non-titled name formats "
        "(titles detected in {affected}/{total} non-empty cells), which may break grouping/matching."
    ),
    "TOKEN_COUNT_INCONSISTENT": (
        "Column '{column}' has inconsistent token counts (single vs multi-token values), "
        "which may affect matching and grouping."
    ),
    "DELIMITER_INCONSISTENT": (
        "Column '{column}' contains multiple delimiter conventions (e.g., commas/periods/Hyphens), "
        "which may create duplicates or mismatches."
    ),
    "WHITESPACE_INCONSISTENT": (
        "Column '{column}' has inconsistent whitespace (extra or leading/trailing spaces), "
        "which may create distinct keys for the same entity."
    ),
    "CASING_INCONSISTENT": (
        "Column '{column}' has inconsistent casing (upper/lower/title/mixed), "
        "which may break case-sensitive matching or grouping."
    ),
    "ALNUM_PATTERN_INCONSISTENT": (
        "Column '{column}' mixes code-like values with other formats (e.g., 'C80' vs 'Room C80'), "
        "which may lead to duplicate entities."
    ),
    "DATE_FORMAT_INCONSISTENT": (
        "Column '{column}' mixes date string formats (e.g., ISO vs slash vs text), "
        "which may cause incorrect ordering or parsing."
    ),
}


def diagnose_format_inconsistencies(workbook_view) -> list[str]:
    """
    Entry point for spreadsheet format diagnosis.
    Returns a list of issue strings.
    """
    issues = []
    for sheet_key, column, series in iter_string_columns(workbook_view):
        signature = extract_format_signature(series)
        for issue_type in detect_inconsistencies(signature):
            item = DiagnosisItem(
                sheet=sheet_key,
                column=column,
                issue_type=issue_type,
                detail=issue_type,
                total=signature.get("total", 0),
                affected=_estimate_affected(signature, issue_type),
            )
            template = _ISSUE_TEMPLATES.get(issue_type)
            if not template:
                continue
            message = (
                f"Sheet '{item.sheet}': "
                + template.format(
                    column=item.column,
                    affected=item.affected,
                    total=item.total,
                )
            )
            issues.append(message)
    return issues


def _estimate_affected(signature: dict, issue_type: str) -> int:
    if issue_type == "TITLE_INCONSISTENT":
        return signature.get("titles", 0)
    if issue_type == "WHITESPACE_INCONSISTENT":
        return signature.get("whitespace_issues", 0)
    if issue_type == "ALNUM_PATTERN_INCONSISTENT":
        return signature.get("code_like", 0)
    return signature.get("total", 0)
