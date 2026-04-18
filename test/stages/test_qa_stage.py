import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from backend.stages.qa.stage import QualityAssuranceStage


def test_start_groups_same_missing_value_column_into_one_policy_issue():
    stage = QualityAssuranceStage(client=None, deployment="offline-test", prompt_profile="offline_strict")
    questions = [
        {
            "id": 1,
            "issue_type": "missing_value",
            "description": "Row 12 has a missing `Cabin` value.",
            "metadata": {"sheet_key": "titanic.xlsx::Sheet1", "column": "Cabin", "excel_row": 12},
        },
        {
            "id": 2,
            "issue_type": "missing_value",
            "description": "Row 45 has a missing `Cabin` value.",
            "metadata": {"sheet_key": "titanic.xlsx::Sheet1", "column": "Cabin", "excel_row": 45},
        },
    ]

    stage.start(questions, original_question="Calculate the correlation coefficient for the target and other factors.")

    assert len(stage.unresolved_problems) == 1
    grouped = stage.unresolved_problems[0]
    assert grouped["issue_type"] == "missing_value_policy"
    assert grouped["metadata"]["column"] == "Cabin"
    assert grouped["metadata"]["affected_rows"] == [12, 45]


def test_finalize_exports_structured_cleaning_policy_plan():
    stage = QualityAssuranceStage(client=None, deployment="offline-test", prompt_profile="offline_strict")
    grouped_problem = {
        "id": "missing_value::titanic.xlsx::Sheet1::Cabin",
        "issue_type": "missing_value_policy",
        "description": "Column `Cabin` has multiple missing values.",
        "question": "For missing `Cabin` values, should I leave them blank, fill a default, or drop those rows?",
        "metadata": {"sheet_key": "titanic.xlsx::Sheet1", "column": "Cabin", "affected_rows": [12, 45]},
    }

    stage.start([grouped_problem], original_question="Calculate the correlation coefficient for the target and other factors.")
    assert stage.next_question_payload() is not None
    stage.consume_user_reply("Leave them blank.")
    stage.finalize_decision()

    policy_plans = stage.export_cleaning_policy_plans()

    assert len(policy_plans) == 1
    assert policy_plans[0]["policy_kind"] == "missing_value"
    assert policy_plans[0]["column"] == "Cabin"
    assert policy_plans[0]["resolution"] == "leave_blank"


def test_match_reply_accepts_short_normalization_choice_without_llm():
    stage = QualityAssuranceStage(client=None, deployment="offline-test")
    problem = {
        "issue_type": "format_inconsistency",
        "question": (
            "I noticed the `Venue Code` column uses both `A10` and `A 10` for what looks like "
            "the same value. Should I standardize it as `A10` or `A 10`?"
        ),
        "metadata": {
            "sheet_key": "events.xlsx::Sheet1",
            "column": "Venue Code",
        },
    }

    matched, action, feedback = stage._match_reply(problem, "Use A10.")

    assert matched is True
    assert action == "Standardize `Venue Code` in `events.xlsx::Sheet1` to `A10`."
    assert feedback == ""


def test_missing_dependency_root_reply_resolves_without_llm():
    stage = QualityAssuranceStage(client=None, deployment="offline-test")
    problem = {
        "id": 1,
        "issue_type": "missing_value",
        "description": "Task A has a blank Depends on value.",
        "question": "The `Depends on` cell for task `Task A` is blank. Should it mean this task is a root task with no dependency, or should I fill a predecessor ID?",
        "metadata": {
            "sheet_key": "plan.xlsx::Tasks",
            "column": "Depends on",
            "excel_row": 7,
        },
    }

    stage.start([problem], original_question="Build the dependency schedule.")
    assert stage.next_question_payload() is not None
    stage.consume_user_reply("Leave it blank. It is a root task with no dependency.")
    stage.finalize_decision()

    assert stage.get_last_mismatch() == ""
    assert stage.export_cleaning_actions() == []
    assert stage.export_interpretation_policies() == [
        "Interpret blank `Depends on` at Excel row 7 in `plan.xlsx::Tasks` as meaning the task is a root task with no prerequisite dependency."
    ]


def test_match_reply_resolves_spacing_preference_without_llm():
    stage = QualityAssuranceStage(client=None, deployment="offline-test")
    problem = {
        "issue_type": "format_inconsistency",
        "question": (
            "I noticed the `Venue Code` column uses both `A10` and `A 10` for what looks like "
            "the same value. Should I standardize it as `A10` or `A 10`?"
        ),
        "metadata": {
            "sheet_key": "events.xlsx::Sheet1",
            "column": "Venue Code",
        },
    }

    matched, action, feedback = stage._match_reply(problem, "Use the version with a space.")

    assert matched is True
    assert action == "Standardize `Venue Code` in `events.xlsx::Sheet1` to `A 10`."
    assert feedback == ""


def test_match_reply_resolves_ordinal_option_without_llm():
    stage = QualityAssuranceStage(client=None, deployment="offline-test")
    problem = {
        "issue_type": "format_inconsistency",
        "question": (
            "I noticed the `Venue Code` column uses both `A10` and `A 10` for what looks like "
            "the same value. Should I standardize it as `A10` or `A 10`?"
        ),
        "metadata": {
            "sheet_key": "events.xlsx::Sheet1",
            "column": "Venue Code",
        },
    }

    matched, action, feedback = stage._match_reply(problem, "Use the second one.")

    assert matched is True
    assert action == "Standardize `Venue Code` in `events.xlsx::Sheet1` to `A 10`."
    assert feedback == ""


def test_missing_key_column_reply_creates_interpretation_policy_without_llm():
    stage = QualityAssuranceStage(client=None, deployment="offline-test")
    problem = {
        "id": 2,
        "issue_type": "missing_key_column",
        "description": "In sheet `scores.xlsx::Scores`, no clear matching key column was found for the multi-file task.",
        "question": (
            "I could not find a clear matching key in `scores.xlsx` / `Scores` for this multi-file task. "
            "The other file(s) appear to match on fields like `Student ID` and `Semester`. "
            "Which column in this sheet should I use to match rows?"
        ),
        "metadata": {
            "sheet_key": "scores.xlsx::Scores",
            "candidate_keys": ["Student ID", "Semester"],
        },
    }

    stage.start([problem], original_question="Join the roster with the score table.")
    assert stage.next_question_payload() is not None
    stage.consume_user_reply("Use Student ID as the join key.")
    stage.finalize_decision()

    assert stage.get_last_mismatch() == ""
    assert stage.export_cleaning_actions() == []
    assert stage.export_interpretation_policies() == [
        "Use `Student ID` as the matching key for sheet `scores.xlsx::Scores` during multi-file alignment."
    ]


def test_missing_key_column_ordinal_reply_creates_policy_without_llm():
    stage = QualityAssuranceStage(client=None, deployment="offline-test")
    problem = {
        "id": 2,
        "issue_type": "missing_key_column",
        "description": "In sheet `scores.xlsx::Scores`, no clear matching key column was found for the multi-file task.",
        "question": (
            "I could not find a clear matching key in `scores.xlsx` / `Scores` for this multi-file task. "
            "The other file(s) appear to match on fields like `Student ID` and `Semester`. "
            "Which column in this sheet should I use to match rows?"
        ),
        "metadata": {
            "sheet_key": "scores.xlsx::Scores",
            "candidate_keys": ["Student ID", "Semester"],
        },
    }

    stage.start([problem], original_question="Join the roster with the score table.")
    assert stage.next_question_payload() is not None
    stage.consume_user_reply("Use the second option.")
    stage.finalize_decision()

    assert stage.get_last_mismatch() == ""
    assert stage.export_cleaning_actions() == []
    assert stage.export_interpretation_policies() == [
        "Use `Semester` as the matching key for sheet `scores.xlsx::Scores` during multi-file alignment."
    ]


def test_duplicate_header_reply_creates_authoritative_header_policy_without_llm():
    stage = QualityAssuranceStage(client=None, deployment="offline-test")
    problem = {
        "id": 3,
        "issue_type": "duplicate_header",
        "description": "In sheet `roster.xlsx::Sheet1`, multiple headers normalize to the same meaning (`Student ID`, `Student_ID`).",
        "question": (
            "I noticed that in `roster.xlsx` / `Sheet1`, the headers `Student ID` and `Student_ID` "
            "look like the same field after normalization. Which header should I treat as the authoritative one for this task?"
        ),
        "metadata": {
            "sheet_key": "roster.xlsx::Sheet1",
            "headers": ["Student ID", "Student_ID"],
        },
    }

    stage.start([problem], original_question="Join the roster with the score table.")
    assert stage.next_question_payload() is not None
    stage.consume_user_reply("Use Student_ID.")
    stage.finalize_decision()

    assert stage.get_last_mismatch() == ""
    assert stage.export_cleaning_actions() == []
    assert stage.export_interpretation_policies() == [
        "Treat header `Student_ID` as the authoritative field in `roster.xlsx::Sheet1` when equivalent normalized headers compete."
    ]


def test_unit_format_reply_resolves_normalization_choice_without_llm():
    stage = QualityAssuranceStage(client=None, deployment="offline-test")
    problem = {
        "id": 4,
        "issue_type": "unit_or_time_format",
        "description": "In sheet `marketing.xlsx::Sheet1`, column `CTR` mixes raw fractions and percentage-scale values.",
        "question": (
            "I noticed that in `marketing.xlsx` / `Sheet1`, column `CTR` mixes values like "
            "`12` and `0.08`. This looks like some rows may use percentage scale while others use raw fractions. "
            "Should I convert the fraction-style values to the same percentage scale before continuing?"
        ),
        "metadata": {
            "sheet_key": "marketing.xlsx::Sheet1",
            "column": "CTR",
            "formats": ["percentage_scale", "raw_fraction"],
        },
    }

    matched, action, feedback = stage._match_reply(
        problem,
        "Yes, convert the fraction values to percentages before continuing.",
    )

    assert matched is True
    assert action == "Standardize `CTR` in `marketing.xlsx::Sheet1` to `percentage_scale`."
    assert feedback == ""


def test_missing_period_endpoint_reply_creates_latest_year_policy_without_llm():
    stage = QualityAssuranceStage(client=None, deployment="offline-test")
    problem = {
        "id": 5,
        "issue_type": "missing_period_endpoint",
        "description": "In sheet `growth.xlsx::Data`, requested period values [2024] are missing from the available data.",
        "question": (
            "I noticed that `growth.xlsx` / `Data` does not contain the requested year(s) 2024. "
            "The latest available year is `2023`. Should I use the latest available year instead and state that assumption in the result?"
        ),
        "metadata": {
            "sheet_key": "growth.xlsx::Data",
            "requested_years": [2020, 2021, 2022, 2023, 2024],
            "available_years": [2020, 2021, 2022, 2023],
            "available_requested_years": [2020, 2021, 2022, 2023],
        },
    }

    stage.start([problem], original_question="Calculate the growth rate for 2020 to 2024.")
    assert stage.next_question_payload() is not None
    stage.consume_user_reply("Yes, use the latest available year and mention that assumption.")
    stage.finalize_decision()

    assert stage.get_last_mismatch() == ""
    assert stage.export_cleaning_actions() == []
    assert stage.export_interpretation_policies() == [
        "When requested years are unavailable in `growth.xlsx::Data`, use the latest available year `2023` instead and state that assumption in the result."
    ]


def test_offline_missing_period_endpoint_reply_does_not_become_cleaning_action():
    stage = QualityAssuranceStage(client=None, deployment="offline-test", prompt_profile="offline_strict")
    problem = {
        "id": 6,
        "issue_type": "missing_period_endpoint",
        "description": "In sheet `growth.xlsx::Data`, requested period values [2024] are missing from the available data.",
        "question": (
            "I noticed that `growth.xlsx` / `Data` does not contain the requested year(s) 2024. "
            "The latest available year is `2023`. Should I use the latest available year instead and state that assumption in the result?"
        ),
        "metadata": {
            "sheet_key": "growth.xlsx::Data",
            "requested_years": [2020, 2021, 2022, 2023, 2024],
            "available_years": [2020, 2021, 2022, 2023],
            "available_requested_years": [2020, 2021, 2022, 2023],
        },
    }

    stage.start([problem], original_question="Calculate the growth rate for 2020 to 2024.")
    assert stage.next_question_payload() is not None
    stage.consume_user_reply(
        "Exclude 2024 from the calculation and use the latest available year instead."
    )
    stage.finalize_decision()

    assert stage.export_cleaning_actions() == []
    assert stage.export_interpretation_policies() == [
        "When requested years are unavailable in `growth.xlsx::Data`, restrict the analysis window to the available requested years `2020`-`2023` and state that adjustment in the result."
    ]


def test_missing_period_endpoint_shift_reply_creates_restricted_window_policy():
    stage = QualityAssuranceStage(client=None, deployment="offline-test", prompt_profile="offline_strict")
    problem = {
        "id": 7,
        "issue_type": "missing_period_endpoint",
        "description": "In sheet `growth.xlsx::Data`, requested period values [2020] are missing from the available data.",
        "question": (
            "I noticed that `growth.xlsx` / `Data` does not contain the requested year(s) 2020. "
            "Within the requested span, the available years are `2021` to `2024`. "
            "Should I shrink the analysis window to the available requested years, interpolate the missing years, or state that the requested period is unavailable?"
        ),
        "metadata": {
            "sheet_key": "growth.xlsx::Data",
            "requested_years": [2020, 2021, 2022, 2023, 2024],
            "available_years": [2021, 2022, 2023, 2024],
            "available_requested_years": [2021, 2022, 2023, 2024],
        },
    }

    stage.start([problem], original_question="Calculate the average rate for 2020 to 2024.")
    assert stage.next_question_payload() is not None
    stage.consume_user_reply("Exclude 2020 and shift the analysis period to 2021-2024.")
    stage.finalize_decision()

    assert stage.export_cleaning_actions() == []
    assert stage.export_interpretation_policies() == [
        "When requested years are unavailable in `growth.xlsx::Data`, restrict the analysis window to the available requested years `2021`-`2024` and state that adjustment in the result."
    ]


def test_missing_value_natural_language_reply_uses_llm_semantic_fallback(monkeypatch):
    from backend.stages.qa import stage as qa_stage_module

    monkeypatch.setattr(
        qa_stage_module,
        "call_llm",
        lambda *_args, **_kwargs: "\n".join(
            [
                "MATCH: YES",
                "DECISION_KIND: fill_value",
                "VALUE: 100",
                "SELECTED_OPTION:",
                "POLICY_KIND:",
                "ACTION: Fill the missing value in `Daily Spending (£)` at Excel row 5 in `tc01_input01.xlsx::Sheet1` with 100.",
            ]
        ),
    )

    stage = QualityAssuranceStage(
        client=object(),
        deployment="offline-test",
        prompt_profile="offline_strict",
    )
    problem = {
        "id": 8,
        "issue_type": "missing_value",
        "description": "In sheet `tc01_input01.xlsx::Sheet1`, column `Daily Spending (£)` is empty at Excel row 5.",
        "question": "In sheet `tc01_input01.xlsx::Sheet1`, column `Daily Spending (£)` is empty at Excel row 5. How should I handle it?",
        "metadata": {
            "sheet_key": "tc01_input01.xlsx::Sheet1",
            "column": "Daily Spending (£)",
            "excel_row": 5,
        },
    }

    matched, action, feedback = stage._match_reply(
        problem,
        "That blank spending cell should count as one hundred pounds.",
    )

    assert matched is True
    assert action == "Fill the missing value in `Daily Spending (£)` at Excel row 5 in `tc01_input01.xlsx::Sheet1` with 100."
    assert feedback == ""


def test_missing_value_structured_llm_decision_builds_local_action(monkeypatch):
    from backend.stages.qa import stage as qa_stage_module

    monkeypatch.setattr(
        qa_stage_module,
        "call_llm",
        lambda *_args, **_kwargs: "\n".join(
            [
                "MATCH: YES",
                "DECISION_KIND: fill_value",
                "VALUE: 250",
                "SELECTED_OPTION:",
                "POLICY_KIND:",
                "ACTION:",
            ]
        ),
    )

    stage = QualityAssuranceStage(
        client=object(),
        deployment="offline-test",
        prompt_profile="offline_strict",
    )
    problem = {
        "id": 9,
        "issue_type": "missing_value",
        "description": "In sheet `tc01_input02.xlsx::Sheet1`, column `Daily Spending (£)` is empty at Excel row 7.",
        "question": "In sheet `tc01_input02.xlsx::Sheet1`, column `Daily Spending (£)` is empty at Excel row 7. How should I handle it?",
        "metadata": {
            "sheet_key": "tc01_input02.xlsx::Sheet1",
            "column": "Daily Spending (£)",
            "excel_row": 7,
        },
    }

    matched, action, feedback = stage._match_reply(
        problem,
        "Please use two hundred and fifty pounds for that missing spending value.",
    )

    assert matched is True
    assert action == "Fill the missing value in `Daily Spending (£)` at Excel row 7 in `tc01_input02.xlsx::Sheet1` with 250."
    assert feedback == ""
