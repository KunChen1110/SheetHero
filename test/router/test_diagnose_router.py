import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from openpyxl import load_workbook

from backend.router.diagnose_router import DiagnoseRouter


def test_self_reporting_scan_task_skips_router_issue_generation_for_generic_identifier_formats():
    question = (
        "Check whether the venue codes are inconsistent, for example A10 versus A 10, "
        "and report the issue."
    )

    assert DiagnoseRouter._is_self_reporting_issue_task(question) is True


def test_real_task3_messy_header_only_triggers_period_clarification():
    dataset_path = Path(__file__).resolve().parents[2] / "dataset" / "Task03" / "tc03_input01.xlsx"
    workbook = load_workbook(dataset_path)
    router = DiagnoseRouter(client=None, deployment="offline-test", prompt_profile="offline_strict")
    question = (
        "Here is a table showing internet penetration rates from 2009 to 2024. "
        "Please calculate the average internet penetration rate for each region over the years 2020–2024. "
        "Identify the region with the fastest growth rate and sort the regions by growth rate. "
        "Also provide a line chart where each region is represented by a different color."
    )

    decision = router.decide(question, "", {str(dataset_path): workbook})

    issue_types = [issue.get("issue_type") for issue in decision.issues]
    assert decision.should_diagnose is True
    assert issue_types == ["missing_period_endpoint"]


def test_extract_requested_years_prefers_last_explicit_range():
    question = (
        "The source table covers 2009 to 2024. "
        "Please calculate the average for the years 2020-2024 and rank the regions."
    )

    assert DiagnoseRouter._extract_requested_years(question) == [2020, 2021, 2022, 2023, 2024]
