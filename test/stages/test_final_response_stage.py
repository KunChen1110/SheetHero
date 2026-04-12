import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from src.backend.stages.final_response.stage import FinalResponseStage


def test_question_content_label_uses_helper_metadata_for_multi_key_join():
    label = FinalResponseStage._question_content_label(
        "Join the spreadsheet tables by the shared student id and semester keys.",
        {},
    )

    assert label == "multi-key join report"


def test_question_content_label_uses_helper_metadata_for_missing_data_scan():
    label = FinalResponseStage._question_content_label(
        "Identify which sheets have missing values and report the affected columns.",
        {},
    )

    assert label == "missing data report"


def test_question_content_label_uses_helper_metadata_for_dependency_schedule():
    label = FinalResponseStage._question_content_label(
        "Schedule tasks based on dependencies and include start time and end time columns.",
        {},
    )

    assert label == "task schedule"


def test_fallback_short_answer_generates_generic_average_subject():
    answer = FinalResponseStage._fallback_short_answer(
        user_question="What is the average revenue per region?",
        final_answer="42",
        validation_passed=True,
        workbook_summary={},
    )

    assert answer == "The average revenue per region is 42."
