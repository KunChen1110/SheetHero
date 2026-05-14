"""Deterministic execution helpers for structured cleaning policy plans."""

from __future__ import annotations


def apply_policy_plan(workbooks: dict, policy_plan: dict) -> tuple[str, str]:
    """Apply one structured policy plan and return a report bucket plus message."""
    if (
        policy_plan.get("policy_kind") == "missing_value"
        and policy_plan.get("resolution") == "leave_blank"
    ):
        column = policy_plan.get("column")
        sheet_key = policy_plan.get("sheet_key")
        return "applied_actions", f"Leave missing `{column}` values unchanged in `{sheet_key}`."

    return "skipped_actions", f"Unsupported policy plan: {policy_plan}"
