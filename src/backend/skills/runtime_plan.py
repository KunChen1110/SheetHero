"""Runtime execution plan types shared across skill prompting and repair."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RuntimeExecutionPlan:
    """Schema-grounded execution plan inferred from the current question and headers."""

    skill_name: str
    task_type: str
    table_roles: dict[str, str] = field(default_factory=dict)
    target_col: str | None = None
    feature_cols: tuple[str, ...] = ()
    group_cols: tuple[str, ...] = ()
    join_keys: tuple[str, ...] = ()
    period_col: str | None = None
    value_cols: tuple[str, ...] = ()
    categorical_cols_to_encode: tuple[str, ...] = ()
    numeric_cols_to_coerce: tuple[str, ...] = ()
    output_contract: dict[str, str] = field(default_factory=dict)

    def to_prompt_summary(self) -> str:
        """Return a compact prompt-safe summary of the inferred plan."""
        lines = [
            f"task_type={self.task_type}",
            f"target_col={self.target_col or ''}",
            f"feature_cols={', '.join(self.feature_cols)}",
            f"group_cols={', '.join(self.group_cols)}",
            f"join_keys={', '.join(self.join_keys)}",
            f"period_col={self.period_col or ''}",
            f"value_cols={', '.join(self.value_cols)}",
            f"output_kind={self.output_contract.get('kind', '')}",
            f"output_sheet={self.output_contract.get('sheet_name', '')}",
        ]
        return "\n".join(lines)


def parse_plan_summary(plan_summary: str) -> dict[str, object]:
    """Parse a compact plan summary back into a small prompt-facing mapping."""
    parsed: dict[str, object] = {}
    for raw_line in (plan_summary or "").splitlines():
        if "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key in {"feature_cols", "group_cols", "join_keys", "value_cols"}:
            parsed[key] = [part.strip() for part in value.split(",") if part.strip()]
        else:
            parsed[key] = value
    return parsed
