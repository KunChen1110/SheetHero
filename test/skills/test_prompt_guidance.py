import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from src.backend.skills import (
    RuntimeExecutionPlan,
    build_execution_strict_rules,
    build_loop_breaker,
    detect_skill,
    select_helper,
)
from src.backend.stages.execution.skill.prompt import ExecutionSkillPromptAdvisor


class _RuntimeStub:
    def _available_workbook_basenames(self):
        return []

    def _build_schema_snapshot(self):
        return ""

    def _observed_header_set(self):
        return {"Date", "Category", "Daily Spending (£)"}

    class question_inference:
        @staticmethod
        def build_skill_grounded_call_hint(*_args, **_kwargs):
            return ""

        @staticmethod
        def infer_runtime_plan(*_args, **_kwargs):
            return RuntimeExecutionPlan(
                skill_name="merge",
                task_type="schema_merge_summary",
                table_roles={"primary_table": "runtime_selected"},
                output_contract={"kind": "workbook", "sheet_name": "Output"},
            )


def test_execution_strict_rules_do_not_force_direct_task_helper_call():
    skill = detect_skill("merge the two tables and calculate the total spending")
    helper = select_helper(skill, "merge the two tables and calculate the total spending")

    guidance = build_execution_strict_rules(skill, helper)

    assert "Use `concat_tables_with_same_headers(...)` for this task." not in guidance
    assert "shared runtime helpers" in guidance
    assert "Do not replace the whole task with a single task-shaped helper shortcut." in guidance


def test_execution_prompt_uses_primary_skill_only_without_secondary_guidance():
    advisor = ExecutionSkillPromptAdvisor(_RuntimeStub())

    prompt = advisor.augment_initial_prompt(
        "Base prompt",
        "merge the two tables and calculate the average spending, then highlight the highest row",
    )

    assert "SECONDARY SKILL GUIDANCE" not in prompt
    assert "NOTE: This task requires multiple operations in order" not in prompt
    assert "PRIMARY SKILL WORKFLOW [MERGE]" in prompt


def test_merge_prompt_guidance_prefers_helper_pipeline_for_same_schema_summary_tasks():
    advisor = ExecutionSkillPromptAdvisor(_RuntimeStub())
    question = (
        "Here are two tables showing my daily spending. First merge the two tables into a single table, "
        "then calculate the average daily spending and the total spending in November. "
        "Also highlight in red the day or days on which I spend the most. "
        "Finally, output the results as a new spreadsheet."
    )

    prompt = advisor.augment_initial_prompt("Base prompt", question)

    assert "concat_tables_with_same_headers" in prompt
    assert "summarize_numeric_column" in prompt
    assert "do not hand-build `data_2d`" in prompt.lower()


def test_schedule_guidance_allows_header_grounded_assignment_helper_path():
    question = (
        "Here are several tables about students and their tutors. "
        "Your task is to produce a new table that lists, for each tutor, "
        "the tutor's name, the meeting time and location, and the students attending that meeting."
    )
    skill = detect_skill(question)
    helper = select_helper(skill, question)

    guidance = build_execution_strict_rules(skill, helper)

    assert "find_table_by_headers" in guidance
    assert "build_relational_assignment_schedule_report()" in guidance


def test_schedule_guidance_prefers_dependency_helper_pipeline_for_dag_tasks():
    question = (
        "Here is a table containing tasks, their durations, and priorities, and another table "
        "describing task dependencies. Schedule the tasks based on these dependencies and report "
        "the total duration required to finish all the tasks."
    )
    skill = detect_skill(question)
    helper = select_helper(skill, question)

    guidance = build_execution_strict_rules(skill, helper)
    loop_breaker = build_loop_breaker(skill, helper)

    assert "build_dependency_schedule" in guidance
    assert "find_table_by_headers" in guidance
    assert "schedule_result['task_id_set']" in loop_breaker
    assert "schedule_result['scheduled_task_ids']" in loop_breaker
    assert "schedule_result['detail_data']" in loop_breaker
    assert "write_dataframe_to_sheet" in loop_breaker


def test_proportion_guidance_prefers_generic_weighted_period_helpers():
    question = (
        "One table gives smartphone units shipped from 2012 to 2025, and another gives "
        "market share from 2017 to 2025. Find the overlapping period and estimate each "
        "brand's units as market_share * shipment."
    )
    skill = detect_skill(question)
    helper = select_helper(skill, question)

    guidance = build_execution_strict_rules(skill, helper)
    loop_breaker = build_loop_breaker(skill, helper)

    assert "Do NOT call `build_market_share_shipment_report()` directly." in guidance
    assert "merge_on_shared_period" in guidance
    assert "build_weighted_period_output" in guidance
    assert "merge_on_shared_period" in loop_breaker
    assert "build_weighted_period_output" in loop_breaker


def test_proportion_loop_breaker_handles_title_heavy_period_tables_without_exact_shipment_header():
    question = (
        "One table gives smartphone units shipped from 2012 to 2025, and another gives "
        "market share from 2017 to 2025. Find the overlapping period and estimate each "
        "brand's units as market_share * shipment."
    )
    skill = detect_skill(question)
    helper = select_helper(skill, question)

    loop_breaker = build_loop_breaker(skill, helper)

    assert "many brand columns" in loop_breaker
    assert "single numeric value column" in loop_breaker
    assert "shipment_value_col" in loop_breaker
    assert "rename(columns={shipment_value_col: 'Shipment'})" in loop_breaker


def test_region_growth_guidance_prefers_runtime_helper_and_chart_path():
    question = (
        "Here is a table showing internet penetration rates from 2009 to 2024. "
        "Please calculate the average internet penetration rate for each region over the years 2020-2024. "
        "Identify the region with the fastest growth rate and sort the regions by growth rate. "
        "Also provide a line chart."
    )
    skill = detect_skill(question)
    helper = select_helper(skill, question)

    guidance = build_execution_strict_rules(skill, helper)
    loop_breaker = build_loop_breaker(skill, helper)

    assert "build_region_growth_analysis" in guidance
    assert "save_plot_to_excel" in guidance or "save_plot_to_excel" in loop_breaker


def test_target_feature_correlation_guidance_prefers_one_row_feature_output():
    question = (
        "Calculate the correlation coefficient between survival and other factors such as sex, age, "
        "fare, cabin, and embarked using the Titanic dataset. Output columns should be Sex, Age, Fare, Cabin, Embarked."
    )
    skill = detect_skill(question)
    helper = select_helper(skill, question)

    plan_summary = (
        "task_type=target_feature_correlation\n"
        "target_col=Survived\n"
        "feature_cols=Sex, Age, Fare, Cabin, Embarked"
    )
    guidance = build_execution_strict_rules(skill, helper, plan_summary=plan_summary)
    loop_breaker = build_loop_breaker(skill, helper, plan_summary=plan_summary)

    assert "compute_feature_correlations" in guidance
    assert "one-row" in guidance.lower()
    assert "Titanic" not in guidance
    assert "target_col='Survived'" not in loop_breaker
    assert "['Sex', 'Age', 'Fare', 'Cabin', 'Embarked']" not in loop_breaker
    assert "target_col=Survived" in guidance
    assert "feature_cols=Sex, Age, Fare, Cabin, Embarked" in guidance
    assert "target_col=target_col" in loop_breaker
    assert "feature_cols=feature_cols" in loop_breaker
