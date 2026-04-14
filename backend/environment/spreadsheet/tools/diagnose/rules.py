"""Deterministic rules mapping signatures to issue types."""

from .types import (
    TITLE_INCONSISTENT,
    TOKEN_COUNT_INCONSISTENT,
    DELIMITER_INCONSISTENT,
    WHITESPACE_INCONSISTENT,
    CASING_INCONSISTENT,
    ALNUM_PATTERN_INCONSISTENT,
    DATE_FORMAT_INCONSISTENT,
)


def detect_inconsistencies(signature: dict) -> list[str]:
    issues = []
    total = signature.get("total", 0)
    if total == 0:
        return issues

    if signature.get("titles", 0) > 0 and signature.get("non_titles", 0) > 0:
        issues.append(TITLE_INCONSISTENT)

    if len(signature.get("token_counts", set())) > 1:
        issues.append(TOKEN_COUNT_INCONSISTENT)

    delimiter_counts = signature.get("delimiter_counts", {})
    for _, count in delimiter_counts.items():
        if 0 < count < total:
            issues.append(DELIMITER_INCONSISTENT)
            break

    if signature.get("whitespace_issues", 0) > 0:
        issues.append(WHITESPACE_INCONSISTENT)

    if len(signature.get("casing_categories", set())) > 1:
        issues.append(CASING_INCONSISTENT)

    if signature.get("code_like", 0) > 0 and signature.get("non_code_like", 0) > 0:
        issues.append(ALNUM_PATTERN_INCONSISTENT)

    if len(signature.get("date_formats", set())) > 1:
        issues.append(DATE_FORMAT_INCONSISTENT)

    return issues
