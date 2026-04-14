"""Structured QA issue-group and cleaning-policy models."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class QAIssueGroup:
    issue_type: str
    sheet_key: str
    column: str | None = None
    affected_rows: tuple[int, ...] = ()

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class CleaningPolicyPlan:
    policy_kind: str
    sheet_key: str
    column: str | None = None
    affected_rows: tuple[int, ...] = ()
    resolution: str = ""
    fill_value: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)
