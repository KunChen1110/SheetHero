from pathlib import Path
import os
import sys

import pandas as pd
from openpyxl import Workbook

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from backend.environment.spreadsheet.loader import load_world
from backend.environment.spreadsheet.tools.workflows import (
    _build_weighted_period_output,
    _build_grouped_assignment_join,
    _extract_period_records,
    _find_first_period_cell,
    _merge_on_shared_period,
    _select_contiguous_labeled_columns,
    build_room_format_report,
    load_all_tables,
)


def _write_workbook(path: Path, rows: list[list[object]]) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    for row in rows:
        sheet.append(row)
    workbook.save(path)


def test_identifier_format_report_is_not_room_specific(tmp_path: Path):
    workbook_path = tmp_path / "venues.xlsx"
    _write_workbook(
        workbook_path,
        [
            ["Venue Code", "Status"],
            ["A10", "Open"],
            ["A 10", "Closed"],
            ["B20", "Open"],
        ],
    )
    world = load_world([str(workbook_path)], output_path=str(tmp_path / "output.xlsx"))

    report = build_room_format_report(world)

    assert "Venue Code" in report["answer"]
    assert "A10" in report["answer"]
    assert "A 10" in report["answer"]


def test_select_contiguous_labeled_columns_stops_at_blank_or_stop_marker():
    header_row = ["", "Year", "North", "South", "West", "In %", "Ignore"]

    columns = _select_contiguous_labeled_columns(
        header_row,
        start_col_idx=2,
        stop_markers=("in %",),
    )

    assert columns == [(2, "North"), (3, "South"), (4, "West")]


def test_extract_period_records_reads_contiguous_period_block():
    rows = [
        ["Region", "North", "South"],
        ["2020", 10, 20],
        ["2021", 15, 25],
        ["", "", ""],
        ["2022", 30, 40],
    ]

    records = _extract_period_records(
        rows,
        period_col_idx=0,
        labeled_columns=[(1, "North"), (2, "South")],
        is_period_value=lambda value: str(value).isdigit(),
        period_transform=int,
    )

    assert records == [
        {"Year": 2020, "North": 10, "South": 20},
        {"Year": 2021, "North": 15, "South": 25},
    ]


def test_merge_on_shared_period_keeps_only_overlap():
    left = [
        {"Time": "Q1 2024", "North": 12.5},
        {"Time": "Q2 2024", "North": 13.0},
    ]
    right = [
        {"Time": "Q2 2024", "Shipment": 100.0},
        {"Time": "Q3 2024", "Shipment": 110.0},
    ]

    overlap_df = _merge_on_shared_period(left, right, period_col="Time")

    assert overlap_df.to_dict(orient="records") == [
        {"Time": "Q2 2024", "North": 13.0, "Shipment": 100.0},
    ]


def test_build_grouped_assignment_join_preserves_schedule_rows():
    assignment_df = pd.DataFrame(
        {
            "Assigned Tutor": ["Alice", "Alice", "Bob"],
            "Student": ["S1", "S2", "S3"],
        }
    )
    schedule_df = pd.DataFrame(
        {
            "Tutor Name": ["Alice", "Bob", "Cara"],
            "Time Slot": ["Mon 9", "Tue 10", "Wed 11"],
            "Room": ["R1", "R2", "R3"],
        }
    )

    output_df = _build_grouped_assignment_join(
        assignment_df=assignment_df,
        assignment_col="Assigned Tutor",
        entity_col="Student",
        schedule_df=schedule_df,
        resource_col="Tutor Name",
        schedule_cols=["Time Slot", "Room"],
    )

    assert output_df.to_dict(orient="records") == [
        {"Tutor Name": "Alice", "Time Slot": "Mon 9", "Room": "R1", "Student": "S1, S2"},
        {"Tutor Name": "Bob", "Time Slot": "Tue 10", "Room": "R2", "Student": "S3"},
        {"Tutor Name": "Cara", "Time Slot": "Wed 11", "Room": "R3", "Student": ""},
    ]


def test_find_first_period_cell_returns_row_and_column():
    rows = [
        ["", "", ""],
        ["Overview", "North", "South"],
        ["2021", 10, 20],
    ]

    assert _find_first_period_cell(rows, is_period_value=lambda value: str(value).isdigit()) == (2, 0)


def test_build_weighted_period_output_scales_value_columns():
    overlap_df = pd.DataFrame(
        {
            "Time": ["Q1 2024", "Q2 2024"],
            "Vivo": [10.0, 20.0],
            "Samsung": [30.0, 40.0],
            "Shipment": [100.0, 50.0],
        }
    )

    output_df = _build_weighted_period_output(
        overlap_df,
        period_col="Time",
        value_columns=["Vivo", "Samsung"],
        weight_col="Shipment",
        output_period_col="Year",
        output_label_template="{name} (Unit shipment)",
    )

    assert output_df.to_dict(orient="records") == [
        {"Year": "Q1 2024", "Vivo (Unit shipment)": 10.0, "Samsung (Unit shipment)": 30.0},
        {"Year": "Q2 2024", "Vivo (Unit shipment)": 10.0, "Samsung (Unit shipment)": 20.0},
    ]


def test_load_all_tables_prefers_structured_data_sheet_over_overview(tmp_path: Path):
    workbook_path = tmp_path / "market_share.xlsx"
    workbook = Workbook()
    overview = workbook.active
    overview.title = "Overview"
    overview.append(["Statistic as Excel data file"])
    data_sheet = workbook.create_sheet("Data")
    data_sheet.append(["Year", "Vivo", "Samsung"])
    data_sheet.append(["2024", 10, 20])
    workbook.save(workbook_path)

    world = load_world([str(workbook_path)], output_path=str(tmp_path / "output.xlsx"))
    tables = load_all_tables(world, require_primary_key=False, stop_at_note_row=False)

    assert len(tables) == 1
    assert tables[0]["sheet_name"] == "Data"
    assert tables[0]["header"] == ["Year", "Vivo", "Samsung"]


def test_load_all_tables_promotes_period_header_row_and_infers_time_column(tmp_path: Path):
    workbook_path = tmp_path / "market_share.xlsx"
    workbook = Workbook()
    overview = workbook.active
    overview.title = "Overview"
    overview.append(["Statistic as Excel data file"])
    data_sheet = workbook.create_sheet("Data")
    data_sheet.append([None])
    data_sheet.append([None])
    data_sheet.append([None, "Smartphone market share held by vendors in India Q1 2017-Q3 2025"])
    data_sheet.append([None, "Smartphone market share held by vendors in India from 1st quarter 2017 to 3rd quarter 2025"])
    data_sheet.append([None, None, "Vivo", "Samsung", "Xiaomi", "Others", None])
    data_sheet.append([None, "Q1 2017", 11, 28, 14, 47, "in %"])
    data_sheet.append([None, "Q2 2017", 13, 24, 17, 46, "in %"])
    workbook.save(workbook_path)

    world = load_world([str(workbook_path)], output_path=str(tmp_path / "output.xlsx"))
    tables = load_all_tables(world, require_primary_key=False, stop_at_note_row=False)

    assert len(tables) == 1
    assert tables[0]["header"] == ["Time", "Vivo", "Samsung", "Xiaomi", "Others"]
    assert tables[0]["rows"] == [
        ["Q1 2017", 11, 28, 14, 47],
        ["Q2 2017", 13, 24, 17, 46],
    ]


def test_load_all_tables_synthesizes_time_value_headers_for_period_series_sheet(tmp_path: Path):
    workbook_path = tmp_path / "shipments.xlsx"
    workbook = Workbook()
    overview = workbook.active
    overview.title = "Overview"
    overview.append(["Statistic as Excel data file"])
    data_sheet = workbook.create_sheet("Data")
    data_sheet.append([None])
    data_sheet.append([None])
    data_sheet.append([None, "India smartphone unit shipments Q2 2012-Q2 2025"])
    data_sheet.append([None, "Total number of smartphone unit shipments in India from 2nd quarter of 2012 to 2nd quarter of 2025"])
    data_sheet.append([None])
    data_sheet.append([None, "Q2 2012", 4])
    data_sheet.append([None, "Q3 2012", 4])
    data_sheet.append([None, "Q4 2012", 5])
    workbook.save(workbook_path)

    world = load_world([str(workbook_path)], output_path=str(tmp_path / "output.xlsx"))
    tables = load_all_tables(world, require_primary_key=False, stop_at_note_row=False)

    assert len(tables) == 1
    assert tables[0]["header"] == ["Time", "Value"]
    assert tables[0]["rows"] == [
        ["Q2 2012", 4],
        ["Q3 2012", 4],
        ["Q4 2012", 5],
    ]
