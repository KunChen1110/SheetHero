"""Runtime execution plan types shared across skill prompting and repair."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence, TYPE_CHECKING

if TYPE_CHECKING:
    from .models import SkillSpec, HelperSpec


# ---------------------------------------------------------------------------
# Structured workflow step (used for composable loop-breaker generation)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WorkflowStep:
    """One atomic step in an execution plan, derived from a detected skill."""
    skill: str                           # e.g. "merge", "aggregate", "highlight", "output"
    step_name: str                       # e.g. "load_concat", "compute_summary", "mark_rows", "write_save"
    preferred_helpers: tuple[str, ...] = ()  # concrete helper functions to prefer for this step
    constraints: tuple[str, ...] = ()        # LLM-facing constraints / invariants for this step
    note: str = ""                       # optional LLM hint shown in the code skeleton
    must_run_after: tuple[str, ...] = ()     # step_names that must precede this step
    input_artifact: str = ""             # primary variable consumed by this step
    output_artifact: str = ""            # primary variable produced by this step

    def to_log_line(self) -> str:
        """Return a single-line summary for verbose logging."""
        helpers = ", ".join(self.preferred_helpers) if self.preferred_helpers else "-"
        arrow = f"{self.input_artifact or '∅'} → {self.output_artifact or '∅'}"
        return f"  [{self.skill:10s}] {self.step_name:20s}  helpers: {helpers:45s}  artifacts: {arrow}"


_STEP_ORDER = {
    "base": 0,
    "merge": 1,
    "aggregate": 2,
    "sort_rank": 3,
    "highlight": 4,
    "output": 99,
}


def compose_skill_plan(
    skills: "Sequence[SkillSpec]",
    helpers: "dict[str, HelperSpec]",
) -> list[WorkflowStep]:
    """Build an ordered list of WorkflowStep from multiple detected skills.

    Steps are sorted deterministically:
        load → merge → aggregate → sort/rank → highlight → write/save
    """
    steps: list[WorkflowStep] = []

    steps.append(WorkflowStep(
        skill="base",
        step_name="load_tables",
        preferred_helpers=("load_all_tables",),
        constraints=("print column names before any operation",),
        note="tables = load_all_tables()",
        input_artifact="",
        output_artifact="tables",
    ))

    # Track what the previous step produced so each step can name its input.
    # "df" reflects that aggregate takes a single DataFrame (extracted from tables),
    # not the raw tables list — the extraction step is implicit (LLM-driven).
    _last_df_artifact = "df"
    # When aggregate is present, write_save should consume summary_df (the filtered/summarized frame),
    # not combined_df — they must be the same object for output_row_numbers to be valid.
    _write_df_artifact = "df"  # updated as steps are added

    for skill in sorted(skills, key=lambda s: _STEP_ORDER.get(s.name, 50)):
        helper = helpers.get(skill.name)
        helper_name = helper.name if helper else ""

        if skill.name == "merge":
            steps.append(WorkflowStep(
                skill="merge",
                step_name="load_concat",
                preferred_helpers=("concat_tables_with_same_headers",),
                constraints=(
                    "classify tables by observed headers, not file order",
                    "do not hand-write pd.concat — use the helper",
                ),
                note="concat_result = concat_tables_with_same_headers(tables)",
                must_run_after=("load_tables",),
                input_artifact="tables",
                output_artifact="combined_df",
            ))
            _last_df_artifact = "combined_df"
            _write_df_artifact = "combined_df"
        elif skill.name == "aggregate":
            steps.append(WorkflowStep(
                skill="aggregate",
                step_name="compute_summary",
                preferred_helpers=("summarize_numeric_column",),
                constraints=(
                    "apply any period filter BEFORE calling summarize_numeric_column",
                    "write_dataframe_to_sheet must use the SAME df passed to summarize_numeric_column",
                    "reset DataFrame index before computing row numbers",
                    "verify value_col exists in observed headers",
                ),
                note="summary_result = summarize_numeric_column(summary_df, value_col='...')",
                must_run_after=("load_concat", "load_tables"),
                input_artifact=_last_df_artifact,
                output_artifact="summary_result",
            ))
            _write_df_artifact = "summary_df"  # must match what summarize_numeric_column received
            # highlight consumes the row numbers from summary_result, not the df itself
        elif skill.name == "highlight":
            steps.append(WorkflowStep(
                skill="highlight",
                step_name="mark_rows",
                preferred_helpers=("highlight_rows",),
                constraints=(
                    "call write_dataframe_to_sheet before highlight_rows",
                    "row = DataFrame position (0-based) + 2",
                    "use summary_result['output_row_numbers'] when available",
                ),
                note="row_numbers = summary_result['output_row_numbers']",
                must_run_after=("compute_summary", "write_output"),
                input_artifact="summary_result['output_row_numbers']",
                output_artifact="",
            ))
        elif skill.name in ("sort_rank", "rank"):
            steps.append(WorkflowStep(
                skill="sort_rank",
                step_name="rank_rows",
                preferred_helpers=(helper_name,) if helper_name else (),
                constraints=("add rank column before writing",),
                note="df = add_rank_column(df, sort_col='...')",
                input_artifact=_last_df_artifact,
                output_artifact="df",
            ))
            _last_df_artifact = "df"

    steps.append(WorkflowStep(
        skill="output",
        step_name="write_save",
        preferred_helpers=("write_dataframe_to_sheet", "save_workbook_to"),
        constraints=(
            "use save_workbook_to(output_path) — do not hardcode output path",
            "do not hand-build data_2d from headers + values",
            "write the SAME df that was passed to summarize_numeric_column when aggregate is present",
        ),
        note="write_dataframe_to_sheet(summary_df, 'Output', 'A1') → save_workbook_to(output_path)",
        must_run_after=("load_tables",),
        input_artifact=_write_df_artifact,
        output_artifact="saved_file",
    ))
    return steps


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
