"""Shared types and constants for format diagnosis."""

from dataclasses import dataclass

TITLE_INCONSISTENT = "TITLE_INCONSISTENT"
TOKEN_COUNT_INCONSISTENT = "TOKEN_COUNT_INCONSISTENT"
DELIMITER_INCONSISTENT = "DELIMITER_INCONSISTENT"
WHITESPACE_INCONSISTENT = "WHITESPACE_INCONSISTENT"
CASING_INCONSISTENT = "CASING_INCONSISTENT"
ALNUM_PATTERN_INCONSISTENT = "ALNUM_PATTERN_INCONSISTENT"
DATE_FORMAT_INCONSISTENT = "DATE_FORMAT_INCONSISTENT"


@dataclass(frozen=True)
class DiagnosisItem:
    sheet: str
    column: str
    issue_type: str
    detail: str
    total: int
    affected: int
