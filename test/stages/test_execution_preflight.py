import os
import re
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from backend.stages.execution.skill.preflight import ExecutionSkillPreflightAdvisor
from backend.stages.execution.skill.generic_preflight import ExecutionGenericPreflightAdvisor


class _InferenceStub:
    @staticmethod
    def expected_regression_predictors():
        return ["price", "ad spend"]

    @staticmethod
    def extract_feature_cols_literal(_code):
        return []

    @staticmethod
    def extract_single_string_kwarg(code, kwarg):
        match = re.search(rf"{kwarg}\s*=\s*['\"]([^'\"]+)['\"]", code)
        return match.group(1) if match else None

    @staticmethod
    def infer_runtime_plan(_skill_name, _helper_name, _user_question, _observed_headers):
        return SimpleNamespace(
            target_col="sales",
            feature_cols=("price", "ad spend"),
        )


class _RuntimeStub:
    def __init__(self) -> None:
        self.question_inference = _InferenceStub()
        self._is_offline_strict = True

    @staticmethod
    def _available_workbook_basenames():
        return []

    @staticmethod
    def _observed_header_set():
        return {"Date", "Category", "Daily Spending (£)", "Notes"}


def test_metadata_routed_preflight_uses_selected_helper_guards(monkeypatch):
    advisor = ExecutionSkillPreflightAdvisor(_RuntimeStub())

    monkeypatch.setattr(
        "backend.stages.execution.skill.preflight.detect_skills",
        lambda _question: [SimpleNamespace(name="regression")],
    )
    monkeypatch.setattr(
        "backend.stages.execution.skill.preflight.select_helper",
        lambda _skill, _question: SimpleNamespace(name="fit_linear_regression_weights"),
    )

    issue = advisor.metadata_routed_preflight_check(
        code_action=(
            "tables = load_all_tables()\n"
            "df = tables[0]['df']\n"
            "regression_result = fit_linear_regression_weights(df, target_col='sales')\n"
        ),
        user_question="Fit a regression model for sales.",
    )

    assert issue is not None
    assert issue.startswith(
        "PREFLIGHT_REGRESSION: regression task must define explicit `feature_cols`."
    )


def test_regression_preflight_coef_guidance_uses_documented_result_keys(monkeypatch):
    advisor = ExecutionSkillPreflightAdvisor(_RuntimeStub())

    monkeypatch.setattr(
        "backend.stages.execution.skill.preflight.detect_skills",
        lambda _question: [SimpleNamespace(name="regression")],
    )
    monkeypatch.setattr(
        "backend.stages.execution.skill.preflight.select_helper",
        lambda _skill, _question: SimpleNamespace(name="fit_linear_regression_weights"),
    )

    issue = advisor.metadata_routed_preflight_check(
        code_action=(
            "tables = load_all_tables()\n"
            "df = tables[0]['df']\n"
            "regression_result = fit_linear_regression_weights(df, target_col='sales', feature_cols=['price'])\n"
            "print(regression_result['coef'])\n"
        ),
        user_question="Fit a regression model for sales.",
    )

    assert issue is not None
    assert "PREFLIGHT_REGRESSION: the regression helper does not return a `coef` key." in issue
    assert "regression_result['used_features']" in issue
    assert "regression_result['output_df']" in issue
    assert "regression_result['detail_data']" in issue
    assert "regression_result['coefficients_df']" in issue


def test_regression_preflight_blocks_target_col_that_conflicts_with_runtime_plan(monkeypatch):
    advisor = ExecutionSkillPreflightAdvisor(_RuntimeStub())

    monkeypatch.setattr(
        "backend.stages.execution.skill.preflight.detect_skills",
        lambda _question: [SimpleNamespace(name="regression")],
    )
    monkeypatch.setattr(
        "backend.stages.execution.skill.preflight.select_helper",
        lambda _skill, _question: SimpleNamespace(name="fit_linear_regression_weights"),
    )

    issue = advisor.metadata_routed_preflight_check(
        code_action=(
            "tables = load_all_tables()\n"
            "df = tables[0]['df']\n"
            "feature_cols = ['price', 'ad spend']\n"
            "regression_result = fit_linear_regression_weights(df, target_col='rain', feature_cols=feature_cols)\n"
            "print('USED_FEATURES:', feature_cols)\n"
        ),
        user_question="Fit a regression model for sales from price and ad spend.",
    )

    assert issue is not None
    assert "PREFLIGHT_REGRESSION: target column conflicts with the runtime plan." in issue
    assert "sales" in issue


def test_self_loading_helper_preflight_rejects_filename_arguments(monkeypatch):
    advisor = ExecutionGenericPreflightAdvisor(_RuntimeStub())

    monkeypatch.setattr(
        "backend.stages.execution.skill.generic_preflight.detect_skills",
        lambda _question: [SimpleNamespace(name="schedule", output_mode="workbook")],
    )
    monkeypatch.setattr(
        "backend.stages.execution.skill.generic_preflight.select_helper",
        lambda _skill, _question: SimpleNamespace(
            name="build_relational_assignment_schedule_report",
            self_loading=True,
            description="Build assignment schedule from relational tables",
        ),
    )

    issue = advisor.offline_preflight_check(
        code_action=(
            "report = build_relational_assignment_schedule_report('students.csv', 'meetings.csv')\n"
            "create_output_sheet('Output')\n"
        ),
        user_question="Build a tutor assignment schedule from multiple tables.",
    )

    assert issue is not None
    assert "must not be called with positional arguments" in issue
    assert "report = build_relational_assignment_schedule_report()" in issue


def test_self_loading_helper_preflight_rejects_dataframe_positional_arguments(monkeypatch):
    advisor = ExecutionGenericPreflightAdvisor(_RuntimeStub())

    monkeypatch.setattr(
        "backend.stages.execution.skill.generic_preflight.detect_skills",
        lambda _question: [SimpleNamespace(name="financial", output_mode="workbook")],
    )
    monkeypatch.setattr(
        "backend.stages.execution.skill.generic_preflight.select_helper",
        lambda _skill, _question: SimpleNamespace(
            name="build_cash_flow_efficiency_report",
            self_loading=True,
            description="Compute cash flow efficiency from a financial statement",
        ),
    )

    issue = advisor.offline_preflight_check(
        code_action=(
            "tables = load_all_tables()\n"
            "df = tables[0]['df']\n"
            "report = build_cash_flow_efficiency_report(df)\n"
            "create_output_sheet('Output')\n"
        ),
        user_question="Evaluate the cash flow efficiency by calculating operating cash flow to net income and free cash flow.",
    )

    assert issue is not None
    assert "must not be called with positional arguments" in issue
    assert "report = build_cash_flow_efficiency_report()" in issue


def test_region_growth_preflight_blocks_manual_header_rebuild(monkeypatch):
    advisor = ExecutionSkillPreflightAdvisor(_RuntimeStub())

    monkeypatch.setattr(
        "backend.stages.execution.skill.preflight.detect_skills",
        lambda _question: [SimpleNamespace(name="aggregate")],
    )
    monkeypatch.setattr(
        "backend.stages.execution.skill.preflight.select_helper",
        lambda _skill, _question: SimpleNamespace(name="build_region_growth_analysis"),
    )

    issue = advisor.metadata_routed_preflight_check(
        code_action=(
            "tables = load_all_tables()\n"
            "df = tables[0]['df']\n"
            "header_row = df.iloc[0]\n"
            "df.columns = header_row\n"
            "report = build_region_growth_analysis(df)\n"
        ),
        user_question="Calculate average penetration for 2020-2024 and rank regions.",
    )

    assert issue is not None
    assert "PREFLIGHT_REGION_GROWTH" in issue
    assert "build_region_growth_analysis()" in issue


def test_region_growth_preflight_requires_helper_instead_of_manual_header_parsing(monkeypatch):
    advisor = ExecutionSkillPreflightAdvisor(_RuntimeStub())

    monkeypatch.setattr(
        "backend.stages.execution.skill.preflight.detect_skills",
        lambda _question: [SimpleNamespace(name="aggregate")],
    )
    monkeypatch.setattr(
        "backend.stages.execution.skill.preflight.select_helper",
        lambda _skill, _question: SimpleNamespace(name="build_region_growth_analysis"),
    )

    issue = advisor.metadata_routed_preflight_check(
        code_action=(
            "tables = load_all_tables()\n"
            "df = tables[0]['df']\n"
            "header_row = None\n"
            "for i, row in df.iterrows():\n"
            "    if any(str(cell).isdigit() for cell in row):\n"
            "        header_row = i - 1\n"
            "headers = df.iloc[header_row].tolist()\n"
            "df_clean = pd.DataFrame(df.iloc[header_row+1:].values.tolist(), columns=headers)\n"
        ),
        user_question="Calculate average penetration for 2020-2024 and rank regions with a line chart.",
    )

    assert issue is not None
    assert "PREFLIGHT_REGION_GROWTH" in issue
    assert "build_region_growth_analysis()" in issue


def test_relational_assignment_preflight_blocks_table_order_guess(monkeypatch):
    advisor = ExecutionSkillPreflightAdvisor(_RuntimeStub())

    monkeypatch.setattr(
        "backend.stages.execution.skill.preflight.detect_skills",
        lambda _question: [SimpleNamespace(name="schedule")],
    )
    monkeypatch.setattr(
        "backend.stages.execution.skill.preflight.select_helper",
        lambda _skill, _question: SimpleNamespace(name="build_relational_assignment_schedule_report"),
    )

    issue = advisor.metadata_routed_preflight_check(
        code_action=(
            "tables = load_all_tables()\n"
            "assignment_df = tables[0]['df']\n"
            "schedule_df = tables[1]['df']\n"
            "merged = pd.merge(assignment_df, schedule_df, left_on='Assigned Tutor', right_on='Tutor Name')\n"
        ),
        user_question="Build a tutor assignment schedule from several tables.",
    )

    assert issue is not None
    assert "PREFLIGHT_ASSIGNMENT_SCHEDULE" in issue
    assert "find_table_by_headers" in issue
    assert "file order" in issue or "list positions" in issue


def test_relational_assignment_preflight_blocks_manual_merge_after_header_selection(monkeypatch):
    advisor = ExecutionSkillPreflightAdvisor(_RuntimeStub())

    monkeypatch.setattr(
        "backend.stages.execution.skill.preflight.detect_skills",
        lambda _question: [SimpleNamespace(name="schedule")],
    )
    monkeypatch.setattr(
        "backend.stages.execution.skill.preflight.select_helper",
        lambda _skill, _question: SimpleNamespace(name="build_relational_assignment_schedule_report"),
    )

    issue = advisor.metadata_routed_preflight_check(
        code_action=(
            "tables = load_all_tables()\n"
            "assignment_t = find_table_by_headers(tables, required_headers=['Assigned Tutor'])\n"
            "schedule_t = find_table_by_headers(tables, required_headers=['Tutor Name', 'Time Slot', 'Room'])\n"
            "output_df = pd.merge(assignment_t['df'], schedule_t['df'], left_on='Assigned Tutor', right_on='Tutor Name')\n"
        ),
        user_question="Build a tutor assignment schedule from several tables.",
    )

    assert issue is not None
    assert "PREFLIGHT_ASSIGNMENT_SCHEDULE" in issue
    assert "build_grouped_assignment_join" in issue


def test_same_schema_merge_summary_preflight_prefers_shared_helpers(monkeypatch):
    advisor = ExecutionSkillPreflightAdvisor(_RuntimeStub())

    monkeypatch.setattr(
        "backend.stages.execution.skill.preflight.detect_skills",
        lambda _question: [SimpleNamespace(name="merge")],
    )
    monkeypatch.setattr(
        "backend.stages.execution.skill.preflight.select_helper",
        lambda _skill, _question: SimpleNamespace(name="concat_tables_with_same_headers"),
    )

    issue = advisor.metadata_routed_preflight_check(
        code_action=(
            "tables = load_all_tables()\n"
            "df1 = tables[0]['df']\n"
            "df2 = tables[1]['df']\n"
            "combined = pd.concat([df1, df2], ignore_index=True)\n"
            "total = combined['Daily Spending (£)'].sum()\n"
            "avg = total / len(combined)\n"
            "data_2d = [combined.columns.tolist()] + combined.values.tolist()\n"
            "write_dataframe_to_sheet(data_2d, 'Output', 'A1')\n"
            "highlight_rows = combined[combined['Daily Spending (£)'] == combined['Daily Spending (£)'].max()].index.tolist()\n"
        ),
        user_question=(
            "Merge two spending tables, calculate the average and total spending, "
            "highlight the highest spending rows, and output a new spreadsheet."
        ),
    )

    assert issue is not None
    assert "PREFLIGHT_CONCAT_MERGE" in issue
    assert "concat_tables_with_same_headers" in issue
    assert "summarize_numeric_column" in issue


def test_same_schema_merge_summary_preflight_blocks_undocumented_summary_result_keys(monkeypatch):
    advisor = ExecutionSkillPreflightAdvisor(_RuntimeStub())

    monkeypatch.setattr(
        "backend.stages.execution.skill.preflight.detect_skills",
        lambda _question: [SimpleNamespace(name="merge")],
    )
    monkeypatch.setattr(
        "backend.stages.execution.skill.preflight.select_helper",
        lambda _skill, _question: SimpleNamespace(name="concat_tables_with_same_headers"),
    )

    issue = advisor.metadata_routed_preflight_check(
        code_action=(
            "tables = load_all_tables()\n"
            "concat_result = concat_tables_with_same_headers(tables)\n"
            "combined_df = concat_result['output_df']\n"
            "combined_df['Date'] = pd.to_datetime(combined_df['Date'], errors='coerce')\n"
            "summary_df = combined_df[combined_df['Date'].dt.month == 11]\n"
            "summary_result = summarize_numeric_column(summary_df, value_col='Daily Spending (£)')\n"
            "max_spending = summary_result['max']\n"
        ),
        user_question=(
            "Merge two spending tables, calculate the average and total spending, "
            "highlight the highest spending rows, and output a new spreadsheet."
        ),
    )

    assert issue is not None
    assert "PREFLIGHT_AGGREGATE" in issue
    assert "output_row_numbers" in issue
    assert "summary_result['summary']" in issue


def test_generic_syntax_preflight_includes_task_loop_breaker_for_merge_tasks():
    advisor = ExecutionGenericPreflightAdvisor(_RuntimeStub())

    issue = advisor.offline_preflight_check(
        code_action=(
            "tables = load_all_tables()\n"
            "summary = {\n"
            "    'Total': 10,\n"
        ),
        user_question=(
            "Merge two spending tables, calculate the average and total spending, "
            "highlight the highest spending rows, and output a new spreadsheet."
        ),
    )

    assert issue is not None
    assert "PREFLIGHT_LINEAR: generated code has a syntax error" in issue
    assert "concat_tables_with_same_headers" in issue
    assert "summarize_numeric_column" in issue


def test_market_share_shipment_preflight_blocks_exact_header_and_table_order_guesses(monkeypatch):
    advisor = ExecutionSkillPreflightAdvisor(_RuntimeStub())

    monkeypatch.setattr(
        "backend.stages.execution.skill.preflight.detect_skills",
        lambda _question: [SimpleNamespace(name="proportion")],
    )
    monkeypatch.setattr(
        "backend.stages.execution.skill.preflight.select_helper",
        lambda _skill, _question: SimpleNamespace(name="build_market_share_shipment_report"),
    )

    issue = advisor.metadata_routed_preflight_check(
        code_action=(
            "tables = load_all_tables()\n"
            "share_df = tables[0]['df']\n"
            "shipment_df = find_table_by_headers(tables, ['Year', 'Shipment'])['df']\n"
            "overlap_df = merge_on_shared_period(share_df, shipment_df, period_col='Time')\n"
        ),
        user_question=(
            "One table gives smartphone units shipped from 2012 to 2025, and another gives "
            "market share from 2017 to 2025. Find the overlapping period and estimate each "
            "brand's units as market_share * shipment."
        ),
    )

    assert issue is not None
    assert "PREFLIGHT_MARKET_SHARE_SHIPMENT" in issue
    assert "many brand columns" in issue
    assert "single numeric value column" in issue
    assert "rename(columns={shipment_value_col: 'Shipment'})" in issue


def test_same_schema_merge_summary_preflight_adds_month_filter_guidance_for_november(monkeypatch):
    advisor = ExecutionSkillPreflightAdvisor(_RuntimeStub())

    monkeypatch.setattr(
        "backend.stages.execution.skill.preflight.detect_skills",
        lambda _question: [SimpleNamespace(name="merge")],
    )
    monkeypatch.setattr(
        "backend.stages.execution.skill.preflight.select_helper",
        lambda _skill, _question: SimpleNamespace(name="concat_tables_with_same_headers"),
    )

    issue = advisor.metadata_routed_preflight_check(
        code_action=(
            "tables = load_all_tables()\n"
            "df1 = tables[0]['df']\n"
            "df2 = tables[1]['df']\n"
            "combined = pd.concat([df1, df2], ignore_index=True)\n"
        ),
        user_question=(
            "Merge two spending tables, calculate the average and total spending in November, "
            "highlight the highest spending rows, and output a new spreadsheet."
        ),
    )

    assert issue is not None
    assert "pd.to_datetime" in issue
    assert ".dt.month == 11" in issue
