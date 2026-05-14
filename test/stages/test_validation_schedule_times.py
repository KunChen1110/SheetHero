from pathlib import Path

from openpyxl import Workbook

from backend.stages.validation.inspectors.workbook import WorkbookValidationInspectorMixin


def test_schedule_time_parser_accepts_extended_hours():
    assert WorkbookValidationInspectorMixin._parse_time_to_minutes("26:00") == 26 * 60
    assert WorkbookValidationInspectorMixin._parse_time_to_minutes("02:30") == 150


def test_generic_workbook_accepts_summary_only_output_when_detail_not_required(tmp_path: Path):
    workbook_path = tmp_path / "summary_only.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Output"
    sheet.append(["Metric", "Value"])
    sheet.append(["Correlation", 0.81])
    sheet.append(["Rating 1 Avg Salary", 5000])
    workbook.save(workbook_path)

    issues = WorkbookValidationInspectorMixin._inspect_saved_generic_workbook(
        str(workbook_path),
        need_detail=False,
        need_summary=True,
    )

    assert issues == []
