import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from backend.skills import detect_skill, detect_skills, select_helper


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


def test_helper_selection_generic_multi_file_merge_defaults_to_relational_join():
    skill = detect_skill("merge the four files into a single file")
    assert skill is not None
    helper = select_helper(skill, "merge the four files into a single file")
    assert helper is not None
    assert helper.name == "build_relational_join_enrichment_report"


def test_helper_selection_skips_generic_join_helper_for_downstream_analytic_report():
    question = (
        "Join the tables using StoreID and ProductID, keep only the H2 2024 months, "
        "compute net revenue, aggregate the results by Region and Category, compare each aggregate "
        "to the revenue target, create a Top 10 store leaderboard, and output three sheets."
    )
    skill = detect_skill(question)
    assert skill is not None
    helper = select_helper(skill, question)
    assert helper is None


def test_helper_selection_multi_key_join_from_explicit_two_key_phrase():
    skill = detect_skill("join the spreadsheet tables by the shared student id and semester keys")
    assert skill is not None
    helper = select_helper(skill, "join the spreadsheet tables by the shared student id and semester keys")
    assert helper is not None
    assert helper.name == "build_multi_key_relational_join_report"


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


def test_helper_selection_target_feature_correlation():
    question = (
        "Calculate the correlation coefficient between survival and other factors "
        "such as sex, age, fare, cabin, and embarked using the Titanic dataset."
    )
    skill = detect_skill(question)
    helper = select_helper(skill, question)
    assert helper.name == "compute_feature_correlations"


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


def test_rank_detected_from_generic_weight_formula():
    skill = detect_skill(
        "Score each applicant using 0.5 * experience + 0.3 * skills + 0.2 * interview score, then rank them."
    )
    assert skill is not None
    assert skill.name == "rank"


def test_helper_selection_cash_flow_efficiency():
    question = (
        "Evaluate the cash flow efficiency by calculating operating cash flow to net income "
        "and free cash flow."
    )
    skill = detect_skill(question)
    helper = select_helper(skill, question)
    assert skill is not None
    assert skill.name == "financial"
    assert helper is not None
    assert helper.name == "build_cash_flow_efficiency_report"


def test_helper_selection_financial_dashboard():
    question = (
        "Calculate gross profit, net profit, gross profit margin, net profit margin, "
        "customer acquisition cost, and marketing efficiency ratio, then output a "
        "dashboard comparing actuals to targets."
    )
    skill = detect_skill(question)
    helper = select_helper(skill, question)
    assert skill is not None
    assert skill.name == "financial"
    assert helper is not None
    assert helper.name == "build_financial_dashboard_report"


def test_helper_selection_inventory_policy():
    question = (
        "Calculate EOQ, reorder point, orders per year, cycle time, and total annual cost, "
        "then run sensitivity analysis."
    )
    skill = detect_skill(question)
    helper = select_helper(skill, question)
    assert skill is not None
    assert skill.name == "financial"
    assert helper is not None
    assert helper.name == "build_inventory_eoq_report"


def test_helper_selection_region_share_and_cost_report():
    question = (
        "Given regional population totals and regional healthcare expenditure, "
        "calculate each region's share of the global population and the "
        "average expenditure per person."
    )
    skill = detect_skill(question)
    helper = select_helper(skill, question)
    assert skill is not None
    assert skill.name == "proportion"
    assert helper is not None
    assert helper.name == "build_region_share_cost_report"


def test_helper_selection_two_dimension_mean_count_summary_report():
    question = (
        "Given a dataset containing country, category, and rating, "
        "generate a table showing for each country and category the average rating and the number of records."
    )
    skill = detect_skill(question)
    helper = select_helper(skill, question)
    assert skill is not None
    assert skill.name == "aggregate"
    assert helper is not None
    assert helper.name == "build_two_dimension_mean_count_summary_report"


def test_merge_skill_detected_for_join_with_singular_table_names():
    question = (
        "Merge the store sales data with the store information table using Store ID, "
        "then compute total monthly sales by city for March and rank cities."
    )
    skill = detect_skill(question)
    helper = select_helper(skill, question)
    assert skill is not None
    assert skill.name == "merge"
    assert helper is not None
    assert helper.name == "build_relational_join_enrichment_report"


def test_helper_selection_multi_source_group_comparison_report():
    question = (
        "Merge weekly sales with reference information by ID, then calculate average sales, "
        "temperature, and fuel price for each group and compare holiday versus non-holiday periods."
    )
    skill = detect_skill(question)
    helper = select_helper(skill, question)
    assert skill is not None
    assert skill.name == "merge"
    assert helper is not None
    assert helper.name == "build_multi_source_group_comparison_report"


def test_helper_selection_multi_source_utilisation_summary_report():
    question = (
        "Compute service utilisation and staff utilisation for each department, identify departments above 90%, "
        "and highlight those values in red."
    )
    skill = detect_skill(question)
    helper = select_helper(skill, question)
    assert skill is not None
    assert skill.name == "aggregate"
    assert helper is not None
    assert helper.name == "build_multi_source_utilisation_summary_report"


def test_helper_selection_university_utilisation_summary_report():
    question = (
        "You have five clean university tables: students, courses, sections, enrollments, and rooms. "
        "Join the tables using StudentID, CourseID, SectionID, and RoomID. "
        "For each section, calculate enrolled count, waitlisted count, fill rate, and waitlist rate. "
        "Then summarise instructor load with section count, total enrolled, and scheduled hours, "
        "and create a room-utilisation summary by building using average section fill rate."
    )
    skill = detect_skill(question)
    helper = select_helper(skill, question)
    assert skill is not None
    assert skill.name == "aggregate"
    assert helper is not None
    assert helper.name == "build_multi_source_utilisation_summary_report"


def test_statistical_skill_prioritized_over_aggregate_for_correlation_plus_average_question():
    question = (
        "Calculate the Pearson correlation between PerformanceRating and MonthlySalary, "
        "and compute the average salary for each rating level."
    )
    skill = detect_skill(question)
    assert skill is not None
    assert skill.name == "statistical"


def test_detect_skills_returns_priority_sorted_matches():
    question = (
        "Calculate EOQ, reorder point, orders per year, cycle time, and total annual cost, "
        "then run sensitivity analysis."
    )
    matched = detect_skills(question)
    assert [skill.name for skill in matched[:2]] == ["financial", "aggregate"]


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
