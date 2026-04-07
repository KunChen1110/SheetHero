import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from src.backend.task_skills import detect_skill, select_helper


def test_merge_detected_from_generic_question():
    skill = detect_skill("merge the two tables into a single file")
    assert skill is not None
    assert skill.name == "merge"


def test_aggregate_detected_from_generic_question():
    skill = detect_skill("calculate the average score grouped by department")
    assert skill is not None
    assert skill.name == "aggregate"


def test_statistical_detected():
    skill = detect_skill("compute the correlation matrix for all numeric columns")
    assert skill is not None
    assert skill.name == "statistical"


def test_schedule_detected():
    skill = detect_skill("schedule the tasks based on dependencies")
    assert skill is not None
    assert skill.name == "schedule"


def test_scan_detected():
    skill = detect_skill("check the file for missing data")
    assert skill is not None
    assert skill.name == "scan"


def test_no_skill_for_vague_question():
    skill = detect_skill("what is the meaning of life")
    assert skill is None


def test_highlight_question_no_wrong_skill():
    """A question about 'average + highlight' without 'merge' should hit aggregate, not merge."""
    skill = detect_skill("calculate the average spending and highlight the highest day")
    assert skill is not None
    assert skill.name == "aggregate"


def test_helper_selection_merge_same_schema():
    skill = detect_skill("merge the two tables and calculate the average, highlight the max")
    assert skill is not None
    helper = select_helper(skill, "merge the two tables and calculate the average, highlight the max")
    assert helper is not None
    assert helper.name == "concat_tables_with_same_headers"


def test_helper_selection_merge_join():
    skill = detect_skill("merge the two files using the student ID column")
    assert skill is not None
    helper = select_helper(skill, "merge the two files using the student ID column")
    assert helper is not None
    assert helper.name == "build_relational_join_enrichment_report"


def test_helper_selection_fill():
    skill = detect_skill("fill any missing data using information from the reference file")
    assert skill is not None
    helper = select_helper(skill, "fill any missing data using information from the reference file")
    assert helper is not None
    assert helper.name == "fill_missing_from_reference"


def test_helper_selection_aggregate_time():
    skill = detect_skill("calculate the total enrollment by year and semester, sorted descending")
    helper = select_helper(skill, "calculate the total enrollment by year and semester, sorted descending")
    assert helper.name == "build_time_series_aggregation_report"


def test_helper_selection_aggregate_group():
    skill = detect_skill("group countries by continent, calculate average emissions, rank descending")
    helper = select_helper(skill, "group countries by continent, calculate average emissions, rank descending")
    assert helper.name == "build_grouped_aggregation_ranking_report"


def test_helper_selection_regression():
    skill = detect_skill("find the regression coefficients for ice cream sales")
    helper = select_helper(skill, "find the regression coefficients for ice cream sales")
    assert helper.name == "fit_linear_regression_weights"


def test_helper_selection_correlation():
    skill = detect_skill("compute the correlation matrix between survival and other factors")
    helper = select_helper(skill, "compute the correlation matrix between survival and other factors")
    assert helper.name == "build_correlation_matrix_table"


def test_helper_selection_cycle():
    skill = detect_skill("determine which graphs contain a cycle")
    helper = select_helper(skill, "determine which graphs contain a cycle")
    assert helper.name == "build_cycle_detection_report"


def test_helper_selection_dependency_schedule():
    skill = detect_skill("schedule tasks based on their dependencies and durations")
    helper = select_helper(skill, "schedule tasks based on their dependencies and durations")
    assert helper.name == "build_dependency_schedule"


def test_helper_selection_allocation():
    skill = detect_skill("allocate students to rooms based on capacity limits")
    helper = select_helper(skill, "allocate students to rooms based on capacity limits")
    assert helper.name == "build_capacity_constrained_allocation_report"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
