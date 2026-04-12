"""Skill-specific execution preflight guard helpers."""

import re
from typing import TYPE_CHECKING, Optional

from ....skills import (
    detect_skills,
    get_helper_documented_result_keys,
    get_helper_preflight_guard_names,
    helper_result_variable_name,
    select_helper,
)
from ..analysis.schedule_helper_analysis import inspect_schedule_helper_sources

if TYPE_CHECKING:
    from ..runtime import ExecutionRuntime


class ExecutionSkillPreflightAdvisor:
    """Own skill-specific execution preflight rules."""

    def __init__(self, runtime: "ExecutionRuntime"):
        self.runtime = runtime

    def uses_literal_input_basenames(self, code_action: str) -> bool:
        code = code_action or ""
        lower = code.lower()
        for basename in self.runtime._available_workbook_basenames():
            escaped = re.escape((basename or "").lower())
            if not escaped:
                continue
            if re.search(rf"['\"]{escaped}['\"]", lower):
                return True
        return False

    @staticmethod
    def _helper_name(helper) -> Optional[str]:
        return getattr(helper, "name", None) if helper is not None else None

    def _selected_helper_name(self, user_question: str) -> Optional[str]:
        skills = detect_skills(user_question)
        skill = skills[0] if skills else None
        helper = select_helper(skill, user_question) if skill else None
        return self._helper_name(helper)

    @staticmethod
    def _documented_result_key_lines(helper_name: str) -> list[str]:
        result_var = helper_result_variable_name(helper_name)
        return [
            f"  `{result_var}['{key}']`"
            for key in get_helper_documented_result_keys(helper_name)
        ]

    @staticmethod
    def _extract_assigned_string_var(code_action: str, variable_name: str) -> Optional[str]:
        match = re.search(
            rf"^\s*{re.escape(variable_name)}\s*=\s*['\"]([^'\"]+)['\"]",
            code_action or "",
            flags=re.IGNORECASE | re.MULTILINE,
        )
        if not match:
            return None
        return match.group(1).strip()

    @staticmethod
    def _extract_assigned_string_list_var(code_action: str, variable_name: str) -> list[str]:
        match = re.search(
            rf"^\s*{re.escape(variable_name)}\s*=\s*\[([^\]]*)\]",
            code_action or "",
            flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
        )
        if not match:
            return []
        return [item.strip() for item in re.findall(r"['\"]([^'\"]+)['\"]", match.group(1))]

    def metadata_routed_preflight_check(self, code_action: str, user_question: str) -> Optional[str]:
        helper_name = self._selected_helper_name(user_question)
        if not helper_name:
            return None
        for guard_name in get_helper_preflight_guard_names(helper_name):
            guard = getattr(self, guard_name, None)
            if not callable(guard):
                continue
            issue = guard(code_action, user_question, helper_name=helper_name)
            if issue is not None:
                return issue
        return None

    def regression_helper_guard(
        self,
        code_action: str,
        user_question: str,
        helper_name: Optional[str] = None,
    ) -> Optional[str]:
        helper_name = helper_name or self._selected_helper_name(user_question)
        if helper_name != "fit_linear_regression_weights":
            return None
        code = code_action or ""
        lower = code.lower()
        if "fit_linear_regression_weights(" in lower:
            if (
                re.search(r"regression_result\s*\[\s*['\"]detail_data['\"]\s*\]\.columns", lower)
                or re.search(r"regression_result\s*\[\s*['\"]detail_data['\"]\s*\]\.values", lower)
            ):
                return (
                    "PREFLIGHT_REGRESSION: `regression_result['detail_data']` is already a 2D table payload, not a DataFrame.\n"
                    "- Either write it directly:\n"
                    "  `write_dataframe_to_sheet(regression_result['detail_data'], 'Output', 'A1')`\n"
                    "- Or use the DataFrame form:\n"
                    "  `write_dataframe_to_sheet(regression_result['output_df'], 'Output', 'A1')`"
                )
            if re.search(r"regression_result\s*\[\s*['\"]coef['\"]\s*\]", lower):
                documented_lines = self._documented_result_key_lines(helper_name)
                return (
                    "PREFLIGHT_REGRESSION: the regression helper does not return a `coef` key.\n"
                    "- Use these keys only:\n"
                    + "\n".join(documented_lines)
                    + "\n- Write `regression_result['output_df']` directly."
                )
            return None
        return (
            "PREFLIGHT_REGRESSION: use the runtime regression helper instead of hand-writing least-squares code.\n"
            "- Preferred linear pipeline:\n"
            "  `tables = load_all_tables()`\n"
            "  `df = tables[0]['df']`\n"
            "  `feature_cols = ['col1', 'col2', ...]`\n"
            "  `regression_result = fit_linear_regression_weights(df, target_col='...', feature_cols=feature_cols)`\n"
            "  `print('USED_FEATURES:', regression_result['used_features'])`\n"
            "  `write_dataframe_to_sheet(regression_result['output_df'], 'Output', 'A1')`\n"
            "- Do not import sklearn/statsmodels and do not hand-write `numpy.linalg.lstsq` in this task."
        )

    def merge_fill_helper_guard(self, code_action: str, user_question: str) -> Optional[str]:
        """Domain-specific helper guards.

        Most domain-specific helpers no longer have dedicated detectors.
        The generic preflight in generic_preflight.py handles skill-matched helpers.
        """
        return None

    def concat_merge_guard(
        self,
        code_action: str,
        user_question: str,
        helper_name: Optional[str] = None,
    ) -> Optional[str]:
        """Guard for cross-table stacking tasks: fires when concat helper should be used but isn't."""
        helper_name = helper_name or self._selected_helper_name(user_question)
        if helper_name != "concat_tables_with_same_headers":
            return None

        lower_q = (user_question or "").lower()
        has_merge = any(w in lower_q for w in ("merge", "combine", "concatenate", "concat"))
        if not has_merge:
            return None

        code = code_action or ""
        lower = code.lower()
        uses_concat_helper = "concat_tables_with_same_headers(" in lower
        builds_data_2d = "data_2d" in lower

        if uses_concat_helper and not builds_data_2d:
            return None

        # Detect month qualifier so temporal filter guidance can be appended.
        month_num: Optional[int] = None
        for name in self._MONTH_NAMES:
            if name in lower_q:
                from calendar import month_name as _mn
                # Convert name to number via index (1-based)
                full_names = [m.lower() for m in _mn]  # ['', 'january', ...]
                if name in full_names:
                    month_num = full_names.index(name)
                else:
                    _abbr_map = {
                        "jan": 1, "feb": 2, "mar": 3, "apr": 4,
                        "jun": 6, "jul": 7, "aug": 8,
                        "sep": 9, "oct": 10, "nov": 11, "dec": 12,
                    }
                    month_num = _abbr_map.get(name)
                break

        msg = (
            "PREFLIGHT_CONCAT_MERGE: cross-table stacking tasks should use concat_tables_with_same_headers.\n"
            "- Load and stack:\n"
            "  `tables = load_all_tables()`\n"
            "  `concat_result = concat_tables_with_same_headers(tables)`\n"
            "  `combined_df = concat_result['output_df']`\n"
            "  `print(combined_df.columns.tolist(), len(combined_df))`\n"
            "- Do not hand-build data_2d from headers + rows; write DataFrames directly.\n"
            "- Classify tables by verified headers, not filename or file order."
        )
        if month_num is not None:
            msg += (
                f"\n- The question specifies a period (month {month_num}): filter BEFORE summarizing:\n"
                "  `combined_df['Date'] = pd.to_datetime(combined_df['Date'], errors='coerce')`\n"
                f"  `summary_df = combined_df[combined_df['Date'].dt.month == {month_num}]`"
            )
        return msg

    # ------------------------------------------------------------------
    # Aggregate guard (independent of concat)
    # ------------------------------------------------------------------

    def aggregate_summary_guard(
        self,
        code_action: str,
        user_question: str,
        helper_name: Optional[str] = None,
    ) -> Optional[str]:
        """Guard for aggregate/summary tasks: fires when summarize_numeric_column should be used but isn't."""
        helper_name = helper_name or self._selected_helper_name(user_question)
        if helper_name != "concat_tables_with_same_headers":
            return None

        lower_q = (user_question or "").lower()
        has_aggregate = any(w in lower_q for w in (
            "average", "mean", "total", "sum", "count",
            "maximum", "minimum", "highest", "lowest", "median",
        ))
        if not has_aggregate:
            return None

        code = code_action or ""
        lower = code.lower()
        uses_summary_helper = "summarize_numeric_column(" in lower
        shadows_highlight_rows = re.search(r"^\s*highlight_rows\s*=", code, flags=re.MULTILINE) is not None

        undocumented_summary_key = None
        if uses_summary_helper:
            documented_summary_keys = {"summary", "output_row_numbers"}
            for key in re.findall(r"summary_result\s*\[\s*['\"]([^'\"]+)['\"]\s*\]", code):
                if key not in documented_summary_keys:
                    undocumented_summary_key = key
                    break

        if uses_summary_helper and not shadows_highlight_rows and undocumented_summary_key is None:
            return None

        return (
            "PREFLIGHT_AGGREGATE: use summarize_numeric_column for numeric summary tasks.\n"
            "  `summary_result = summarize_numeric_column(df, value_col='...')`\n"
            "  `add_summary_row('Output', len(df) + 2, summary_result['summary'])`\n"
            "- summary_result keys: 'summary' (dict), 'output_row_numbers' (list of 1-based ints).\n"
            + (
                f"- Does not return key '{undocumented_summary_key}'. "
                "Use 'summary' for totals/averages and 'output_row_numbers' for highlighting.\n"
                if undocumented_summary_key else ""
            )
            + "- Do not reassign the name `highlight_rows` to a variable."
        )

    # ------------------------------------------------------------------
    # Highlight guard (independent of merge/aggregate)
    # ------------------------------------------------------------------

    def highlight_guard(
        self,
        code_action: str,
        user_question: str,
        helper_name: Optional[str] = None,
    ) -> Optional[str]:
        """Guard for highlight tasks: fires when highlight_rows is called with wrong row numbers."""
        lower_q = (user_question or "").lower()
        needs_highlight = any(w in lower_q for w in (
            "highlight", "highlighted", "red", "color", "colour", "mark in red",
        ))
        if not needs_highlight:
            return None

        code = code_action or ""
        lower = code.lower()
        if "highlight_rows(" not in lower:
            return None

        # Detect manual enumerate-based row numbers (risky pattern)
        uses_manual_enumerate = bool(re.search(r"enumerate\s*\(", code))
        shadows_highlight_rows = re.search(r"^\s*highlight_rows\s*=", code, flags=re.MULTILINE) is not None
        uses_summary_row_numbers = "summary_result['output_row_numbers']" in code or 'summary_result["output_row_numbers"]' in code

        if not shadows_highlight_rows and not uses_manual_enumerate:
            return None

        return (
            "PREFLIGHT_HIGHLIGHT: row numbers passed to highlight_rows must be 1-based and header-offset.\n"
            "- Preferred: use `row_numbers = summary_result['output_row_numbers']` (already correct).\n"
            "- If computing manually: row = DataFrame position (0-based) + 2 (header row).\n"
            "  `row_numbers = [i + 2 for i, v in enumerate(df['col']) if v == max_val]`\n"
            "- The df passed to write_dataframe_to_sheet must have a reset (0-based) index.\n"
            "- Do not reassign the name `highlight_rows` to a variable in your code."
        )

    # ------------------------------------------------------------------
    # Temporal filter guard (aggregate + period-qualified questions)
    # ------------------------------------------------------------------

    _MONTH_NAMES = (
        "january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "november", "december",
        "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "oct", "nov", "dec",
    )

    def temporal_filter_guard(
        self,
        code_action: str,
        user_question: str,
        helper_name: Optional[str] = None,
    ) -> Optional[str]:
        """Fire when the question names a month/period but the code lacks a date filter.

        Targeting the merge+aggregate family: if the question says "in November"
        or "for Q3" but the generated code runs summarize_numeric_column over
        the unfiltered combined_df, stats and highlight row numbers will be wrong.
        """
        lower_q = (user_question or "").lower()
        has_month = any(m in lower_q for m in self._MONTH_NAMES)
        has_period = any(w in lower_q for w in (
            "in q1", "in q2", "in q3", "in q4", "quarter", "semester",
            "this year", "last year", "year to date",
        ))
        if not (has_month or has_period):
            return None

        code = code_action or ""
        lower = code.lower()

        # Only fire when aggregate helper is in use
        if "summarize_numeric_column(" not in lower:
            return None

        # Check whether any date-based filter is applied before summarize
        has_date_filter = any(pat in lower for pat in (
            ".dt.month", ".dt.year", ".dt.quarter",
            "month ==", "month==", "year ==", "year==",
            "quarter ==", "quarter==",
            ".str.contains",
            "pd.to_datetime",
        ))
        if has_date_filter:
            return None

        # Determine which month was mentioned for a concrete hint
        month_hint = ""
        for name in self._MONTH_NAMES:
            if name in lower_q:
                month_hint = name.capitalize()
                break

        period_label = f"'{month_hint}'" if month_hint else "the requested period"
        return (
            f"PREFLIGHT_TEMPORAL_FILTER: the question asks for stats restricted to {period_label} "
            "but the code passes the unfiltered DataFrame to summarize_numeric_column.\n"
            "- Convert the date column and filter BEFORE summarizing:\n"
            "  `combined_df['Date'] = pd.to_datetime(combined_df['Date'], errors='coerce')`\n"
            "  `summary_df = combined_df[combined_df['Date'].dt.month == <N>]  # e.g. 11 for November`\n"
            "- Pass `summary_df` (not `combined_df`) to both summarize_numeric_column AND write_dataframe_to_sheet.\n"
            "- `output_row_numbers` is only valid for the DataFrame that was written — using a different frame gives wrong highlight rows."
        )

    # keep old name as alias so existing caller sites continue to work
    def same_schema_merge_summary_guard(
        self,
        code_action: str,
        user_question: str,
        helper_name: Optional[str] = None,
    ) -> Optional[str]:
        c = self.concat_merge_guard(code_action, user_question, helper_name)
        a = self.aggregate_summary_guard(code_action, user_question, helper_name)
        t = self.temporal_filter_guard(code_action, user_question, helper_name)
        h = self.highlight_guard(code_action, user_question, helper_name)
        parts = [p for p in (c, a, t, h) if p]
        return "\n".join(parts) if parts else None

    def market_share_shipment_guard(
        self,
        code_action: str,
        user_question: str,
        helper_name: Optional[str] = None,
    ) -> Optional[str]:
        helper_name = helper_name or self._selected_helper_name(user_question)
        if helper_name != "build_market_share_shipment_report":
            return None

        code = code_action or ""
        lower = code.lower()
        assumes_exact_shipment_header = (
            "find_table_by_headers(" in lower
            and "shipment" in lower
        )
        guesses_table_order = bool(
            re.search(r"(share|shipment)_df\s*=\s*tables\[\d+\]\s*\[\s*['\"]df['\"]\s*\]", lower)
        )
        calls_direct_helper = "build_market_share_shipment_report(" in lower

        if not (assumes_exact_shipment_header or guesses_table_order or calls_direct_helper):
            return None

        return (
            "PREFLIGHT_MARKET_SHARE_SHIPMENT: do not identify the share/shipment tables from list order or from an assumed exact `Shipment` header.\n"
            "- The market-share table is the wider period table with many brand columns.\n"
            "- The shipment table is the narrower period table with `Time` plus a single numeric value column.\n"
            "- Preferred repair shape:\n"
            "  `tables = load_all_tables(require_primary_key=False, stop_at_note_row=False)`\n"
            "  `share_t = max(tables, key=lambda t: len(t['df'].columns))`\n"
            "  `shipment_t = min(tables, key=lambda t: len(t['df'].columns))`\n"
            "  `share_df = share_t['df'].copy()`\n"
            "  `shipment_df = shipment_t['df'].copy()`\n"
            "  `if 'Year' in share_df.columns: share_df = share_df.rename(columns={'Year': 'Time'})`\n"
            "  `if 'Year' in shipment_df.columns: shipment_df = shipment_df.rename(columns={'Year': 'Time'})`\n"
            "  `shipment_value_cols = [c for c in shipment_df.columns if c != 'Time']`\n"
            "  `shipment_value_col = shipment_value_cols[0]`\n"
            "  `shipment_df = shipment_df.rename(columns={shipment_value_col: 'Shipment'})`\n"
            "  `overlap_df = merge_on_shared_period(share_df, shipment_df[['Time', 'Shipment']], period_col='Time')`"
        )

    def regression_feature_guard(
        self,
        code_action: str,
        user_question: str,
        helper_name: Optional[str] = None,
    ) -> Optional[str]:
        helper_name = helper_name or self._selected_helper_name(user_question)
        if helper_name != "fit_linear_regression_weights":
            return None
        code = code_action or ""
        lower = code.lower()
        observed_headers = sorted(getattr(self.runtime, "_observed_header_set", lambda: set())())
        try:
            plan = self.runtime.question_inference.infer_runtime_plan(
                "statistical",
                "fit_linear_regression_weights",
                user_question,
                observed_headers,
            )
        except Exception:
            plan = None
        expected_target = getattr(plan, "target_col", None) if plan is not None else None
        expected_features = list(getattr(plan, "feature_cols", ()) or ())
        literal_target = (
            self._extract_assigned_string_var(code, "target_col")
            or self.runtime.question_inference.extract_single_string_kwarg(code, "target_col")
        )
        if expected_target and literal_target and literal_target.strip().lower() != expected_target.strip().lower():
            return (
                "PREFLIGHT_REGRESSION: target column conflicts with the runtime plan.\n"
                f"- Runtime plan target: {expected_target}\n"
                f"- Current code target: {literal_target}\n"
                "- Use the target column inferred from the current question and schema."
            )
        if "feature_cols" not in lower:
            return (
                "PREFLIGHT_REGRESSION: regression task must define explicit `feature_cols`.\n"
                "- Use all predictor columns (exclude target/ID/date-like columns).\n"
                "- Include binary categorical predictors (e.g., yes/no -> 1/0).\n"
                "- Print `USED_FEATURES` before fitting."
            )
        expected = expected_features or self.runtime.question_inference.expected_regression_predictors()
        if not expected:
            return None
        used = (
            self._extract_assigned_string_list_var(code, "feature_cols")
            or self.runtime.question_inference.extract_feature_cols_literal(code)
        )
        if not used:
            return (
                "PREFLIGHT_REGRESSION: could not parse explicit feature list.\n"
                "- Define `feature_cols = [\"col1\", \"col2\", ...]` as string literals.\n"
                "- Include all available predictors and print `USED_FEATURES`."
            )
        used_set = {u.strip().lower() for u in used}
        missing = [h for h in expected if h.strip().lower() not in used_set]
        if missing:
            missing_str = ", ".join(missing[:6])
            return (
                "PREFLIGHT_REGRESSION: feature coverage incomplete.\n"
                f"- Missing predictor(s): {missing_str}\n"
                "- Do not omit available predictors in regression tasks.\n"
                "- Add missing columns into `feature_cols` and encode binary categorical columns to 0/1."
            )
        if "used_features" not in lower:
            return (
                "PREFLIGHT_REGRESSION: add explicit feature audit print.\n"
                "- Add: print(\"USED_FEATURES:\", feature_cols)"
            )
        return None

    def scheduling_dependency_guard(
        self,
        code_action: str,
        user_question: str,
        helper_name: Optional[str] = None,
    ) -> Optional[str]:
        helper_name = helper_name or self._selected_helper_name(user_question)
        if helper_name != "build_dependency_schedule":
            return None
        runtime = self.runtime
        code = code_action or ""
        lower = code.lower()
        duration_hour_lines = [
            line.strip().lower()
            for line in code.splitlines()
            if "duration (hours)" in line.lower()
        ]
        filename_role_guess = (
            re.search(r"for\s+\w+\s+in\s+all_files\s+if\s+.*['\"]tasks?['\"]\s+in\s+\w+", lower)
            or re.search(r"for\s+\w+\s+in\s+all_files\s+if\s+.*['\"]dependenc", lower)
            or re.search(r"(task_table|dependency_table)\s*=\s*tables\[\d+\]", lower)
            or self.uses_literal_input_basenames(code)
        )
        uses_schedule_helper = "build_dependency_schedule(" in lower
        uses_table_loader = "load_all_tables(" in lower
        uses_header_selector = "find_table_by_headers(" in lower

        if "pd.merge(" in lower:
            return (
                "PREFLIGHT_SCHEDULING: do not merge task table with dependency table for DAG scheduling.\n"
                "- Keep tasks and dependencies as separate DataFrames.\n"
                "- Build `task_id_set` from task table first.\n"
                "- Parse dependency rows separately; blank/NaN predecessor means ROOT and should not be dropped."
            )

        schema_mismatch_markers = (
            "same_schema",
            "schema mismatch between files",
            "raise valueerror(\"schema mismatch",
            "raise valueerror('schema mismatch",
        )
        if any(marker in lower for marker in schema_mismatch_markers):
            return (
                "PREFLIGHT_SCHEDULING: dependency scheduling expects complementary tables, not matching schemas.\n"
                "- Identify task table by headers like `Task ID` + duration/name/priority columns.\n"
                "- Identify dependency table by headers `Task ID` + `Depends on`.\n"
                "- Keep them separate even when headers differ; do not raise schema mismatch."
            )
        if filename_role_guess:
            return (
                "PREFLIGHT_SCHEDULING: do not identify task/dependency tables from filenames, literal input basenames, or list positions.\n"
                "- Classify each table by verified headers only.\n"
                "- Task table must be chosen from headers like `Task ID` + `Task Name` + `Duration (hours)`.\n"
                "- Dependency table must be chosen from headers `Task ID` + `Depends on`."
            )
        if not uses_schedule_helper:
            return (
                "PREFLIGHT_SCHEDULING: use the runtime dependency-scheduling helper instead of hand-writing DAG logic.\n"
                "- Preferred linear pipeline:\n"
                "  `tables = load_all_tables()`\n"
                "  `task_table = find_table_by_headers(tables, required_headers=['Task ID'], preferred_headers=['Task Name', 'Duration (hours)', 'Priority'], forbidden_headers=['Depends on'])`\n"
                "  `dependency_table = find_table_by_headers(tables, required_headers=['Task ID', 'Depends on'])`\n"
                "  `schedule_result = build_dependency_schedule(task_table['df'], dependency_table['df'], start_time='08:00')`\n"
                "- Then write `schedule_result['detail_data']`, add `schedule_result['summary']`, print coverage, and save.\n"
                "- Do not hand-write adjacency/in_degree/queue in this task."
            )
        if not uses_table_loader:
            return (
                "PREFLIGHT_SCHEDULING: use `load_all_tables()` for dependency-scheduling tasks.\n"
                "- This keeps file loading linear and avoids repeated runtime I/O mistakes.\n"
                "- Then pick task/dependency tables with `find_table_by_headers(...)`."
            )
        if not uses_header_selector:
            return (
                "PREFLIGHT_SCHEDULING: use `find_table_by_headers(...)` to classify task and dependency tables.\n"
                "- Do not hand-write role selection logic from filenames, order, or partial header guesses."
            )
        helper_source_issue = inspect_schedule_helper_sources(code)
        if helper_source_issue == "missing_args":
            return (
                "PREFLIGHT_SCHEDULING: `build_dependency_schedule(...)` must receive both task and dependency DataFrames.\n"
                "- Use the exact helper call shape:\n"
                "  `schedule_result = build_dependency_schedule(task_table['df'], dependency_table['df'], start_time='08:00')`"
            )
        if helper_source_issue == "reconstructed_df":
            return (
                "PREFLIGHT_SCHEDULING: do not rebuild reduced DataFrames before calling `build_dependency_schedule(...)`.\n"
                "- Pass the original selected tables directly:\n"
                "  `schedule_result = build_dependency_schedule(task_table['df'], dependency_table['df'], start_time='08:00')`\n"
                "- Do NOT do `pd.DataFrame({...})` or column-subset reconstruction for the helper inputs.\n"
                "- The helper needs the original task metadata columns such as `Task Name`, `Duration (hours)`, and `Priority`."
            )
        if helper_source_issue == "non_selector_df":
            return (
                "PREFLIGHT_SCHEDULING: `build_dependency_schedule(...)` inputs must come from the selected table payloads.\n"
                "- Pass `task_table['df']` and `dependency_table['df']` directly, or simple aliases assigned from them.\n"
                "- Do NOT pass synthetic tables, partial row lists, or manually rebuilt DataFrames to the helper."
            )
        if uses_schedule_helper:
            return None
        if re.search(
            r"(task_df|task_file)\s*=\s*\[\s*\w+\s+for\s+\w+\s+in\s+tables\s+if\s+['\"]task id['\"]\s+in\s+\w+\[['\"]df['\"]\]\.columns\s*\]\[0\]\[['\"]df['\"]\]",
            lower,
        ):
            return (
                "PREFLIGHT_SCHEDULING: task-table selection is underspecified.\n"
                "- Do not choose the task table from `Task ID` alone because both tables contain that header.\n"
                "- Task table must be identified by `Task ID` plus task metadata like `Task Name`, `Duration (hours)`, or `Priority`.\n"
                "- Dependency table must be identified by `Task ID` plus `Depends on`."
            )
        if re.search(
            r"(task_table|task_df|task_file)\s*=\s*\[\s*\w+\s+for\s+\w+\s+in\s+tables\s+if\s+['\"]task id['\"]\s+in\s+\w+\[['\"]df['\"]\]\.columns\s*\]\[0\]\[['\"]df['\"]\]",
            lower,
        ):
            return (
                "PREFLIGHT_SCHEDULING: task-table selection is underspecified.\n"
                "- Do not choose the task table from `Task ID` alone because both tables contain that header.\n"
                "- Task table must be identified by `Task ID` plus task metadata like `Task Name`, `Duration (hours)`, or `Priority`.\n"
                "- Dependency table must be identified by `Task ID` plus `Depends on`."
            )
        if re.search(
            r"(dependency_df|dependencies)\s*=\s*\[\s*\w+\s+for\s+\w+\s+in\s+tables\s+if\s+['\"]depends on['\"]\s+in\s+\w+\[['\"]df['\"]\]\.columns\s*\]\[0\]\[['\"]df['\"]\]",
            lower,
        ):
            return (
                "PREFLIGHT_SCHEDULING: dependency-table selection should produce one DataFrame, not a list-derived mixed container.\n"
                "- Pick one dependency DataFrame by verified headers.\n"
                "- Keep task table and dependency table as separate DataFrames, not list-like stand-ins."
            )
        if (
            "dependencies = []" in lower
            and ".append(" in lower
            and (
                re.search(r"for\s+\w+\s+in\s+dependencies\s*:", lower)
                or re.search(r"\[\s*\w+\[['\"]task id['\"]\].*for\s+\w+\s+in\s+dependencies", lower)
                or re.search(r"dependencies\[['\"]depends on['\"]\]", lower)
            )
        ):
            return (
                "PREFLIGHT_SCHEDULING: dependency data structure is inconsistent.\n"
                "- Do not build `dependencies = []` and then treat it like dependency rows.\n"
                "- Keep a single dependency DataFrame such as `dependency_df`.\n"
                "- Iterate dependency rows with `for _, row in dependency_df.iterrows():`."
            )
        if re.search(
            r"if\s+not\s+(task_table|task_df|task_file)\b|if\s+(task_table|task_df|task_file)\s+and|if\s+not\s+.*dependencies",
            lower,
        ):
            return (
                "PREFLIGHT_LINEAR: do not use DataFrame truthiness in conditions.\n"
                "- Use `is None` for DataFrame presence checks.\n"
                "- Use `.empty` only when you really need emptiness.\n"
                "- Example: `if task_table is None or dependency_df is None:`"
            )

        task_dep_mixing_patterns = (
            (
                re.search(r"for\s+\w+(?:\s*,\s*\w+)?\s+in\s+task_df\.iterrows\(\)", lower)
                and re.search(r"row\[['\"]depends on['\"]\]", lower)
            ),
            (
                re.search(r"for\s+\w+(?:\s*,\s*\w+)?\s+in\s+dep_df\.iterrows\(\)", lower)
                and any(
                    marker in lower
                    for marker in (
                        "row['task name']",
                        'row["task name"]',
                        "row['duration (hours)']",
                        'row["duration (hours)"]',
                        "row['priority']",
                        'row["priority"]',
                    )
                )
            ),
        )
        if any(task_dep_mixing_patterns):
            return (
                "PREFLIGHT_SCHEDULING: task table and dependency table responsibilities are mixed.\n"
                "- The task table contains fields like `Task ID`, `Task Name`, `Duration (hours)`, `Priority`.\n"
                "- The dependency table contains `Task ID` and `Depends on`.\n"
                "- Determine ROOT tasks and edges from the dependency table only; do not read `Depends on` from `task_df`."
            )

        if re.search(r"['\"]08:00['\"]", code) and re.search(r"\+\s*f?['\"]", code):
            return (
                "PREFLIGHT_SCHEDULING: do not do time arithmetic with strings.\n"
                "- Keep time as integer minutes or datetime objects during computation.\n"
                "- Only format to `HH:MM` in the final output rows."
            )

        output_column_markers = ("start time", "end time")
        if not all(marker in lower for marker in output_column_markers):
            return (
                "PREFLIGHT_SCHEDULING: schedule output must include `Start Time` and `End Time` columns.\n"
                "- Build final Output columns as: `Task ID`, `Task Name`, `Priority`, `Start Time`, `End Time`.\n"
                "- Use exact starter shape:\n"
                "  `detail_data = [['Task ID', 'Task Name', 'Priority', 'Start Time', 'End Time']]`\n"
                "- Then append one row per scheduled task using formatted `HH:MM` text.\n"
                "- Do not write the raw task table directly."
            )

        if "start time (minutes)" in lower or "end time (minutes)" in lower:
            return (
                "PREFLIGHT_SCHEDULING: final output columns must be human-readable `Start Time` and `End Time`, not minute-count columns.\n"
                "- Keep minutes only as internal computation state.\n"
                "- Final rows must use exact headers: `Task ID`, `Task Name`, `Priority`, `Start Time`, `End Time`.\n"
                "- Format output values as `HH:MM` strings."
            )

        drops_root_markers = (
            "dropna(subset=['depends on']",
            'dropna(subset=["depends on"]',
            "['depends on'].notna(",
            '["depends on"].notna(',
        )
        if any(m in lower for m in drops_root_markers):
            return (
                "PREFLIGHT_SCHEDULING: blank `Depends on` rows are ROOT tasks and must not be dropped.\n"
                "- Remove the `dropna/notna` filter on dependency predecessor.\n"
                "- Use blank/NaN predecessor as 'no incoming edge'."
            )
        if (
            "depends on" in lower
            and "pd.notnull(" in lower
            and "pd.isna(" not in lower
            and ".strip() == ''" not in lower
            and ".strip()==''" not in lower
        ):
            return (
                "PREFLIGHT_SCHEDULING: root-task handling is incomplete.\n"
                "- For dependency rows use: `if pd.isna(dep) or str(dep).strip() == '': continue`.\n"
                "- Only create adjacency/in_degree edges for real predecessor task IDs."
            )
        if (
            "if pd.isna(depends_on)" in lower
            and "schedule_order.append(task_id)" in lower
            and re.search(r"else:\s*.*task_id\s*=\s*row\[['\"]task id['\"]\]", lower, flags=re.DOTALL)
        ):
            return (
                "PREFLIGHT_SCHEDULING: root-task branch is using `task_id` before reading it from the current dependency row.\n"
                "- In the dependency loop, assign `task_id = row['Task ID']` before any root/edge logic.\n"
                "- Then use blank/NaN `Depends on` only to skip edge creation, not to append a stale task ID.\n"
                "- Root tasks should come from zero in-degree after graph construction."
            )
        if (
            re.search(r"adjacency\[\s*(dependency|depends_on|dep)\s*\]", lower)
            and "pd.isna(" not in lower
            and ".strip() == ''" not in lower
            and ".strip()==''" not in lower
        ):
            return (
                "PREFLIGHT_SCHEDULING: adjacency is being built from a predecessor without a blank/NaN guard.\n"
                "- Guard first: `if pd.isna(dep) or str(dep).strip() == '': continue`.\n"
                "- Then append `adjacency[dep].append(task_id)` and increment `in_degree[task_id]`."
            )
        if re.search(r"adjacency\[\s*row\[['\"]task id['\"]\]\s*\]\.append\(\s*none\s*\)", lower):
            return (
                "PREFLIGHT_SCHEDULING: do not append `None` edges for root tasks.\n"
                "- Blank/NaN `Depends on` means no incoming edge, so skip edge creation entirely.\n"
                "- Keep root tasks as nodes with zero in-degree; do not store placeholder neighbors."
            )
        if (
            re.search(r"root_tasks\s*=\s*\[\s*\w+\[['\"]task id['\"]\]", lower)
            and re.search(r"for\s+\w+\s+in\s+dependencies", lower)
        ):
            return (
                "PREFLIGHT_SCHEDULING: root-task extraction is iterating the wrong container level.\n"
                "- Do not iterate a list of dependency DataFrames as if each item were a row.\n"
                "- Iterate the dependency DataFrame rows only: `for _, row in dependency_df.iterrows():`.\n"
                "- Root tasks come from rows where `Depends on` is blank/NaN."
            )
        reversed_edge_patterns = (
            r"adjacency\[\s*(?:from_task|src_task|task_id|task|current_task)\s*\]\.append\(\s*(?:to_task|depends_on|dep_on|dependency|dep)\s*\)",
            r"in_degree\[\s*(?:to_task|depends_on|dep_on|dependency|dep)\s*\]\s*\+=\s*1",
        )
        if any(re.search(pattern, lower) for pattern in reversed_edge_patterns):
            return (
                "PREFLIGHT_SCHEDULING: dependency edge direction is reversed.\n"
                "- In this task, `Task ID` is the current task and `Depends on` is its predecessor.\n"
                "- Correct edge direction is `depends_on -> task_id`.\n"
                "- Use `adjacency[depends_on].append(task_id)` and `in_degree[task_id] += 1`."
            )
        if (
            re.search(r"astype\s*\(\s*\{[^}]*['\"]task id['\"]\s*:\s*int", lower)
            or re.search(r"int\s*\(\s*row\[['\"]task id['\"]\]\s*\)", lower)
            or re.search(r"int\s*\(\s*(?:dep|depends_on|dep_task_id|task_id)\s*\)", lower)
            or re.search(r"\[\s*set\(\)\s*for\s+_\s+in\s+range", lower)
            or re.search(r"(adjacency|in_degree)\s*\[\s*[a-z_]+\s*-\s*1\s*\]", lower)
        ):
            return (
                "PREFLIGHT_SCHEDULING: Task IDs must stay as original string labels, not numeric indices.\n"
                "- Do NOT cast `Task ID` or `Depends on` values to `int`.\n"
                "- Values like `T1`, `T2`, ... are graph node labels and must remain strings.\n"
                "- Use dictionary-based graph state keyed by exact task IDs:\n"
                "  `task_id_set = set(task_df['Task ID'])`\n"
                "  `adjacency = {task_id: [] for task_id in task_id_set}`\n"
                "  `in_degree = {task_id: 0 for task_id in task_id_set}`"
            )

        topo_markers = ("in_degree", "adjacency", "queue", "deque(", "topological")
        if not any(m in lower for m in topo_markers):
            return (
                "PREFLIGHT_SCHEDULING: dependency scheduling must explicitly build an execution order from dependencies.\n"
                "- Use a DAG ordering method such as Kahn algorithm with adjacency/in_degree/queue.\n"
                "- Do not write the task table directly without dependency processing."
            )
        if re.search(r"task_id_set\s*=\s*.*(?:tolist\(\)|list\()", lower):
            return (
                "PREFLIGHT_SCHEDULING: `task_id_set` must be a set, not a list.\n"
                "- Use: `task_id_set = set(task_df['Task ID'])`\n"
                "- Compare coverage with another set such as `scheduled_task_ids = set(schedule_order)`."
            )
        if (
            ("start time" in lower and "end time" in lower)
            and re.search(r"\b(task_df|df_tasks|tasks_df)\.values\.tolist\(\)", code)
        ):
            return (
                "PREFLIGHT_SCHEDULING: final schedule rows cannot be the raw task table values.\n"
                "- Build output rows from scheduled order after computing Start/End Time.\n"
                "- Do not append `task_df.values.tolist()` into the final schedule table."
            )

        if (
            "itertuples(" in lower
            and any(
                marker in lower
                for marker in (
                    ".task_id",
                    ".task_name",
                    ".depends_on",
                    ".duration_hours",
                    ".duration__hours",
                )
            )
        ):
            return (
                "PREFLIGHT_SCHEDULING: spaced headers must be accessed by exact column name, not tuple attributes.\n"
                "- Do NOT use `itertuples()` with `.Task_ID` / `.Depends_on` style access.\n"
                "- Use `iterrows()` and exact header access such as `row['Task ID']` and `row['Depends on']`."
            )

        if (
            "duration (hours)" in lower
            and duration_hour_lines
            and not any(re.search(r"(?:\*\s*60|60\s*\*)", line) for line in duration_hour_lines)
        ):
            return (
                "PREFLIGHT_SCHEDULING: `Duration (hours)` must be converted to minutes before scheduling.\n"
                "- Keep computation in integer minutes from `8 * 60`.\n"
                "- Example: `duration_minutes = int(round(float(task_row['Duration (hours)']) * 60))`.\n"
                "- Do not add raw hour values directly to `current_time_minutes`."
            )

        if (
            "duration (hours)" in lower
            and duration_hour_lines
            and any(re.search(r"(?:\*\s*60|60\s*\*)", line) for line in duration_hour_lines)
            and "pd.to_numeric(" not in lower
            and ".astype(float)" not in lower
            and "float(" not in lower
        ):
            return (
                "PREFLIGHT_SCHEDULING: convert duration values to numeric before multiplying by 60.\n"
                "- Use `pd.to_numeric(tasks_df['Duration (hours)'], errors='coerce').astype(float)` or `float(value)`.\n"
                "- Do not do string duration * 60."
            )
        if re.search(
            r"for\s+\w+\s+in\s+\w+\.iterrows\(\).*?\w+\[['\"]duration \(hours\)['\"]\]",
            lower,
            flags=re.DOTALL,
        ):
            return (
                "PREFLIGHT_SCHEDULING: `iterrows()` returns `(index, row)` pairs, not row objects directly.\n"
                "- Use `for _, row in task_df.iterrows():` before `row['Duration (hours)']` access.\n"
                "- Or compute total duration from the numeric column directly with `pd.to_numeric(...).sum()`."
            )

        if re.search(
            r"float\s*\(\s*task_df\s*\[\s*task_df\s*\[\s*['\"]task id['\"]\s*\]\s*==.*?\]\s*\[\s*['\"]duration \(hours\)['\"]\s*\]\s*\)",
            lower,
            flags=re.DOTALL,
        ):
            return (
                "PREFLIGHT_SCHEDULING: do not call `float(...)` on a filtered pandas Series.\n"
                "- Select one task row first, then read scalar fields from that row.\n"
                "- Use:\n"
                "  `task_row = task_df.loc[task_df['Task ID'] == task_id].iloc[0]`\n"
                "  `duration_minutes = int(round(float(task_row['Duration (hours)']) * 60))`"
            )

        if (
            "in_degree = {}" in lower
            and "adjacency = {}" in lower
            and "dependency_dict.items()" in lower
        ):
            return (
                "PREFLIGHT_SCHEDULING: adjacency/in_degree must be initialized for every task before processing dependencies.\n"
                "- Start from `task_id_set` or `task_df['Task ID']`, not only from dependency-bearing rows.\n"
                "- Use shapes like `adjacency = {task_id: [] for task_id in task_id_set}` and `in_degree = {task_id: 0 for task_id in task_id_set}`.\n"
                "- Otherwise ROOT tasks are missing and queue construction will fail."
            )

        if (
            "schedule.append((" in lower
            and re.search(r"schedule\[\w+\]\s*=", lower)
        ):
            return (
                "PREFLIGHT_SCHEDULING: keep schedule order and final output rows as separate data structures.\n"
                "- `schedule_order` should stay a flat list of task IDs only.\n"
                "- `detail_data` should hold final 5-column output rows.\n"
                "- Do not append one tuple shape to `schedule` and then overwrite it with another tuple shape."
            )

        if re.search(r"(task|entry)\[\s*1\s*\]\s*\[['\"]task id['\"]\]", lower):
            return (
                "PREFLIGHT_SCHEDULING: schedule coverage checks must compare task-ID sets directly, not by indexing mixed tuple payloads.\n"
                "- Use `schedule_order` as a list of task IDs.\n"
                "- Then compare `set(schedule_order)` with `task_id_set`."
            )

        if "schedule_df.append(" in lower:
            return (
                "PREFLIGHT_SCHEDULING: do not build the final schedule with DataFrame.append() inside the loop.\n"
                "- Accumulate `detail_data` as a Python list of rows.\n"
                "- Convert once at the end or pass the row list directly to `write_dataframe_to_sheet(...)`."
            )

        if (
            "total duration" in lower
            and "schedule_df.values" in lower
        ):
            return (
                "PREFLIGHT_SCHEDULING: total duration summary must come from a numeric accumulator, not from stringified schedule rows.\n"
                "- Keep `total_duration_minutes` or `total_duration_hours` while building the schedule.\n"
                "- Write summary from that numeric variable."
            )

        if (
            "add_summary_row(" in lower
            and "total duration" in lower
            and re.search(r"total_duration\s*/\s*60", lower)
            and re.search(r"total_duration\s*\+=", lower)
            and any("* 60" not in line and "60 *" not in line for line in duration_hour_lines)
        ):
            return (
                "PREFLIGHT_SCHEDULING: summary duration units are inconsistent.\n"
                "- If `total_duration` accumulates hours, write hours directly.\n"
                "- If `total_duration` accumulates minutes, divide by 60 exactly once when reporting hours.\n"
                "- Do not divide hour totals by 60 a second time."
            )
        if (
            "add_summary_row(" in lower
            and "total duration" in lower
            and re.search(r"len\s*\(\s*schedule_order\s*\)\s*\*", lower)
        ):
            return (
                "PREFLIGHT_SCHEDULING: total-duration summary cannot be derived from task count times a constant.\n"
                "- Accumulate duration from real task rows while building the schedule.\n"
                "- Use a numeric accumulator such as `total_duration_minutes += duration_minutes`.\n"
                "- Report hours once with `total_duration_minutes / 60`."
            )
        if (
            "total_duration_minutes" in lower
            and "iterrows()" in lower
            and "duration (hours)" in lower
            and "sum(" in lower
        ):
            return (
                "PREFLIGHT_SCHEDULING: total-duration summary should not use `sum(... for row in df.iterrows())`.\n"
                "- `iterrows()` yields `(index, row)` tuples.\n"
                "- Use either `for _, row in task_df.iterrows()` or, better, `pd.to_numeric(task_df['Duration (hours)'], errors='coerce').sum()`.\n"
                "- Then convert hours to minutes once with `* 60` if needed."
            )
        if (
            "fillna({})" in lower
            and "duration (hours)" in lower
            and "sum(" in lower
        ):
            return (
                "PREFLIGHT_SCHEDULING: total-duration summary is iterating the DataFrame object, not task rows.\n"
                "- Do not use `for task in task_table.fillna({})` for row-wise duration math.\n"
                "- Prefer column-level aggregation:\n"
                "  `total_duration_hours = pd.to_numeric(task_table['Duration (hours)'], errors='coerce').sum()`\n"
                "- Then report that numeric total directly in hours."
            )
        if "write_data = [detail_data]" in lower or re.search(r"write_dataframe_to_sheet\s*\(\s*\[\s*detail_data\s*\]", lower):
            return (
                "PREFLIGHT_LINEAR: do not wrap the 2D output table in an extra list.\n"
                "- `detail_data` is already the full table payload.\n"
                "- Call `write_dataframe_to_sheet(detail_data, \"Output\", \"A1\")` directly."
            )

        return None

    def relational_assignment_guard(
        self,
        code_action: str,
        user_question: str,
        helper_name: Optional[str] = None,
    ) -> Optional[str]:
        helper_name = helper_name or self._selected_helper_name(user_question)
        if helper_name != "build_relational_assignment_schedule_report":
            return None

        code = code_action or ""
        lower = code.lower()
        uses_helper = "build_relational_assignment_schedule_report(" in lower
        uses_header_selector = "find_table_by_headers(" in lower
        filename_or_order_guess = (
            re.search(r"tables\s*\[\s*\d+\s*\]\s*\[\s*['\"]df['\"]\s*\]", lower)
            or re.search(r"tables\s*\[\s*['\"][^'\"]+\.(csv|xlsx?)['\"]\s*\]", lower)
            or self.uses_literal_input_basenames(code)
        )

        if filename_or_order_guess:
            return (
                "PREFLIGHT_ASSIGNMENT_SCHEDULE: do not identify assignment/schedule tables from filenames, literal basenames, file order, or list positions.\n"
                "- Classify tables by verified headers only.\n"
                "- Preferred pipeline:\n"
                "  `tables = load_all_tables()`\n"
                "  `assignment_t = find_table_by_headers(tables, required_headers=['Assigned Tutor'], preferred_headers=['Student Name', 'Name', 'Student'])`\n"
                "  `schedule_t = find_table_by_headers(tables, required_headers=['Tutor Name', 'Time Slot', 'Room'])`\n"
                "  `output_df = build_grouped_assignment_join(assignment_t['df'], 'Assigned Tutor', 'Name', schedule_t['df'], 'Tutor Name', ['Time Slot', 'Room'])`\n"
                "- Or call `build_relational_assignment_schedule_report()` directly when the matched helper fits the observed headers."
            )

        if not uses_helper and not uses_header_selector:
            return (
                "PREFLIGHT_ASSIGNMENT_SCHEDULE: relational assignment tasks must ground table roles by headers before joining.\n"
                "- Load all tables, then use `find_table_by_headers(...)` to select the assignment and schedule tables.\n"
                "- Assignment table: `Assigned Tutor` plus entity headers like `Student Name`, `Name`, or `Student`.\n"
                "- Schedule table: `Tutor Name` + `Time Slot` + `Room`.\n"
                "- After that, either compose with `build_grouped_assignment_join(...)` or call `build_relational_assignment_schedule_report()` directly."
            )

        if (
            uses_header_selector
            and not uses_helper
            and "build_grouped_assignment_join(" not in lower
            and "pd.merge(" in lower
        ):
            return (
                "PREFLIGHT_ASSIGNMENT_SCHEDULE: after header-grounded table selection, use the shared grouped-assignment helper instead of a hand-written bare merge.\n"
                "- Preferred composition:\n"
                "  `output_df = build_grouped_assignment_join(assignment_t['df'], 'Assigned Tutor', 'Name', schedule_t['df'], 'Tutor Name', ['Time Slot', 'Room'])`\n"
                "- This keeps entity-column resolution grounded in the observed headers and avoids hard-coded `Student Name` assumptions.\n"
                "- If the matched helper fits the observed headers exactly, `build_relational_assignment_schedule_report()` is also allowed."
            )

        return None

    def region_growth_helper_guard(
        self,
        code_action: str,
        user_question: str,
        helper_name: Optional[str] = None,
    ) -> Optional[str]:
        helper_name = helper_name or self._selected_helper_name(user_question)
        if helper_name != "build_region_growth_analysis":
            return None

        code = code_action or ""
        lower = code.lower()
        uses_helper = "build_region_growth_analysis(" in lower
        if not uses_helper:
            return (
                "PREFLIGHT_REGION_GROWTH: use `build_region_growth_analysis()` for this region-growth chart task instead of hand-parsing the multi-row header.\n"
                "- Preferred workflow:\n"
                "  `region_growth_result = build_region_growth_analysis(sheet_name='Data', start_year=2021, end_year=2024)`\n"
                "  `create_output_sheet('Output')`\n"
                "  `write_dataframe_to_sheet(region_growth_result['output_df'], 'Output', 'A1')`\n"
                "  `summary_row = len(region_growth_result['output_df']) + 2`\n"
                "  `add_summary_row('Output', summary_row, region_growth_result['summary'])`\n"
                "  `chart_df = region_growth_result['chart_df']`\n"
                "  `for region in region_growth_result['region_columns']: plt.plot(chart_df['Year'], chart_df[region], label=region)`\n"
                "  `save_plot_to_excel('Output', 'F2')`"
            )

        if re.search(r"build_region_growth_analysis\(\s*(tables\[|df\b|pd\.)", lower):
            return (
                "PREFLIGHT_REGION_GROWTH: `build_region_growth_analysis()` expects runtime workbook context, not a DataFrame.\n"
                "- Call it as `build_region_growth_analysis()` or with optional named args like `sheet_name='Data'`.\n"
                "- Do not pass `tables[...]`, `df`, or other DataFrame objects into the helper."
            )
        return None
