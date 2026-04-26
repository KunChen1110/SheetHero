import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from backend.skills.runtime_plan import RuntimeExecutionPlan
from backend.stages.execution.skill.question_inference import ExecutionQuestionInferenceAdvisor


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


def test_infer_regression_plan_uses_target_like_column_and_all_predictors():
    advisor = ExecutionQuestionInferenceAdvisor(_DummyRuntime())

    plan = advisor.infer_runtime_plan(
        skill_name="statistical",
        helper_name="fit_linear_regression_weights",
        user_question=(
            "Fit a linear regression model to estimate the weight of temperature, price, "
            "and number of tourists in predicting ice cream sales."
        ),
        observed_headers=[
            "Temperature (F)",
            "Ice-cream Price ($)",
            "Number of Tourists (thousands)",
            "Ice Cream Sales ($,thousands)",
            "Did it rain on that day?",
        ],
    )

    assert plan.task_type == "regression"
    assert plan.target_col == "Ice Cream Sales ($,thousands)"
    assert plan.feature_cols == (
        "Temperature (F)",
        "Ice-cream Price ($)",
        "Number of Tourists (thousands)",
        "Did it rain on that day?",
    )


def test_infer_regression_plan_does_not_treat_day_suffix_as_target_marker_when_headers_are_sorted():
    advisor = ExecutionQuestionInferenceAdvisor(_DummyRuntime())
    observed_headers = sorted(
        [
            "Temperature (F)",
            "Ice-cream Price ($)",
            "Number of Tourists (thousands)",
            "Ice Cream Sales ($,thousands)",
            "Did it rain on that day?",
        ]
    )

    plan = advisor.infer_runtime_plan(
        skill_name="statistical",
        helper_name="fit_linear_regression_weights",
        user_question=(
            "Assume a linear relationship between ice-cream sales and three factors: "
            "temperature, price, and number of tourists. Fit a linear regression model "
            "to estimate the weight (coefficient) of each factor in predicting sales."
        ),
        observed_headers=observed_headers,
    )

    assert plan.target_col == "Ice Cream Sales ($,thousands)"
    assert "Did it rain on that day?" in plan.feature_cols
