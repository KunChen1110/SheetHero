"""Test matrix for the 7 skill-composition combinations.

Tests the full chain:
  question → detect_skills() → compose_skill_plan() → WorkflowStep fields
  → build_loop_breaker() output content

Combinations covered:
  1. merge only
  2. aggregate only
  3. highlight only
  4. merge + aggregate
  5. merge + highlight
  6. aggregate + highlight
  7. merge + aggregate + highlight
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from backend.skills import (
    detect_skills,
    select_helper,
    compose_skill_plan,
    build_loop_breaker,
    WorkflowStep,
)
from backend.skills.registry import all_skills as _all_skills_list


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _skill_by_name(name: str):
    for s in _all_skills_list():
        if s.name == name:
            return s
    raise KeyError(f"skill {name!r} not in registry")


def _make_plan_and_breaker(question: str):
    matched_skills = detect_skills(question)
    assert matched_skills, f"no skill detected for: {question!r}"
    primary = matched_skills[0]
    helper = select_helper(primary, question)
    helpers_map = {
        s.name: select_helper(s, question) for s in matched_skills
    }
    plan = compose_skill_plan(matched_skills, helpers_map)
    breaker = build_loop_breaker(primary, helper, extra_skills=matched_skills) if helper else ""
    return matched_skills, plan, breaker


def _step_names(plan: list[WorkflowStep]) -> list[str]:
    return [s.step_name for s in plan]


def _skill_names(plan: list[WorkflowStep]) -> list[str]:
    return [s.skill for s in plan]


# ---------------------------------------------------------------------------
# 1. merge only
# ---------------------------------------------------------------------------

def test_merge_only_plan():
    q = "combine all the monthly sales files into one table"
    matched, plan, breaker = _make_plan_and_breaker(q)

    skill_names_detected = [s.name for s in matched]
    assert "merge" in skill_names_detected

    step_names = _step_names(plan)
    assert "load_tables" in step_names
    assert "load_concat" in step_names
    assert "write_save" in step_names
    # aggregate and highlight must NOT appear
    assert "compute_summary" not in step_names
    assert "mark_rows" not in step_names


def test_merge_only_step_fields():
    q = "combine all the monthly sales files into one table"
    _, plan, _ = _make_plan_and_breaker(q)

    concat_step = next(s for s in plan if s.step_name == "load_concat")
    assert "concat_tables_with_same_headers" in concat_step.preferred_helpers
    assert concat_step.output_artifact == "combined_df"
    assert any("header" in c for c in concat_step.constraints)


def test_merge_only_loop_breaker():
    q = "combine all the monthly sales files into one table"
    _, _, breaker = _make_plan_and_breaker(q)

    assert "concat_tables_with_same_headers" in breaker
    assert "combined_df" in breaker
    # no aggregate lines
    assert "summarize_numeric_column" not in breaker
    # no highlight lines
    assert "highlight_rows" not in breaker


# ---------------------------------------------------------------------------
# 2. aggregate only
# ---------------------------------------------------------------------------

def test_aggregate_only_plan():
    q = "calculate the average revenue grouped by region"
    matched, plan, breaker = _make_plan_and_breaker(q)

    skill_names_detected = [s.name for s in matched]
    assert "aggregate" in skill_names_detected

    step_names = _step_names(plan)
    assert "load_tables" in step_names
    assert "write_save" in step_names
    # merge and highlight must NOT appear for pure aggregate
    assert "load_concat" not in step_names
    assert "mark_rows" not in step_names


def test_aggregate_only_step_fields():
    q = "calculate the average revenue grouped by region"
    _, plan, _ = _make_plan_and_breaker(q)

    # output step should declare output_artifact and constraint
    output_step = next(s for s in plan if s.step_name == "write_save")
    assert "save_workbook_to" in output_step.preferred_helpers
    assert output_step.output_artifact == "saved_file"
    assert any("output_path" in c for c in output_step.constraints)


# ---------------------------------------------------------------------------
# 3. highlight only
# ---------------------------------------------------------------------------

def test_highlight_only_plan():
    q = "highlight the highest scoring student rows in red"
    matched, plan, breaker = _make_plan_and_breaker(q)

    skill_names_detected = [s.name for s in matched]
    assert "highlight" in skill_names_detected

    step_names = _step_names(plan)
    assert "mark_rows" in step_names
    assert "load_concat" not in step_names


def test_highlight_only_step_fields():
    q = "highlight the highest scoring student rows in red"
    _, plan, _ = _make_plan_and_breaker(q)

    mark_step = next(s for s in plan if s.step_name == "mark_rows")
    assert "highlight_rows" in mark_step.preferred_helpers
    assert any("write_dataframe_to_sheet" in c for c in mark_step.constraints)
    assert "compute_summary" in mark_step.must_run_after or "write_output" in mark_step.must_run_after


# ---------------------------------------------------------------------------
# 4. merge + aggregate
# ---------------------------------------------------------------------------

def test_merge_aggregate_plan():
    q = "combine the monthly files and calculate the total sales per region"
    matched, plan, breaker = _make_plan_and_breaker(q)

    skill_names_detected = {s.name for s in matched}
    assert "merge" in skill_names_detected
    assert "aggregate" in skill_names_detected

    step_names = _step_names(plan)
    assert "load_concat" in step_names
    assert "compute_summary" in step_names
    assert "write_save" in step_names
    # highlight must NOT appear
    assert "mark_rows" not in step_names


def test_merge_aggregate_ordering():
    q = "combine the monthly files and calculate the total sales per region"
    _, plan, _ = _make_plan_and_breaker(q)

    step_names = _step_names(plan)
    assert step_names.index("load_concat") < step_names.index("write_save")
    # aggregate after merge when both present
    if "compute_summary" in step_names:
        assert step_names.index("load_concat") < step_names.index("compute_summary")


def test_merge_aggregate_loop_breaker():
    q = "combine the monthly files and calculate the total sales per region"
    matched = detect_skills(q)
    primary = matched[0]
    helper = select_helper(primary, q)
    if helper and helper.name == "concat_tables_with_same_headers":
        breaker = build_loop_breaker(primary, helper, extra_skills=matched)
        assert "concat_tables_with_same_headers" in breaker
        assert "summarize_numeric_column" in breaker
        assert "highlight_rows" not in breaker


# ---------------------------------------------------------------------------
# 5. merge + highlight
# ---------------------------------------------------------------------------

def test_merge_highlight_plan():
    q = "merge all student files and highlight the top scorer rows in red"
    matched, plan, breaker = _make_plan_and_breaker(q)

    skill_names_detected = {s.name for s in matched}
    assert "merge" in skill_names_detected
    assert "highlight" in skill_names_detected

    step_names = _step_names(plan)
    assert "load_concat" in step_names
    assert "mark_rows" in step_names
    assert "write_save" in step_names


def test_merge_highlight_loop_breaker():
    q = "merge all student files and highlight the top scorer rows in red"
    matched = detect_skills(q)
    primary = matched[0]
    helper = select_helper(primary, q)
    if helper and helper.name == "concat_tables_with_same_headers":
        breaker = build_loop_breaker(primary, helper, extra_skills=matched)
        assert "concat_tables_with_same_headers" in breaker
        assert "highlight_rows" in breaker
        # no aggregate lines when aggregate not detected
        assert "summarize_numeric_column" not in breaker


# ---------------------------------------------------------------------------
# 6. aggregate + highlight
# ---------------------------------------------------------------------------

def test_aggregate_highlight_plan():
    q = "find the highest revenue per category and highlight those rows in red"
    matched, plan, breaker = _make_plan_and_breaker(q)

    skill_names_detected = {s.name for s in matched}
    assert "aggregate" in skill_names_detected or "highlight" in skill_names_detected

    step_names = _step_names(plan)
    assert "load_tables" in step_names
    assert "write_save" in step_names


# ---------------------------------------------------------------------------
# 7. merge + aggregate + highlight  (full pipeline)
# ---------------------------------------------------------------------------

def test_full_pipeline_plan():
    q = "combine all monthly sales files, compute the highest total per region, and highlight those rows in red"
    matched, plan, breaker = _make_plan_and_breaker(q)

    skill_names_detected = {s.name for s in matched}
    assert "merge" in skill_names_detected
    assert "aggregate" in skill_names_detected or "highlight" in skill_names_detected

    step_names = _step_names(plan)
    assert "load_tables" in step_names
    assert "write_save" in step_names
    # merge before aggregate before highlight (when all present)
    if "load_concat" in step_names and "compute_summary" in step_names:
        assert step_names.index("load_concat") < step_names.index("compute_summary")
    if "compute_summary" in step_names and "mark_rows" in step_names:
        assert step_names.index("compute_summary") < step_names.index("mark_rows")


def test_full_pipeline_loop_breaker():
    q = "combine all monthly sales files, compute the highest total per region, and highlight those rows in red"
    matched = detect_skills(q)
    primary = matched[0]
    helper = select_helper(primary, q)
    if helper and helper.name == "concat_tables_with_same_headers":
        breaker = build_loop_breaker(primary, helper, extra_skills=matched)
        assert "concat_tables_with_same_headers" in breaker
        if "aggregate" in {s.name for s in matched}:
            assert "summarize_numeric_column" in breaker
        if "highlight" in {s.name for s in matched}:
            assert "highlight_rows" in breaker


# ---------------------------------------------------------------------------
# WorkflowStep structure invariants (apply to ALL compositions)
# ---------------------------------------------------------------------------

def test_workflow_step_always_starts_with_load_tables():
    for q in [
        "combine all monthly files",
        "calculate average per region",
        "highlight top rows in red",
        "merge files and total sales",
    ]:
        matched = detect_skills(q)
        if not matched:
            continue
        helpers_map = {s.name: select_helper(s, q) for s in matched}
        plan = compose_skill_plan(matched, helpers_map)
        assert plan[0].step_name == "load_tables", f"first step should be load_tables for: {q!r}"


def test_workflow_step_always_ends_with_write_save():
    for q in [
        "combine all monthly files",
        "calculate average per region",
        "merge files and total sales and highlight top rows",
    ]:
        matched = detect_skills(q)
        if not matched:
            continue
        helpers_map = {s.name: select_helper(s, q) for s in matched}
        plan = compose_skill_plan(matched, helpers_map)
        assert plan[-1].step_name == "write_save", f"last step should be write_save for: {q!r}"


def test_workflow_step_preferred_helpers_populated():
    q = "combine all monthly files into one table"
    matched = detect_skills(q)
    helpers_map = {s.name: select_helper(s, q) for s in matched}
    plan = compose_skill_plan(matched, helpers_map)
    for step in plan:
        assert isinstance(step.preferred_helpers, tuple), f"step {step.step_name}: preferred_helpers must be tuple"
        assert isinstance(step.constraints, tuple), f"step {step.step_name}: constraints must be tuple"
        assert isinstance(step.must_run_after, tuple), f"step {step.step_name}: must_run_after must be tuple"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
