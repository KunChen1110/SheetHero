import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from src.backend.skills.runtime_plan import RuntimeExecutionPlan
from src.backend.stages.execution.skill.question_inference import ExecutionQuestionInferenceAdvisor


class _DummyRuntime:
    def _observed_header_set(self):
        return {
            "Student ID",
            "Course",
            "Semester",
            "Final Score",
            "Instructor",
        }


def test_grounded_multi_key_join_hint_uses_capability_based_inference():
    advisor = ExecutionQuestionInferenceAdvisor(_DummyRuntime())

    hint = advisor.build_skill_grounded_call_hint(
        "build_multi_key_relational_join_report",
        "Join the tables by student id and semester, then compare the final score by course.",
        ["Student ID", "Course", "Semester", "Final Score", "Instructor"],
    )

    assert "build_multi_key_relational_join_report" in hint
    assert "key_headers=['Student ID', 'Semester']" in hint


def test_infer_target_feature_plan_uses_runtime_headers_only():
    advisor = ExecutionQuestionInferenceAdvisor(_DummyRuntime())

    plan = advisor.infer_runtime_plan(
        skill_name="statistical",
        helper_name="compute_feature_correlations",
        user_question=(
            "Calculate the correlation coefficient between survival and other factors such as "
            "sex, age, fare, cabin, and embarked."
        ),
        observed_headers=["PassengerId", "Survived", "Sex", "Age", "Fare", "Cabin", "Embarked"],
    )

    assert isinstance(plan, RuntimeExecutionPlan)
    assert plan.task_type == "target_feature_correlation"
    assert plan.target_col == "Survived"
    assert plan.feature_cols == ("Sex", "Age", "Fare", "Cabin", "Embarked")


def test_infer_target_feature_plan_does_not_invent_missing_columns():
    advisor = ExecutionQuestionInferenceAdvisor(_DummyRuntime())

    plan = advisor.infer_runtime_plan(
        skill_name="statistical",
        helper_name="compute_feature_correlations",
        user_question="Calculate the correlation coefficient between survival and sex, age, fare, cabin, and embarked.",
        observed_headers=["Survived", "Sex", "Fare"],
    )

    assert plan.target_col == "Survived"
    assert plan.feature_cols == ("Sex", "Fare")
    assert "Age" not in plan.feature_cols
    assert "Cabin" not in plan.feature_cols
    assert "Embarked" not in plan.feature_cols


def test_plan_prompt_summary_uses_runtime_values_not_recipe_text():
    plan = RuntimeExecutionPlan(
        skill_name="statistical",
        task_type="target_feature_correlation",
        table_roles={"primary_table": "input.csv"},
        target_col="Survived",
        feature_cols=("Sex", "Fare"),
        output_contract={"kind": "ranked_rows", "sheet_name": "Output"},
    )

    summary = plan.to_prompt_summary()

    assert "target_col=Survived" in summary
    assert "feature_cols=Sex, Fare" in summary
    assert "use Survived as target" not in summary.lower()
