from __future__ import annotations

from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from openpyxl import Workbook

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.backend.environment.spreadsheet.loader import load_world
from src.backend.environment.sandbox.sandbox import Sandbox
from src.backend.environment.spreadsheet.tools.workflows import (
    build_relational_join_enrichment_report,
    build_grouped_aggregation_ranking_report,
    build_time_series_aggregation_report,
)
from src.backend.stages.execution.runtime import ExecutionRuntime
from src.backend.stages.validation.runtime import ValidationRuntime
from src.backend.skills import detect_skill, select_helper


def _write_workbook(path: Path, sheet_name: str, rows: list[list[object]]) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name
    for row in rows:
        ws.append(row)
    wb.save(path)


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    with TemporaryDirectory(prefix="sheethero_skill_regression_") as temp_dir:
        root = Path(temp_dir)

        print("[skill regression] helper: schema-aligned merge summary")
        merge_a = root / "merge_a.xlsx"
        merge_b = root / "merge_b.xlsx"
        _write_workbook(
            merge_a,
            "Sheet1",
            [
                ["Date", "Category", "Daily Spending (£)", "Notes"],
                ["2025-11-01", "Food", 106.11, "Lunch"],
                ["2025-11-02", "Food", 43.62, "Groceries"],
            ],
        )
        _write_workbook(
            merge_b,
            "Sheet1",
            [
                ["Date", "Category", "Daily Spending (£)", "Notes"],
                ["2025-11-03", "Other", 89.53, "Gift"],
                ["2025-11-04", "Entertainment", 100.00, "Gift"],
            ],
        )
        merge_sandbox = Sandbox(
            excel_paths=[str(merge_a), str(merge_b)],
            output_preferences={},
            output_path=str(root / "merge_runtime_output.xlsx"),
        )
        merge_runtime = ExecutionRuntime(
            client=None,
            deployment="offline-test",
            sandbox=merge_sandbox,
            excel_context_execution="",
        )
        merge_exec = merge_runtime.run(
            understanding_output="",
            user_question=(
                "Merge the files into a single table, calculate the total and average Daily Spending (£), "
                "and highlight the rows with the highest Daily Spending (£)."
            ),
            max_turns=1,
        )
        _assert(merge_exec["success"], "Expected schema-aligned merge fast-path to succeed.")
        merge_validation = ValidationRuntime(
            client=None,
            deployment="offline-test",
            excel_context_understanding="",
        )
        merge_validation_result = merge_validation.run(
            merge_exec,
            (
                "Merge the files into a single table, calculate the total and average Daily Spending (£), "
                "and highlight the rows with the highest Daily Spending (£)."
            ),
            "",
        )
        _assert(merge_validation_result["validation_passed"], "Expected schema-aligned merge fast-path output to pass validation.")

        print("[skill regression] helper: grouped aggregation")
        grouped_path = root / "grouped_scores.xlsx"
        _write_workbook(
            grouped_path,
            "Scores",
            [
                ["Student", "Course", "Semester", "Score"],
                ["Alice", "Math", "Autumn", 82],
                ["Bob", "Math", "Autumn", 74],
                ["Cara", "Physics", "Autumn", 91],
                ["Dan", "Physics", "Spring", 87],
                ["Eva", "History", "Autumn", 79],
                ["Finn", "History", "Spring", 88],
                ["Gina", "Math", "Spring", 95],
            ],
        )
        grouped_world = load_world([str(grouped_path)], output_path=str(root / "grouped_output.xlsx"))
        grouped_report = build_grouped_aggregation_ranking_report(
            grouped_world,
            file_path=None,
            group_cols=["Course"],
            value_col="Score",
            aggregate="mean",
            sort_desc=True,
        )
        grouped_rows = grouped_report["output_df"].to_dict("records")
        _assert(grouped_rows[0]["Course"] == "Physics", "Expected Physics to rank first by average score.")
        _assert(round(float(grouped_rows[0]["Average Score"]), 4) == 89.0, "Unexpected Physics average score.")

        print("[skill regression] helper: grouped inference")
        spending_path = root / "category_spend.xlsx"
        _write_workbook(
            spending_path,
            "Budget",
            [
                ["Date", "Category", "Daily Spending (£)", "Notes"],
                ["2025-01-01", "Food", 30.0, "Lunch"],
                ["2025-01-02", "Food", 45.0, "Groceries"],
                ["2025-01-03", "Transport", 12.5, "Bus"],
                ["2025-01-04", "Transport", 20.0, "Train"],
                ["2025-01-05", "Books", 55.0, "Textbook"],
            ],
        )
        spend_world = load_world([str(spending_path)], output_path=str(root / "spend_output.xlsx"))
        inferred_grouped = build_grouped_aggregation_ranking_report(
            spend_world,
            aggregate="mean",
            sort_desc=True,
        )
        inferred_rows = inferred_grouped["output_df"].to_dict("records")
        _assert(inferred_rows[0]["Category"] == "Books", "Expected Books to rank first by average spending.")
        _assert(
            round(float(inferred_rows[0]["Average Daily Spending (£)"]), 2) == 55.0,
            "Unexpected Books average spending.",
        )

        print("[skill regression] helper: temporal aggregation")
        time_path_a = root / "spend_a.xlsx"
        time_path_b = root / "spend_b.xlsx"
        _write_workbook(
            time_path_a,
            "Sheet1",
            [
                ["Date", "Daily Spending (£)"],
                ["2025-11-01", 106.11],
                ["2025-11-02", 43.62],
            ],
        )
        _write_workbook(
            time_path_b,
            "Sheet1",
            [
                ["Date", "Daily Spending (£)"],
                ["2025-11-03", 89.53],
                ["2025-11-04", 100.00],
            ],
        )
        time_world = load_world([str(time_path_a), str(time_path_b)], output_path=str(root / "time_output.xlsx"))
        time_report = build_time_series_aggregation_report(
            time_world,
            file_path=None,
            date_col="Date",
            value_col=None,
            period="month",
            aggregate="mean",
            window_years=5,
            period_mode="year_month",
            sort_desc=True,
        )
        time_rows = time_report["output_df"].to_dict("records")
        _assert(time_rows[0]["Period"] == "2025-11", "Expected a YYYY-MM monthly period label.")

        print("[skill regression] helper: relational join")
        join_a = root / "student_core.xlsx"
        join_b = root / "student_program.xlsx"
        _write_workbook(
            join_a,
            "Sheet1",
            [
                ["Student ID", "Student Name"],
                ["S01", "Alice"],
                ["S02", "Bob"],
            ],
        )
        _write_workbook(
            join_b,
            "Sheet1",
            [
                ["Student ID", "Program"],
                ["S01", "CS"],
                ["S02", "Math"],
            ],
        )
        join_world = load_world([str(join_a), str(join_b)], output_path=str(root / "join_output.xlsx"))
        join_report = build_relational_join_enrichment_report(
            join_world,
            key_header=None,
            how="inner",
        )
        join_rows = join_report["output_df"].to_dict("records")
        _assert(len(join_rows) == 2, "Expected two joined rows in relational join report.")
        _assert(join_rows[0]["Program"] in {"CS", "Math"}, "Expected joined Program column in relational report.")

        print("[skill regression] detector coverage")

        def _assert_skill_helper(question: str, skill_name: str, helper_name: str | None = None) -> None:
            skill = detect_skill(question)
            _assert(skill is not None, f"Expected `{question}` to match the `{skill_name}` skill.")
            _assert(skill.name == skill_name, f"Expected `{question}` to map to `{skill_name}`, got `{skill.name}`.")
            if helper_name is not None:
                helper = select_helper(skill, question)
                _assert(helper is not None, f"Expected `{question}` to select helper `{helper_name}`.")
                _assert(
                    helper.name == helper_name,
                    f"Expected `{question}` to select `{helper_name}`, got `{helper.name}`.",
                )

        _assert_skill_helper(
            "Calculate the average score for each course and sort the results from highest to lowest.",
            "aggregate",
            "build_grouped_aggregation_ranking_report",
        )
        _assert_skill_helper(
            "Using the Date and Daily Spending columns, calculate the average spending for each YYYY-MM period within the latest 5 years and sort descending.",
            "aggregate",
            "build_time_series_aggregation_report",
        )
        _assert_skill_helper(
            "Merge the student information file with the program file into a single table using the shared student ID.",
            "merge",
            "build_relational_join_enrichment_report",
        )
        _assert_skill_helper(
            "Merge the enrollment file with the attendance file using Student ID and Term as the shared keys.",
            "merge",
            "build_multi_key_relational_join_report",
        )
        _assert_skill_helper(
            "Fill the missing program values in the primary file using the reference file with the shared student ID.",
            "merge",
            "fill_missing_from_reference",
        )
        _assert_skill_helper(
            "Identify where values are missing in the file and report the missing data.",
            "scan",
            "build_missing_data_report",
        )
        _assert_skill_helper(
            "Check whether the room identifiers are inconsistent, for example C80 versus C 80.",
            "scan",
            "build_room_format_report",
        )
        _assert_skill_helper(
            "Create a task schedule based on task durations and dependencies.",
            "schedule",
            "build_dependency_schedule",
        )
        _assert_skill_helper(
            "Use study hours, attendance, and homework score to fit a regression model predicting final score.",
            "statistical",
            "fit_linear_regression_weights",
        )
        _assert_skill_helper(
            "Build a correlation matrix for sepal length, sepal width, petal length, and petal width.",
            "statistical",
            "build_correlation_matrix_table",
        )
        _assert_skill_helper(
            "Analyze the correlations between sepal length, sepal width, petal length, and petal width.",
            "statistical",
            "build_correlation_matrix_table",
        )
        _assert_skill_helper(
            "Audit the spreadsheet for null values and report which fields are missing.",
            "scan",
            "build_missing_data_report",
        )
        _assert_skill_helper(
            "Create a schedule showing each student with their assigned professor meeting slot and room.",
            "schedule",
            "build_relational_assignment_schedule_report",
        )
        _assert_skill_helper(
            "Build a roster showing each advisee with the assigned advisor availability slot and venue.",
            "schedule",
            "build_relational_assignment_schedule_report",
        )
        _assert_skill_helper(
            "Allocate students to rooms based on room capacities and available seats.",
            "schedule",
            "build_capacity_constrained_allocation_report",
        )
        _assert_skill_helper(
            "Place participants into lab sessions according to available slots and remaining capacity.",
            "schedule",
            "build_capacity_constrained_allocation_report",
        )

        print("[skill regression] runtime: grouped")
        grouped_sandbox = Sandbox(
            excel_paths=[str(grouped_path)],
            output_preferences={},
            output_path=str(root / "grouped_runtime_output.xlsx"),
        )
        grouped_runtime = ExecutionRuntime(
            client=None,
            deployment="offline-test",
            sandbox=grouped_sandbox,
            excel_context_execution="",
        )
        grouped_exec = grouped_runtime.run(
            understanding_output="",
            user_question="Calculate the average score for each course and sort the results from highest to lowest.",
            max_turns=1,
        )
        _assert(grouped_exec["success"], "Expected grouped execution fast-path to succeed.")
        _assert(Path(grouped_exec["answer"]).exists(), "Expected grouped fast-path to save an output workbook.")
        grouped_validation = ValidationRuntime(
            client=None,
            deployment="offline-test",
            excel_context_understanding="",
        )
        grouped_validation_result = grouped_validation.run(
            grouped_exec,
            "Calculate the average score for each course and sort the results from highest to lowest.",
            "",
        )
        _assert(grouped_validation_result["validation_passed"], "Expected grouped fast-path output to pass validation.")

        print("[skill regression] runtime: temporal")
        temporal_sandbox = Sandbox(
            excel_paths=[str(time_path_a), str(time_path_b)],
            output_preferences={},
            output_path=str(root / "temporal_runtime_output.xlsx"),
        )
        temporal_runtime = ExecutionRuntime(
            client=None,
            deployment="offline-test",
            sandbox=temporal_sandbox,
            excel_context_execution="",
        )
        temporal_exec = temporal_runtime.run(
            understanding_output="",
            user_question=(
                "Using the Date and Daily Spending (£) columns, calculate the average spending "
                "for each YYYY-MM period within the latest 5 years and sort descending."
            ),
            max_turns=1,
        )
        _assert(temporal_exec["success"], "Expected temporal execution fast-path to succeed.")
        _assert(Path(temporal_exec["answer"]).exists(), "Expected temporal fast-path to save an output workbook.")
        temporal_validation = ValidationRuntime(
            client=None,
            deployment="offline-test",
            excel_context_understanding="",
        )
        temporal_validation_result = temporal_validation.run(
            temporal_exec,
            "Using the Date and Daily Spending (£) columns, calculate the average spending for each YYYY-MM period within the latest 5 years and sort descending.",
            "",
        )
        _assert(temporal_validation_result["validation_passed"], "Expected temporal fast-path output to pass validation.")

        print("[skill regression] runtime: relational join")
        join_sandbox = Sandbox(
            excel_paths=[str(join_a), str(join_b)],
            output_preferences={},
            output_path=str(root / "join_runtime_output.xlsx"),
        )
        join_runtime = ExecutionRuntime(
            client=None,
            deployment="offline-test",
            sandbox=join_sandbox,
            excel_context_execution="",
        )
        join_exec = join_runtime.run(
            understanding_output="",
            user_question="Merge the student information file with the program file into a single table using the shared student ID.",
            max_turns=1,
        )
        _assert(join_exec["success"], "Expected relational join fast-path to succeed.")
        _assert(Path(join_exec["answer"]).exists(), "Expected relational join fast-path to save an output workbook.")
        join_validation = ValidationRuntime(
            client=None,
            deployment="offline-test",
            excel_context_understanding="",
        )
        join_validation_result = join_validation.run(
            join_exec,
            "Merge the student information file with the program file into a single table using the shared student ID.",
            "",
        )
        _assert(join_validation_result["validation_passed"], "Expected relational join fast-path output to pass validation.")

        print("[skill regression] runtime: composite-key relational join")
        enrollment_path = root / "enrollment.xlsx"
        attendance_path = root / "attendance.xlsx"
        _write_workbook(
            enrollment_path,
            "Sheet1",
            [
                ["Student ID", "Term", "Student Name", "Course"],
                ["S01", "2025-Autumn", "Alice", "Math"],
                ["S01", "2026-Spring", "Alice", "Math"],
                ["S02", "2025-Autumn", "Bob", "Physics"],
            ],
        )
        _write_workbook(
            attendance_path,
            "Sheet1",
            [
                ["Student ID", "Term", "Attendance Rate", "Advisor"],
                ["S01", "2025-Autumn", 0.95, "Dr. Chen"],
                ["S01", "2026-Spring", 0.91, "Dr. Chen"],
                ["S02", "2025-Autumn", 0.88, "Dr. Singh"],
            ],
        )
        composite_join_sandbox = Sandbox(
            excel_paths=[str(enrollment_path), str(attendance_path)],
            output_preferences={},
            output_path=str(root / "composite_join_runtime_output.xlsx"),
        )
        composite_join_runtime = ExecutionRuntime(
            client=None,
            deployment="offline-test",
            sandbox=composite_join_sandbox,
            excel_context_execution="",
        )
        composite_join_exec = composite_join_runtime.run(
            understanding_output="",
            user_question="Merge the enrollment file with the attendance file using Student ID and Term as the shared keys.",
            max_turns=1,
        )
        _assert(composite_join_exec["success"], "Expected composite-key relational join fast-path to succeed.")
        _assert(Path(composite_join_exec["answer"]).exists(), "Expected composite-key relational join fast-path to save an output workbook.")
        composite_join_validation = ValidationRuntime(
            client=None,
            deployment="offline-test",
            excel_context_understanding="",
        )
        composite_join_validation_result = composite_join_validation.run(
            composite_join_exec,
            "Merge the enrollment file with the attendance file using Student ID and Term as the shared keys.",
            "",
        )
        _assert(
            composite_join_validation_result["validation_passed"],
            "Expected composite-key relational join fast-path output to pass validation.",
        )

        print("[skill regression] runtime: reference fill")
        fill_primary = root / "fill_primary.xlsx"
        fill_reference = root / "fill_reference.xlsx"
        _write_workbook(
            fill_primary,
            "Sheet1",
            [
                ["Student ID", "Name", "Program"],
                ["S01", "Alice", ""],
                ["S02", "Bob", "Math"],
            ],
        )
        _write_workbook(
            fill_reference,
            "Sheet1",
            [
                ["Student ID", "Program"],
                ["S01", "CS"],
                ["S02", "Math"],
            ],
        )
        fill_sandbox = Sandbox(
            excel_paths=[str(fill_primary), str(fill_reference)],
            output_preferences={},
            output_path=str(root / "fill_runtime_output.xlsx"),
        )
        fill_runtime = ExecutionRuntime(
            client=None,
            deployment="offline-test",
            sandbox=fill_sandbox,
            excel_context_execution="",
        )
        fill_exec = fill_runtime.run(
            understanding_output="",
            user_question="Fill the missing program values in the primary file using the reference file with the shared student ID.",
            max_turns=1,
        )
        _assert(fill_exec["success"], "Expected reference-fill fast-path to succeed.")
        fill_validation = ValidationRuntime(
            client=None,
            deployment="offline-test",
            excel_context_understanding="",
        )
        fill_validation_result = fill_validation.run(
            fill_exec,
            "Fill the missing program values in the primary file using the reference file with the shared student ID.",
            "",
        )
        _assert(fill_validation_result["validation_passed"], "Expected reference-fill fast-path output to pass validation.")

        print("[skill regression] runtime: missing-data scan")
        missing_scan_path = root / "missing_scan.xlsx"
        _write_workbook(
            missing_scan_path,
            "Sheet1",
            [
                ["Date", "Daily Spending (£)", "Notes"],
                ["2025-11-01", 106.11, "Lunch"],
                ["2025-11-02", "", "Missing amount"],
            ],
        )
        missing_sandbox = Sandbox(
            excel_paths=[str(missing_scan_path)],
            output_preferences={},
            output_path=str(root / "missing_scan_output.xlsx"),
        )
        missing_runtime = ExecutionRuntime(
            client=None,
            deployment="offline-test",
            sandbox=missing_sandbox,
            excel_context_execution="",
        )
        missing_exec = missing_runtime.run(
            understanding_output="",
            user_question="Identify where values are missing in the file and report the missing data.",
            max_turns=1,
        )
        _assert(missing_exec["success"], "Expected missing-data scan fast-path to succeed.")
        _assert("missing" in missing_exec["answer"].lower(), "Expected missing-data fast-path to return a missing-data answer.")

        print("[skill regression] runtime: identifier-format scan")
        room_scan_path = root / "room_scan.xlsx"
        _write_workbook(
            room_scan_path,
            "Sheet1",
            [
                ["Room", "Capacity"],
                ["C80", 30],
                ["C 80", 32],
            ],
        )
        room_sandbox = Sandbox(
            excel_paths=[str(room_scan_path)],
            output_preferences={},
            output_path=str(root / "room_scan_output.xlsx"),
        )
        room_runtime = ExecutionRuntime(
            client=None,
            deployment="offline-test",
            sandbox=room_sandbox,
            excel_context_execution="",
        )
        room_exec = room_runtime.run(
            understanding_output="",
            user_question="Check whether the room identifiers are inconsistent, for example C80 versus C 80.",
            max_turns=1,
        )
        _assert(room_exec["success"], "Expected room-format scan fast-path to succeed.")
        _assert("room" in room_exec["answer"].lower(), "Expected room-format fast-path to return a room-related answer.")

        print("[skill regression] runtime: dependency schedule")
        task_info = root / "task_info.xlsx"
        task_deps = root / "task_deps.xlsx"
        _write_workbook(
            task_info,
            "Sheet1",
            [
                ["Task ID", "Task Name", "Duration (hours)", "Priority"],
                ["T1", "Design", 2, "High"],
                ["T2", "Build", 3, "Medium"],
            ],
        )
        _write_workbook(
            task_deps,
            "Sheet1",
            [
                ["Task ID", "Depends on"],
                ["T1", ""],
                ["T2", "T1"],
            ],
        )
        schedule_sandbox = Sandbox(
            excel_paths=[str(task_info), str(task_deps)],
            output_preferences={},
            output_path=str(root / "schedule_runtime_output.xlsx"),
        )
        schedule_runtime = ExecutionRuntime(
            client=None,
            deployment="offline-test",
            sandbox=schedule_sandbox,
            excel_context_execution="",
        )
        schedule_exec = schedule_runtime.run(
            understanding_output="",
            user_question="Create a task schedule based on task durations and dependencies.",
            max_turns=1,
        )
        _assert(schedule_exec["success"], "Expected dependency schedule fast-path to succeed.")
        schedule_validation = ValidationRuntime(
            client=None,
            deployment="offline-test",
            excel_context_understanding="",
        )
        schedule_validation_result = schedule_validation.run(
            schedule_exec,
            "Create a task schedule based on task durations and dependencies.",
            "",
        )
        _assert(schedule_validation_result["validation_passed"], "Expected dependency schedule fast-path output to pass validation.")

        print("[skill regression] runtime: capacity-constrained allocation")
        allocation_entities = root / "allocation_entities.xlsx"
        allocation_resources = root / "allocation_resources.xlsx"
        _write_workbook(
            allocation_entities,
            "Sheet1",
            [
                ["Student ID", "Student Name"],
                ["S01", "Alice"],
                ["S02", "Bob"],
                ["S03", "Cara"],
                ["S04", "Dan"],
            ],
        )
        _write_workbook(
            allocation_resources,
            "Sheet1",
            [
                ["Room", "Capacity", "Session"],
                ["A101", 2, "Morning"],
                ["B202", 2, "Afternoon"],
            ],
        )
        allocation_sandbox = Sandbox(
            excel_paths=[str(allocation_entities), str(allocation_resources)],
            output_preferences={},
            output_path=str(root / "allocation_runtime_output.xlsx"),
        )
        allocation_runtime = ExecutionRuntime(
            client=None,
            deployment="offline-test",
            sandbox=allocation_sandbox,
            excel_context_execution="",
        )
        allocation_exec = allocation_runtime.run(
            understanding_output="",
            user_question="Allocate students to rooms based on room capacities and available seats.",
            max_turns=1,
        )
        _assert(allocation_exec["success"], "Expected capacity-constrained allocation fast-path to succeed.")
        allocation_validation = ValidationRuntime(
            client=None,
            deployment="offline-test",
            excel_context_understanding="",
        )
        allocation_validation_result = allocation_validation.run(
            allocation_exec,
            "Allocate students to rooms based on room capacities and available seats.",
            "",
        )
        _assert(
            allocation_validation_result["validation_passed"],
            "Expected capacity-constrained allocation fast-path output to pass validation.",
        )

        print("[skill regression] runtime: relational assignment schedule")
        assigned_students = root / "assigned_students.xlsx"
        professor_slots = root / "professor_slots.xlsx"
        _write_workbook(
            assigned_students,
            "Sheet1",
            [
                ["Student ID", "Student Name", "Assigned Professor"],
                ["S01", "Alice", "Prof. Chen"],
                ["S02", "Bob", "Prof. Chen"],
                ["S03", "Cara", "Prof. Singh"],
            ],
        )
        _write_workbook(
            professor_slots,
            "Sheet1",
            [
                ["Professor Name", "Day", "Time Slot", "Room"],
                ["Prof. Chen", "Monday", "10:00", "A101"],
                ["Prof. Singh", "Tuesday", "14:00", "B202"],
            ],
        )
        assignment_sandbox = Sandbox(
            excel_paths=[str(assigned_students), str(professor_slots)],
            output_preferences={},
            output_path=str(root / "assignment_runtime_output.xlsx"),
        )
        assignment_runtime = ExecutionRuntime(
            client=None,
            deployment="offline-test",
            sandbox=assignment_sandbox,
            excel_context_execution="",
        )
        assignment_exec = assignment_runtime.run(
            understanding_output="",
            user_question="Create a schedule showing each student with their assigned professor meeting slot and room.",
            max_turns=1,
        )
        _assert(assignment_exec["success"], "Expected relational assignment schedule fast-path to succeed.")
        assignment_validation = ValidationRuntime(
            client=None,
            deployment="offline-test",
            excel_context_understanding="",
        )
        assignment_validation_result = assignment_validation.run(
            assignment_exec,
            "Create a schedule showing each student with their assigned professor meeting slot and room.",
            "",
        )
        _assert(assignment_validation_result["validation_passed"], "Expected relational assignment schedule fast-path output to pass validation.")

        # Domain-specific macro helpers are now exposed as LLM helper hints rather than
        # automatic skill fast-paths, so this synthetic regression focuses on the
        # five routed skills and their registered helpers.

        print("[skill regression] runtime: regression")
        regression_path = root / "regression.xlsx"
        _write_workbook(
            regression_path,
            "Sheet1",
            [
                ["Student", "Study Hours", "Attendance", "Homework Score", "Final Score"],
                ["A", 5, 90, 80, 78],
                ["B", 7, 95, 88, 86],
                ["C", 3, 80, 72, 68],
                ["D", 9, 98, 92, 93],
            ],
        )
        regression_sandbox = Sandbox(
            excel_paths=[str(regression_path)],
            output_preferences={},
            output_path=str(root / "regression_runtime_output.xlsx"),
        )
        regression_runtime = ExecutionRuntime(
            client=None,
            deployment="offline-test",
            sandbox=regression_sandbox,
            excel_context_execution="",
        )
        regression_exec = regression_runtime.run(
            understanding_output="",
            user_question="Use Study Hours, Attendance, and Homework Score to fit a regression model predicting Final Score.",
            max_turns=1,
        )
        _assert(regression_exec["success"], "Expected regression fast-path to succeed.")
        regression_validation = ValidationRuntime(
            client=None,
            deployment="offline-test",
            excel_context_understanding="",
        )
        regression_validation_result = regression_validation.run(
            regression_exec,
            "Use Study Hours, Attendance, and Homework Score to fit a regression model predicting Final Score.",
            "",
        )
        _assert(regression_validation_result["validation_passed"], "Expected regression fast-path output to pass validation.")

        print("[skill regression] runtime: correlation")
        correlation_path = root / "correlation.xlsx"
        _write_workbook(
            correlation_path,
            "Sheet1",
            [
                ["species", "sepal_length", "sepal_width", "petal_length", "petal_width"],
                ["Iris-setosa", 5.1, 3.5, 1.4, 0.2],
                ["Iris-setosa", 4.9, 3.0, 1.4, 0.2],
                ["Iris-versicolor", 7.0, 3.2, 4.7, 1.4],
                ["Iris-versicolor", 6.4, 3.2, 4.5, 1.5],
            ],
        )
        correlation_sandbox = Sandbox(
            excel_paths=[str(correlation_path)],
            output_preferences={},
            output_path=str(root / "correlation_runtime_output.xlsx"),
        )
        correlation_runtime = ExecutionRuntime(
            client=None,
            deployment="offline-test",
            sandbox=correlation_sandbox,
            excel_context_execution="",
        )
        correlation_exec = correlation_runtime.run(
            understanding_output="",
            user_question="Build a correlation matrix for sepal length, sepal width, petal length, and petal width.",
            max_turns=1,
        )
        _assert(correlation_exec["success"], "Expected correlation fast-path to succeed.")
        correlation_validation = ValidationRuntime(
            client=None,
            deployment="offline-test",
            excel_context_understanding="",
        )
        correlation_validation_result = correlation_validation.run(
            correlation_exec,
            "Build a correlation matrix for sepal length, sepal width, petal length, and petal width.",
            "",
        )
        _assert(correlation_validation_result["validation_passed"], "Expected correlation fast-path output to pass validation.")

    print("Synthetic skill regression passed.")


if __name__ == "__main__":
    main()
