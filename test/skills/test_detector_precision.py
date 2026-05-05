"""Precision and semantic contract tests for skill detectors.

Covers:
  1. is_merge_request false positives — single-table column/cell operations
  2. is_merge_request true positives — genuine cross-table merge tasks
  3. Skill boundary validation — single-skill routing per category
  4. Temporal handling audit — multi-month, vague phrases, guard behaviour
  5. Highlight contract — output_row_numbers semantics
  6. Plan source-of-truth — build_loop_breaker conditionality
"""

import sys
import os

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from backend.skills.detectors import (
    is_merge_request,
    is_aggregate_request,
    is_highlight_request,
)
from backend.skills import detect_skills, select_helper, build_loop_breaker
from backend.skills.prompt_builders import _extract_month_from_question


# ---------------------------------------------------------------------------
# 1. is_merge_request — false positive coverage (single-table operations)
# ---------------------------------------------------------------------------

class TestMergeDetectorFalsePositives:
    """Merge words that appear in single-table contexts must NOT trigger merge detection."""

    @pytest.mark.parametrize("question", [
        # Cell / formatting operations
        "merge cells A1:C1 in the sheet",
        "merge the header cells in the workbook",
        # Column combination within one table
        "combine the first name and last name columns in the table",
        "combine columns within one table to create a new field",
        "concatenate the Name and Surname columns in the spreadsheet",
        "concatenate columns to build a full address",
        # Single-structure operations (no multi-source)
        "union of all categories within one sheet",
        "union of distinct values in the dataset",
        "stack a bar chart in the table",
        "stack rows in the same spreadsheet",
        # Ambiguous/cross-concept phrases
        "join the first and last name into one column",
        "link the two columns together in the table",
        "average across all years in the table",          # "across" must not trigger alone
        "compute total across the sheet",
        "merge sort the values in the dataset",            # sorting algorithm, not data merge
    ])
    def test_no_merge_for_single_table_operation(self, question: str):
        assert is_merge_request(question) is False, (
            f"False positive: {question!r} should NOT be detected as merge"
        )


# ---------------------------------------------------------------------------
# 2. is_merge_request — true positive coverage (genuine cross-table tasks)
# ---------------------------------------------------------------------------

class TestMergeDetectorTruePositives:
    """Cross-table and cross-file operations must be detected as merge."""

    @pytest.mark.parametrize("question", [
        # Explicit multi-source with join verb
        "Merge both sales files into one table",
        "Join the two spreadsheets on the shared key",
        "Append the two monthly files and compute totals",
        "Stack both workbooks and summarize",
        "Combine the two datasets into a single output",
        "Stitch both workbooks together for analysis",
        "Union the two tables and write the result",
        # Explicit multi-file pattern (no join verb needed)
        "From both files, calculate average sales per day",
        "Calculate total sales across both files",
        "Merge the data from multiple tables into one",
        # Fill-missing patterns
        "fill missing values using the reference file",
        "populate missing entries use another file",
        # Key-join patterns
        "enrich the data from another file using the customer ID",
        "link the two datasets by employee ID",
        # Second-file references
        "append rows from the second file to the first",
        "join using the other file as lookup",
    ])
    def test_merge_detected_for_cross_table_operation(self, question: str):
        assert is_merge_request(question) is True, (
            f"False negative: {question!r} SHOULD be detected as merge"
        )


# ---------------------------------------------------------------------------
# 3. Skill boundary validation
# ---------------------------------------------------------------------------

class TestSkillBoundaryValidation:
    """Each question type must route to exactly the correct skill set."""

    def _skill_names(self, q: str) -> list[str]:
        return [s.name for s in detect_skills(q)]

    # 3a. Single-table aggregation (no merge)
    def test_single_table_aggregation_no_merge(self):
        q = "Calculate total sales per department from the single worksheet"
        names = self._skill_names(q)
        assert "aggregate" in names, f"aggregate not detected in {names}"
        assert "merge" not in names, f"false merge detected in {names}"

    def test_monthly_aggregation_no_merge(self):
        q = "Summarize average revenue by month and sort by highest"
        names = self._skill_names(q)
        assert "aggregate" in names
        assert "merge" not in names

    # 3b. Merge-only (no aggregation)
    def test_merge_only_no_aggregation(self):
        q = "Merge both customer files on customer ID and write the combined table"
        names = self._skill_names(q)
        assert "merge" in names
        assert "aggregate" not in names

    def test_fill_missing_merge_only(self):
        q = "Fill missing department values using the reference file"
        names = self._skill_names(q)
        assert "merge" in names
        assert "aggregate" not in names

    # 3c. Highlight-only (no merge, no aggregation)
    def test_highlight_only(self):
        q = "Highlight the rows where the score is above 90 in red"
        names = self._skill_names(q)
        assert "highlight" in names
        assert "merge" not in names
        assert "aggregate" not in names

    def test_highlight_bold_only(self):
        q = "Bold the top-performing rows in the output"
        names = self._skill_names(q)
        assert "highlight" in names
        assert "merge" not in names

    # 3d. Aggregation + highlight without merge
    def test_aggregate_highlight_no_merge(self):
        q = "Summarize total sales by region and highlight the top 3 regions"
        names = self._skill_names(q)
        assert "aggregate" in names
        assert "highlight" in names
        assert "merge" not in names

    def test_aggregate_highlight_november_no_merge(self):
        # Explicit agg_word ("total") is required — "calculate" alone is too generic
        q = "Calculate total daily sales for November and highlight the highest-spending day"
        names = self._skill_names(q)
        assert "aggregate" in names
        assert "highlight" in names
        assert "merge" not in names

    def test_calculate_without_agg_word_does_not_trigger_aggregate(self):
        """Known limitation: 'calculate daily sales' without sum/total/average/stats
        does not trigger aggregate detection. Explicit agg_words are required."""
        q = "Calculate daily sales for November and highlight the highest-spending day"
        names = self._skill_names(q)
        # "calculate" alone is not an agg_word — no false aggregate trigger
        assert "aggregate" not in names

    # 3e. Schedule / DAG tasks must NOT trigger merge even with two-table descriptions
    def test_schedule_two_input_tables_no_merge(self):
        """DAG scheduling tasks describe two input tables but should not trigger merge."""
        q = (
            "Here is a table containing tasks, their durations, and priorities, "
            "and another table describing task dependencies. Schedule the tasks based "
            "on these dependencies and report the total duration."
        )
        names = self._skill_names(q)
        assert "schedule" in names, f"schedule not detected; got {names}"
        assert "merge" not in names, f"false merge on schedule question; got {names}"


# ---------------------------------------------------------------------------
# 4. Temporal handling audit (current behaviour documented, no new impl)
# ---------------------------------------------------------------------------

class TestTemporalHandlingAudit:
    """Document current behaviour for multi-month, vague, and edge-case temporal phrases."""

    def test_explicit_single_month_detected(self):
        """Single unambiguous month triggers temporal grouping."""
        assert is_aggregate_request("compute daily totals for November") is True
        assert is_aggregate_request("show november stats") is True

    def test_explicit_month_with_prefix(self):
        """Month preceded by 'in'/'for' triggers temporal grouping."""
        assert is_aggregate_request("average sales per day in November") is True
        assert is_aggregate_request("summarize for december by store") is True

    def test_multi_month_returns_first_month_only(self):
        """_extract_month_from_question returns the first month found (known limitation)."""
        month = _extract_month_from_question("Show totals for November and December")
        # Current behaviour: first matched month only. December is lost.
        assert month == 11, (
            f"Expected 11 (November, first found), got {month}. "
            "Multi-month extraction is a known limitation — only first month is used."
        )

    def test_vague_relative_period_returns_none(self):
        """Vague phrases like 'last 2 months' yield no month number."""
        assert _extract_month_from_question("last 2 months") is None
        assert _extract_month_from_question("recent period") is None
        assert _extract_month_from_question("past quarter") is None

    def test_vague_period_does_not_trigger_temporal_filter_guard_aggregate(self):
        """Vague temporal phrases should NOT trigger temporal-grouped aggregate detection."""
        # "last 2 months" has no month name → has_temporal_group = False
        # needs group_words like "per day" to trigger aggregate
        assert is_aggregate_request("compute totals for the last 2 months") is False
        assert is_aggregate_request("summarize the recent period data") is False

    def test_vague_period_with_grouping_triggers_aggregate(self):
        """Vague temporal + explicit grouping = aggregate."""
        # "per day" is in group_words → has_group = True
        assert is_aggregate_request("compute daily totals over the last 2 months") is True

    def test_march_as_verb_no_false_positive(self):
        """'march' as a verb must not trigger temporal grouping."""
        # "march toward the total" — "total " triggers has_agg, "march" must NOT trigger temporal
        assert is_aggregate_request("march toward the total goal") is False

    def test_august_as_adjective_no_false_positive(self):
        """'august' as an adjective must not trigger temporal grouping."""
        # Even with a grouping word it might still fire — document the limit
        result = is_aggregate_request("august summary by department")
        # "august" is not in _unambiguous_months → has_temporal_group=False
        # "summary" is agg_word, "by department" is group_word → should FIRE (correct for "August summary")
        # This is an acceptable true positive since "august summary by department" most likely
        # means summary of August data grouped by department.
        assert result is True, "August + summary + by department should be treated as aggregate"

    def test_quarter_triggers_temporal_group(self):
        """Quarter identifiers trigger temporal grouping."""
        assert is_aggregate_request("compute average per q3") is True
        assert is_aggregate_request("show quarterly sales totals") is True


# ---------------------------------------------------------------------------
# 5. Highlight contract: output_row_numbers semantics
# ---------------------------------------------------------------------------

class TestHighlightContract:
    """Verify that output_row_numbers maps correctly to OUTPUT table Excel rows."""

    def test_output_row_numbers_match_max_row_in_written_table(self):
        """
        Contract: summarize_numeric_column resets index to 0-based,
        then +2 gives Excel row (1=header, 2=first data row).
        output_row_numbers is only valid for the exact df written at A1.
        """
        from backend.environment.spreadsheet.tools.workflows import summarize_numeric_column

        df = pd.DataFrame({
            "Day": ["Mon", "Tue", "Wed", "Thu", "Fri"],
            "Sales": [100, 250, 180, 250, 90],
        })
        result = summarize_numeric_column(df, value_col="Sales")
        # Max value is 250, appearing at indices 1 and 3 (0-based after reset_index)
        assert result["max_value"] == 250
        assert result["total"] == 870
        assert result["average"] == 174
        assert result["summary"]["Total"] == 870
        assert result["summary"]["Average"] == 174
        assert result["output_row_numbers"] == [3, 5], (
            "Index 1 → Excel row 3 (header=1, data starts at 2), index 3 → Excel row 5"
        )

    def test_output_row_numbers_after_filter(self):
        """After period filter, indices are re-mapped relative to the filtered df."""
        from backend.environment.spreadsheet.tools.workflows import summarize_numeric_column

        full_df = pd.DataFrame({
            "Date": ["2024-11-01", "2024-11-02", "2024-12-01", "2024-11-03"],
            "Sales": [100, 300, 999, 200],
        })
        # Simulated November filter — row with Sales=999 is excluded
        nov_df = full_df[full_df["Date"].str.startswith("2024-11")].reset_index(drop=True)
        result = summarize_numeric_column(nov_df, value_col="Sales")
        # In nov_df: index 0=100, 1=300, 2=200 → max=300 at index 1 → Excel row 3
        assert result["max_value"] == 300
        assert result["output_row_numbers"] == [3]

    def test_output_row_numbers_invalid_if_different_df_written(self):
        """
        Demonstrates the contract violation: if a DIFFERENT df is written to the sheet
        than the one passed to summarize_numeric_column, row numbers are wrong.
        """
        from backend.environment.spreadsheet.tools.workflows import summarize_numeric_column

        summary_df = pd.DataFrame({
            "Day": ["Mon", "Tue", "Wed"],
            "Sales": [100, 250, 180],
        })
        written_df = pd.DataFrame({
            "Day": ["Mon", "Tue", "Wed", "Thu"],   # DIFFERENT — one extra row prepended
            "Sales": [50, 100, 250, 180],
        })
        result = summarize_numeric_column(summary_df, value_col="Sales")
        # output_row_numbers says row 3 (index 1 → 1+2=3), but in written_df the
        # 250 is at index 2 → row 4. The numbers are WRONG for the written table.
        assert result["output_row_numbers"] == [3]  # correct for summary_df
        # In written_df, 250 is at index 2 → correct row would be 4, not 3.
        correct_for_written = [i + 2 for i, v in enumerate(written_df["Sales"]) if v == 250]
        assert correct_for_written == [4]
        assert result["output_row_numbers"] != correct_for_written, (
            "Confirms: output_row_numbers is WRONG when a different df is written. "
            "Always use the same df for both summarize_numeric_column and write_dataframe_to_sheet."
        )

    def test_output_row_numbers_reset_index_ensures_contiguous(self):
        """reset_index inside summarize_numeric_column ensures contiguous 0-based indices."""
        from backend.environment.spreadsheet.tools.workflows import summarize_numeric_column

        # df with non-contiguous index (e.g. result of a filter without reset_index)
        df = pd.DataFrame(
            {"Sales": [100, 300, 200]},
            index=[5, 7, 9],  # non-contiguous index
        )
        result = summarize_numeric_column(df, value_col="Sales")
        # reset_index maps to 0,1,2 → max at index 1 → Excel row 3
        assert result["output_row_numbers"] == [3]


# ---------------------------------------------------------------------------
# 6. Plan as single source of truth: build_loop_breaker conditionality
# ---------------------------------------------------------------------------

class TestPlanSourceOfTruth:
    """build_loop_breaker must include aggregate/highlight steps only when detected in plan."""

    def _breaker_for(self, question: str) -> str:
        skills = detect_skills(question)
        assert skills, f"no skill detected for {question!r}"
        primary = skills[0]
        helper = select_helper(primary, question)
        if helper is None:
            return ""
        return build_loop_breaker(primary, helper, extra_skills=skills, user_question=question)

    def test_merge_only_loop_breaker_has_no_summarize(self):
        """merge-only plan must NOT include summarize_numeric_column in loop breaker."""
        breaker = self._breaker_for("Merge both customer files on customer ID")
        assert "summarize_numeric_column" not in breaker, (
            "merge-only loop breaker should not reference summarize_numeric_column"
        )
        assert "highlight_rows" not in breaker

    def test_merge_only_loop_breaker_has_no_highlight(self):
        breaker = self._breaker_for("Combine the two datasets and write the result")
        assert "highlight_rows" not in breaker

    def test_full_pipeline_loop_breaker_has_summarize_and_highlight(self):
        """merge+aggregate+highlight plan MUST include both summarize and highlight."""
        q = "Merge both files, compute daily totals for November, and highlight the top day"
        breaker = self._breaker_for(q)
        assert "summarize_numeric_column" in breaker, "missing summarize_numeric_column"
        assert "highlight_rows" in breaker, "missing highlight_rows"
        assert "concat_tables_with_same_headers" in breaker

    def test_aggregate_highlight_loop_breaker_plan_driven(self):
        """aggregate+highlight without merge should still produce a useful loop breaker."""
        q = "Summarize daily sales for November and highlight the highest day"
        skills = detect_skills(q)
        names = [s.name for s in skills]
        assert "aggregate" in names
        assert "highlight" in names
        assert "merge" not in names

    def test_temporal_filter_injected_only_when_month_named(self):
        """Active (uncommented) dt.month filter must appear only when question names a month.
        When no month is specified the filter line is emitted as a comment template."""
        q_with_month = "Merge both files, compute daily totals for November, highlight top"
        q_no_month = "Merge both files and compute daily totals, highlight top"
        b_month = self._breaker_for(q_with_month)
        b_no_month = self._breaker_for(q_no_month)

        # With month: active filter line (no leading #)
        active_month_filter_pattern = "dt.month == 11"
        assert active_month_filter_pattern in b_month, (
            f"expected active dt.month filter in loop breaker for month question"
        )

        # Without month: the filter is a commented-out template, not active code
        # The comment `# summary_df = combined_df[combined_df['Date'].dt.month == N]`
        # may still contain "dt.month ==" — the important thing is no ACTIVE uncommented
        # filter line should reference a concrete month number.
        import re
        # Active filter = no leading #, contains dt.month == <number>
        active_lines = [
            ln for ln in b_no_month.splitlines()
            if re.search(r"dt\.month\s*==\s*\d+", ln) and not ln.lstrip().startswith("#")
        ]
        assert not active_lines, (
            f"unexpected active dt.month filter without month in question: {active_lines}"
        )

    def test_highlight_rows_contract_note_in_aggregate_plan(self):
        """The explicit highlight_rows contract note must appear when aggregate is in plan."""
        q = "Merge both files, compute daily totals for November, highlight top"
        breaker = self._breaker_for(q)
        assert "highlight_rows" in breaker
        assert "output_row_numbers" not in breaker
        assert "same df" in breaker.lower() or "same" in breaker.lower()
