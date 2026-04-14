"""Schedule-specific code validation helpers."""

import re


class ScheduleValidationInspectorMixin:
    @classmethod
    def _collect_schedule_code_issues(cls, all_code: str) -> list[str]:
        issues: list[str] = []
        lower_code = (all_code or "").lower()
        uses_schedule_helper = "build_dependency_schedule(" in lower_code
        duration_hour_lines = [
            line.strip().lower()
            for line in (all_code or "").splitlines()
            if "duration (hours)" in line.lower()
        ]
        filename_role_guess = (
            re.search(r"for\s+\w+\s+in\s+all_files\s+if\s+.*['\"]tasks?['\"]\s+in\s+\w+", lower_code)
            or re.search(r"for\s+\w+\s+in\s+all_files\s+if\s+.*['\"]dependenc", lower_code)
            or re.search(r"(task_table|dependency_table)\s*=\s*tables\[\d+\]", lower_code)
            or cls._code_uses_literal_xlsx_name(all_code)
        )
        if "pd.merge(" in lower_code:
            issues.append(
                "Scheduling task incorrectly merges task and dependency tables; these should be processed separately."
            )
        if "same_schema" in lower_code or "schema mismatch between files" in lower_code:
            issues.append(
                "Scheduling task incorrectly assumes task and dependency tables must share the same schema."
            )
        if filename_role_guess:
            issues.append(
                "Scheduling task identifies task/dependency tables from filenames, literal input basenames, or list order instead of verified headers."
            )
        if not uses_schedule_helper:
            issues.append("Scheduling code does not use the runtime helper `build_dependency_schedule(...)`.")
        if uses_schedule_helper and "find_table_by_headers(" not in lower_code:
            issues.append(
                "Scheduling code uses the schedule helper but does not use `find_table_by_headers(...)` for role selection."
            )
        if uses_schedule_helper and "load_all_tables(" not in lower_code:
            issues.append(
                "Scheduling code uses the schedule helper but does not use `load_all_tables()` for linear multi-file loading."
            )
        if uses_schedule_helper:
            return issues
        if (
            re.search(r"for\s+\w+(?:\s*,\s*\w+)?\s+in\s+task_df\.iterrows\(\)", lower_code)
            and re.search(r"row\[['\"]depends on['\"]\]", lower_code)
        ):
            issues.append(
                "Scheduling code reads `Depends on` from the task table; root detection and edges must come from the dependency table."
            )
        if (
            re.search(r"for\s+\w+(?:\s*,\s*\w+)?\s+in\s+dep_df\.iterrows\(\)", lower_code)
            and any(
                marker in lower_code
                for marker in (
                    "row['task name']",
                    'row["task name"]',
                    "row['duration (hours)']",
                    'row["duration (hours)"]',
                    "row['priority']",
                    'row["priority"]',
                )
            )
        ):
            issues.append(
                "Scheduling code reads task metadata from the dependency table; keep table roles separate."
            )
        if (
            "if pd.isna(depends_on)" in lower_code
            and "schedule_order.append(task_id)" in lower_code
            and re.search(r"else:\s*.*task_id\s*=\s*row\[['\"]task id['\"]\]", lower_code, flags=re.DOTALL)
        ):
            issues.append(
                "Scheduling code uses `task_id` in the root-task branch before assigning it from the current dependency row."
            )
        if (
            "dropna(subset=['depends on']" in lower_code
            or 'dropna(subset=["depends on"]' in lower_code
            or "['depends on'].notna(" in lower_code
            or '["depends on"].notna(' in lower_code
        ):
            issues.append("Scheduling task drops blank dependencies even though they represent root tasks.")
        if re.search(r"adjacency\[\s*row\[['\"]task id['\"]\]\s*\]\.append\(\s*none\s*\)", lower_code):
            issues.append("Scheduling code appends `None` edges for root tasks instead of skipping edge creation.")
        if (
            "itertuples(" in lower_code
            and any(
                marker in lower_code
                for marker in (".task_id", ".task_name", ".depends_on", ".duration_hours", ".duration__hours")
            )
        ):
            issues.append(
                "Scheduling code uses tuple-attribute access for headers with spaces; use exact column names like `row['Task ID']`."
            )
        reversed_edge_patterns = (
            r"adjacency\[\s*(?:from_task|src_task|task_id|task|current_task)\s*\]\.append\(\s*(?:to_task|depends_on|dep_on|dependency|dep)\s*\)",
            r"in_degree\[\s*(?:to_task|depends_on|dep_on|dependency|dep)\s*\]\s*\+=\s*1",
        )
        if any(re.search(pattern, lower_code) for pattern in reversed_edge_patterns):
            issues.append("Scheduling code reverses dependency direction; edges must be `depends_on -> task_id`.")
        if (
            "duration (hours)" in lower_code
            and duration_hour_lines
            and not any(re.search(r"(?:\*\s*60|60\s*\*)", line) for line in duration_hour_lines)
        ):
            issues.append(
                "Scheduling code uses `Duration (hours)` but does not convert hours to minutes before time arithmetic."
            )
        if (
            "add_summary_row(" in lower_code
            and "total duration" in lower_code
            and re.search(r"len\s*\(\s*schedule_order\s*\)\s*\*", lower_code)
        ):
            issues.append(
                "Scheduling summary is derived from task count times a constant instead of real scheduled durations."
            )
        if "start time" not in lower_code or "end time" not in lower_code:
            issues.append("Scheduling code does not clearly build `Start Time` and `End Time` output columns.")
        topo_markers = ("in_degree", "adjacency", "queue", "deque(", "topological")
        if not any(marker in lower_code for marker in topo_markers):
            issues.append("Scheduling code does not show explicit dependency-order construction.")
        return issues
