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
    def extract_string_list_kwarg(_code, _kwarg):
        return []

    @staticmethod
    def infer_runtime_plan(_skill_name, _helper_name, _user_question, _observed_headers):
        if _helper_name == "compute_feature_correlations":
            return SimpleNamespace(
                target_col="Survived",
                feature_cols=(
                    "Sex", "Age", "Fare", "Pclass", "SibSp", "Parch",
                    "HasCabin", "Embarked_C", "Embarked_Q", "Embarked_S",
                ),
            )
        return SimpleNamespace(target_col="sales", feature_cols=("price", "ad spend"))


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


class _QuestionInferenceWithNormalize(_InferenceStub):
    @staticmethod
    def normalize_header_name_for_grounding(header):
        return re.sub(r"[^a-z0-9]+", "", str(header).lower())

    @staticmethod
    def extract_string_list_kwarg(_code, _kwarg):
        return []


class _TableStub:
    def __init__(self, header):
        self.header = header


class _SchemaRuntimeStub(_RuntimeStub):
    def __init__(self, headers):
        super().__init__()
        self.question_inference = _QuestionInferenceWithNormalize()
        self.world = SimpleNamespace(tables=[_TableStub(header) for header in headers])


class _ObservedHeaderRuntimeStub(_RuntimeStub):
    def __init__(self, headers):
        super().__init__()
        self.question_inference = _QuestionInferenceWithNormalize()
        self._headers = set(headers)

    def _observed_header_set(self):
        return self._headers


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


def test_feature_correlation_preflight_blocks_default_table_window(monkeypatch):
    advisor = ExecutionSkillPreflightAdvisor(_RuntimeStub())

    monkeypatch.setattr(
        "backend.stages.execution.skill.preflight.detect_skills",
        lambda _question: [SimpleNamespace(name="statistical")],
    )
    monkeypatch.setattr(
        "backend.stages.execution.skill.preflight.select_helper",
        lambda _skill, _question: SimpleNamespace(name="compute_feature_correlations"),
    )

    issue = advisor.metadata_routed_preflight_check(
        code_action=(
            "tables = load_all_tables()\n"
            "df = tables[0]['df']\n"
            "feature_cols = ['Sex', 'Age', 'Fare']\n"
            "correlation_result = compute_feature_correlations(df, target_col='Survived', feature_cols=feature_cols)\n"
        ),
        user_question="Calculate Pearson correlation coefficients for the full Titanic dataset.",
    )

    assert issue is not None
    assert issue.startswith("PREFLIGHT_FEATURE_CORRELATION: full-dataset correlation")
    assert "A1:Z200000" in issue


def test_feature_correlation_preflight_blocks_target_in_features(monkeypatch):
    advisor = ExecutionSkillPreflightAdvisor(_RuntimeStub())

    monkeypatch.setattr(
        "backend.stages.execution.skill.preflight.detect_skills",
        lambda _question: [SimpleNamespace(name="statistical")],
    )
    monkeypatch.setattr(
        "backend.stages.execution.skill.preflight.select_helper",
        lambda _skill, _question: SimpleNamespace(name="compute_feature_correlations"),
    )

    issue = advisor.metadata_routed_preflight_check(
        code_action=(
            "tables = load_all_tables(range_ref='A1:Z200000', require_primary_key=False, stop_at_note_row=False)\n"
            "df = tables[0]['df']\n"
            "feature_cols = ['Survived', 'Sex', 'Age', 'Fare']\n"
            "correlation_result = compute_feature_correlations(df, target_col='Survived', feature_cols=feature_cols)\n"
        ),
        user_question="Calculate Pearson correlation coefficients for the full Titanic dataset.",
    )

    assert issue is not None
    assert issue.startswith("PREFLIGHT_FEATURE_CORRELATION: `feature_cols` must exclude the target column.")


def test_feature_correlation_preflight_blocks_recomputing_hascabin(monkeypatch):
    advisor = ExecutionSkillPreflightAdvisor(_RuntimeStub())

    monkeypatch.setattr(
        "backend.stages.execution.skill.preflight.detect_skills",
        lambda _question: [SimpleNamespace(name="statistical")],
    )
    monkeypatch.setattr(
        "backend.stages.execution.skill.preflight.select_helper",
        lambda _skill, _question: SimpleNamespace(name="compute_feature_correlations"),
    )

    issue = advisor.metadata_routed_preflight_check(
        code_action=(
            "tables = load_all_tables(range_ref='A1:Z200000', require_primary_key=False, stop_at_note_row=False)\n"
            "df = tables[0]['df']\n"
            "df['HasCabin'] = df['Cabin'].notnull().astype(int)\n"
            "feature_cols = ['Sex', 'Age', 'Fare', 'Pclass', 'SibSp', 'Parch', 'HasCabin', 'Embarked_C', 'Embarked_Q', 'Embarked_S']\n"
            "correlation_result = compute_feature_correlations(df, target_col='Survived', feature_cols=feature_cols)\n"
        ),
        user_question="Calculate Pearson correlation coefficients using the provided HasCabin column.",
    )

    assert issue is not None
    assert issue.startswith("PREFLIGHT_FEATURE_CORRELATION: do not recompute `HasCabin`")


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
        lambda _question: [SimpleNamespace(name="financial", output_mode="workbook", helpers=())],
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


def test_preflight_blocks_named_agg_source_columns_missing_from_runtime_schema(monkeypatch):
    advisor = ExecutionGenericPreflightAdvisor(_ObservedHeaderRuntimeStub(
        {"SectionID", "Instructor", "Building", "EnrollStatus", "Capacity"}
    ))

    monkeypatch.setattr(
        "backend.stages.execution.skill.generic_preflight.detect_skills",
        lambda _question: [SimpleNamespace(name="aggregate", output_mode="workbook")],
    )
    monkeypatch.setattr(
        "backend.stages.execution.skill.generic_preflight.select_helper",
        lambda _skill, _question: SimpleNamespace(
            name="build_multi_source_utilisation_summary_report",
            self_loading=True,
            description="Aggregate multi-source utilisation ratios and return threshold-based highlight rows",
        ),
    )

    issue = advisor.offline_preflight_check(
        code_action=(
            "report = build_multi_source_utilisation_summary_report()\n"
            "full_data = report['output_df'].copy()\n"
            "section_utilisation = full_data.groupby(['SectionID', 'Instructor'], as_index=False).agg(\n"
            "    Enrolled_Count=('EnrollStatus', lambda x: (x == 'Registered').sum()),\n"
            "    Fill_Rate=('Capacity', 'mean')\n"
            ")\n"
            "instructor_load = section_utilisation.groupby('Instructor').agg(\n"
            "    Total_Enrolled=('Enrolled_Count', 'sum'),\n"
            "    Scheduled_Hours=('ScheduledHours', 'sum')\n"
            ").reset_index()\n"
        ),
        user_question="Build utilisation summaries across multiple university tables.",
    )

    assert issue is not None
    assert issue.startswith("PREFLIGHT_AGG_SOURCE_COLUMNS:")
    assert "ScheduledHours" in issue


def test_self_loading_helper_preflight_requires_helper_instead_of_manual_loading(monkeypatch):
    advisor = ExecutionGenericPreflightAdvisor(_RuntimeStub())

    monkeypatch.setattr(
        "backend.stages.execution.skill.generic_preflight.detect_skills",
        lambda _question: [SimpleNamespace(name="financial", output_mode="workbook", helpers=())],
    )
    monkeypatch.setattr(
        "backend.stages.execution.skill.generic_preflight.select_helper",
        lambda _skill, _question: SimpleNamespace(
            name="build_inventory_eoq_report",
            self_loading=True,
            description="Build EOQ and sensitivity output from an inventory parameter sheet",
        ),
    )

    issue = advisor.offline_preflight_check(
        code_action=(
            "file_paths = list_all_workbooks()\n"
            "table = read_table_multi(file_paths[0], 'Sheet1', 'A1:Z200')\n"
            "df = pd.DataFrame(table['rows'], columns=table['header'])\n"
            "create_output_sheet('Output')\n"
            "saved_file = save_workbook_to(output_path)\n"
            "print(f'SAVED_FILE: {saved_file}')\n"
        ),
        user_question="Calculate EOQ, reorder point, and sensitivity analysis for the inventory data.",
    )

    assert issue is not None
    assert "PREFLIGHT_SELF_LOADING_HELPER" in issue
    assert "build_inventory_eoq_report()" in issue


def test_header_alias_grounding_guard_blocks_missing_currency_suffix_column(monkeypatch):
    advisor = ExecutionGenericPreflightAdvisor(
        _ObservedHeaderRuntimeStub({"EmployeeID", "HoursPerWeek", "PerformanceRating", "MonthlySalary_USD"})
    )

    monkeypatch.setattr(
        "backend.stages.execution.skill.generic_preflight.detect_skills",
        lambda _question: [SimpleNamespace(name="statistical", output_mode="workbook", helpers=())],
    )
    monkeypatch.setattr(
        "backend.stages.execution.skill.generic_preflight.select_helper",
        lambda _skill, _question: None,
    )

    issue = advisor.offline_preflight_check(
        code_action=(
            "tables = load_all_tables()\n"
            "df = tables[0]['df'].copy()\n"
            "correlation = df[['PerformanceRating', 'MonthlySalary']].corr().iloc[0, 1]\n"
            "saved_file = save_workbook_to(output_path)\n"
            "print(f'SAVED_FILE: {saved_file}')\n"
        ),
        user_question="Calculate the Pearson correlation between PerformanceRating and MonthlySalary.",
    )

    assert issue is not None
    assert "PREFLIGHT_HEADER_GROUNDING" in issue
    assert "MonthlySalary" in issue
    assert "MonthlySalary_USD" in issue


def test_header_alias_grounding_guard_ignores_aggregation_function_names(monkeypatch):
    advisor = ExecutionGenericPreflightAdvisor(
        _ObservedHeaderRuntimeStub({"SupplierID", "Country", "POID", "OrderValue"})
    )

    monkeypatch.setattr(
        "backend.stages.execution.skill.generic_preflight.detect_skills",
        lambda _question: [SimpleNamespace(name="merge", output_mode="workbook", helpers=())],
    )
    monkeypatch.setattr(
        "backend.stages.execution.skill.generic_preflight.select_helper",
        lambda _skill, _question: None,
    )

    issue = advisor.offline_preflight_check(
        code_action=(
            "report = build_relational_join_enrichment_report(key_header=None, how='inner')\n"
            "joined_df = report['output_df'].copy()\n"
            "supplier_df = joined_df.groupby('SupplierID', as_index=False).agg(\n"
            "    po_count=('POID', 'count'),\n"
            "    total_value=('OrderValue', 'sum'),\n"
            ")\n"
            "saved_file = save_workbook_to(output_path)\n"
            "print(f'SAVED_FILE: {saved_file}')\n"
            "saved_file\n"
        ),
        user_question="Create a supplier scorecard and buyer summary from procurement tables.",
    )

    assert issue is None


def test_header_alias_grounding_guard_ignores_helper_result_keys():
    advisor = ExecutionGenericPreflightAdvisor(
        _ObservedHeaderRuntimeStub({"Task ID", "Task Name", "Duration (hours)", "Priority", "Depends on"})
    )

    issue = advisor.header_alias_grounding_guard(
        "schedule_result = build_dependency_schedule(task_df, dep_df)\n"
        "print('TASK_ID_SET:', sorted(schedule_result['task_id_set']))\n"
        "print('SCHEDULED_TASK_IDS:', sorted(schedule_result['scheduled_task_ids']))\n"
        "write_dataframe_to_sheet(schedule_result['detail_data'], 'Output', 'A1')\n"
    )

    assert issue is None


def test_preflight_allows_header_grounded_pipeline_when_no_join_helper_covers_task():
    advisor = ExecutionGenericPreflightAdvisor(
        _ObservedHeaderRuntimeStub(
            {
                "StoreID", "ProductID", "Month", "UnitsSold", "DiscountPct",
                "UnitPrice", "UnitCost", "Region", "Category", "RevenueTarget",
            }
        )
    )

    issue = advisor.offline_preflight_check(
        code_action=(
            "tables = load_all_tables()\n"
            "stores_t = find_table_by_headers(tables, required_headers=['StoreID', 'Region'])\n"
            "products_t = find_table_by_headers(tables, required_headers=['ProductID', 'Category', 'UnitPrice', 'UnitCost'])\n"
            "sales_t = find_table_by_headers(tables, required_headers=['StoreID', 'ProductID', 'Month', 'UnitsSold', 'DiscountPct'])\n"
            "targets_t = find_table_by_headers(tables, required_headers=['StoreID', 'Category', 'Month', 'RevenueTarget'])\n"
            "sales = sales_t['df'].copy()\n"
            "stores = stores_t['df'].copy()\n"
            "products = products_t['df'].copy()\n"
            "targets = targets_t['df'].copy()\n"
            "h2 = sales[(sales['Month'] >= '2024-07') & (sales['Month'] <= '2024-12')]\n"
            "h2 = h2.merge(stores, on='StoreID', how='inner').merge(products, on='ProductID', how='inner')\n"
            "h2['NetRevenue'] = h2['UnitsSold'] * h2['UnitPrice'] * (1 - h2['DiscountPct'] / 100)\n"
            "region_category = h2.groupby(['Region', 'Category'], as_index=False).agg(NetRevenue=('NetRevenue', 'sum'))\n"
            "create_output_sheet('Region_Category_H2')\n"
            "write_dataframe_to_sheet(region_category, 'Region_Category_H2', 'A1')\n"
            "saved_file = save_workbook_to(output_path)\n"
            "print(f'SAVED_FILE: {saved_file}')\n"
            "saved_file\n"
        ),
        user_question=(
            "Join the tables using StoreID and ProductID, keep only the H2 2024 months, compute net revenue, "
            "aggregate the results by Region and Category, compare each aggregate to the revenue target, "
            "create a Top 10 store leaderboard, and output three sheets."
        ),
    )

    assert issue is None


def test_preflight_blocks_placeholder_helper_imports(monkeypatch):
    advisor = ExecutionGenericPreflightAdvisor(
        _ObservedHeaderRuntimeStub({"SupplierID", "POID", "OrderValue"})
    )

    monkeypatch.setattr(
        "backend.stages.execution.skill.generic_preflight.detect_skills",
        lambda _question: [SimpleNamespace(name="merge", output_mode="workbook", helpers=())],
    )
    monkeypatch.setattr(
        "backend.stages.execution.skill.generic_preflight.select_helper",
        lambda _skill, _question: None,
    )

    issue = advisor.offline_preflight_check(
        code_action=(
            "from your_spreadsheet_helpers import *\n"
            "report = build_relational_join_enrichment_report(key_header=None, how='inner')\n"
            "saved_file = save_workbook_to(output_path)\n"
            "print(f'SAVED_FILE: {saved_file}')\n"
            "saved_file\n"
        ),
        user_question="Create a supplier scorecard and buyer summary from procurement tables.",
    )

    assert issue is not None
    assert "PREFLIGHT_LINEAR" in issue
    assert "already injected into the sandbox globals" in issue


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


def test_concat_merge_guard_skips_cross_schema_tables(monkeypatch):
    advisor = ExecutionSkillPreflightAdvisor(
        _SchemaRuntimeStub(
            headers=[
                ["EmployeeID", "Name"],
                ["EmployeeID", "MonthlySalary_USD"],
            ]
        )
    )

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
            "left = tables[0]['df']\n"
            "right = tables[1]['df']\n"
            "combined = left.merge(right, on='EmployeeID', how='inner')\n"
        ),
        user_question="Merge the two files into a single file.",
    )

    assert issue is None


def test_concat_merge_guard_does_not_infer_month_from_non_month_word(monkeypatch):
    advisor = ExecutionSkillPreflightAdvisor(
        _SchemaRuntimeStub(
            headers=[
                ["Store ID", "Sales"],
                ["Store ID", "Sales"],
            ]
        )
    )

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
            "combined = pd.concat([t['df'] for t in tables], ignore_index=True)\n"
        ),
        user_question="Merge the two files and maybe compute the total sales.",
    )

    assert issue is not None
    assert "month 5" not in issue


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
    advisor = ExecutionSkillPreflightAdvisor(
        _SchemaRuntimeStub(
            headers=[
                ["Date", "Category", "Daily Spending (£)", "Notes"],
                ["Date", "Category", "Daily Spending (£)", "Notes"],
            ]
        )
    )

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
    assert "highlight_rows" in issue
    assert "output_row_numbers" not in issue
    assert "summary_result['summary']" in issue
    assert "max_indices" not in issue


def test_same_schema_merge_summary_preflight_blocks_summary_write_dataframe_mismatch(monkeypatch):
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
            "daily_spending = combined_df.groupby('Day')['Amount_GBP'].sum()\n"
            "summary_data = daily_spending.reset_index()\n"
            "create_output_sheet('Output')\n"
            "write_dataframe_to_sheet(summary_data, 'Output', 'A1')\n"
            "summary_result = summarize_numeric_column(combined_df, value_col='Amount_GBP')\n"
            "add_summary_row('Output', len(summary_data) + 2, summary_result['summary'])\n"
            "highlight_rows('Output', summary_result['max_indices'], {'fill_color': 'red'})\n"
        ),
        user_question=(
            "Merge two spending tables, calculate the average and total spending, "
            "highlight the highest spending rows, and output a new spreadsheet."
        ),
    )

    assert issue is not None
    assert "PREFLIGHT_SUMMARY_OUTPUT_ALIGNMENT" in issue
    assert "combined_df" in issue
    assert "summary_data" in issue


def test_highlight_preflight_blocks_summary_max_indices_for_excel_rows():
    advisor = ExecutionSkillPreflightAdvisor(_RuntimeStub())

    issue = advisor.highlight_guard(
        code_action=(
            "summary_result = summarize_numeric_column(combined_df, value_col='Amount_GBP')\n"
            "write_dataframe_to_sheet(combined_df, 'Output', 'A1')\n"
            "highlight_rows('Output', summary_result['max_indices'], {'fill_color': 'red'})\n"
        ),
        user_question="Highlight in red the day on which I spend the most.",
    )

    assert issue is not None
    assert "PREFLIGHT_HIGHLIGHT" in issue
    assert "highlight_rows" in issue
    assert "max_indices" in issue


def test_highlight_preflight_allows_manual_header_offset_enumerate_rows():
    advisor = ExecutionSkillPreflightAdvisor(_RuntimeStub())

    issue = advisor.highlight_guard(
        code_action=(
            "summary_result = summarize_numeric_column(daily_totals, value_col='Amount_GBP')\n"
            "write_dataframe_to_sheet(daily_totals, 'Output', 'A1')\n"
            "max_val = daily_totals['Amount_GBP'].max()\n"
            "row_numbers = [i + 2 for i, v in enumerate(daily_totals['Amount_GBP']) if v == max_val]\n"
            "highlight_rows('Output', row_numbers, {'fill_color': 'red'})\n"
        ),
        user_question="Highlight in red the day on which I spend the most.",
    )

    assert issue is None


def test_highlight_preflight_blocks_inline_index_from_dataframe_not_written():
    advisor = ExecutionSkillPreflightAdvisor(_RuntimeStub())

    issue = advisor.highlight_guard(
        code_action=(
            "write_dataframe_to_sheet(combined_df, 'Output', 'A1')\n"
            "highlight_rows('Output', [daily_spending[daily_spending['Day'] == max_day].index[0] + 2], {'fill_color': 'red'})\n"
        ),
        user_question="Highlight in red the day on which I spend the most.",
    )

    assert issue is not None
    assert "PREFLIGHT_HIGHLIGHT" in issue
    assert "daily_spending" in issue
    assert "combined_df" in issue


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


def test_generic_preflight_allows_return_inside_nested_function():
    advisor = ExecutionGenericPreflightAdvisor(
        _ObservedHeaderRuntimeStub({"GraphID", "Contains_Cycle"})
    )

    issue = advisor.offline_preflight_check(
        code_action=(
            "def has_cycle(graph):\n"
            "    if graph:\n"
            "        return True\n"
            "    return False\n"
            "tables = load_all_tables()\n"
            "create_output_sheet('Output')\n"
            "write_dataframe_to_sheet([['GraphID', 'Contains_Cycle'], ['g1', True]], 'Output', 'A1')\n"
            "saved_file = save_workbook_to(output_path)\n"
            "print('SAVED_FILE:', saved_file)\n"
            "saved_file\n"
        ),
        user_question="Determine which graphs contain a cycle and write the result to an Excel file.",
    )

    assert issue is None


def test_generic_preflight_blocks_actual_top_level_return():
    advisor = ExecutionGenericPreflightAdvisor(
        _ObservedHeaderRuntimeStub({"GraphID", "Contains_Cycle"})
    )

    issue = advisor.offline_preflight_check(
        code_action=(
            "tables = load_all_tables()\n"
            "saved_file = save_workbook_to(output_path)\n"
            "return saved_file\n"
        ),
        user_question="Write the result to an Excel file.",
    )

    assert issue is not None
    assert "top-level `return` is invalid" in issue


def test_generic_preflight_blocks_dataframe_ops_on_detail_data():
    advisor = ExecutionGenericPreflightAdvisor(
        _ObservedHeaderRuntimeStub({"Month", "Revenue_USD"})
    )

    issue = advisor.offline_preflight_check(
        code_action=(
            "dashboard_result = build_financial_dashboard_report()\n"
            "total_revenue = dashboard_result['detail_data'].sum()\n"
            "saved_file = save_workbook_to(output_path)\n"
            "print('SAVED_FILE:', saved_file)\n"
            "saved_file\n"
        ),
        user_question="Build a financial dashboard comparing actuals to targets.",
    )

    assert issue is not None
    assert "detail_data" in issue
    assert "output_df" in issue


def test_weighted_share_value_preflight_blocks_exact_header_and_table_order_guesses(monkeypatch):
    advisor = ExecutionSkillPreflightAdvisor(_RuntimeStub())

    monkeypatch.setattr(
        "backend.stages.execution.skill.preflight.detect_skills",
        lambda _question: [SimpleNamespace(name="proportion")],
    )
    monkeypatch.setattr(
        "backend.stages.execution.skill.preflight.select_helper",
        lambda _skill, _question: SimpleNamespace(name="build_weighted_share_value_report"),
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
    advisor = ExecutionSkillPreflightAdvisor(
        _SchemaRuntimeStub(
            headers=[
                ["Date", "Category", "Daily Spending (£)", "Notes"],
                ["Date", "Category", "Daily Spending (£)", "Notes"],
            ]
        )
    )

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


def test_market_share_question_does_not_false_trigger_month_filter(monkeypatch):
    advisor = ExecutionSkillPreflightAdvisor(_RuntimeStub())

    monkeypatch.setattr(
        "backend.stages.execution.skill.preflight.detect_skills",
        lambda _question: [SimpleNamespace(name="proportion")],
    )
    monkeypatch.setattr(
        "backend.stages.execution.skill.preflight.select_helper",
        lambda _skill, _question: SimpleNamespace(name="build_weighted_share_value_report"),
    )

    issue = advisor.metadata_routed_preflight_check(
        code_action=(
            "tables = load_all_tables()\n"
            "share_table = find_table_by_headers(tables, required_headers=['Quarter', 'Tata'])\n"
            "units_table = find_table_by_headers(tables, required_headers=['Quarter', 'Total_EV_Units_thousand'])\n"
            "overlap_df = merge_on_shared_period(share_table['df'], units_table['df'], period_col='Quarter')\n"
            "output_df = build_weighted_period_output(\n"
            "    overlap_df,\n"
            "    period_col='Quarter',\n"
            "    value_columns=['Tata', 'MG', 'Hyundai', 'Mahindra', 'Kia', 'Others'],\n"
            "    weight_col='Total_EV_Units_thousand',\n"
            "    output_period_col='Quarter',\n"
            "    output_label_template='{name}',\n"
            ")\n"
        ),
        user_question=(
            "One table gives total EV units sold in India by quarter, and the other gives "
            "market share by brand. Find the overlapping time period and estimate each "
            "brand's EV units sold."
        ),
    )

    assert issue is None or "PREFLIGHT_TEMPORAL_FILTER" not in issue


def test_market_share_overlap_does_not_false_trigger_aggregate_guard(monkeypatch):
    advisor = ExecutionSkillPreflightAdvisor(_RuntimeStub())

    monkeypatch.setattr(
        "backend.stages.execution.skill.preflight.detect_skills",
        lambda _question: [SimpleNamespace(name="merge")],
    )
    monkeypatch.setattr(
        "backend.stages.execution.skill.preflight.select_helper",
        lambda _skill, _question: SimpleNamespace(name="concat_tables_with_same_headers"),
    )

    issue = advisor.aggregate_summary_guard(
        code_action=(
            "tables = load_all_tables()\n"
            "units_df = tables[0]['df']\n"
            "share_df = tables[1]['df']\n"
            "merged = units_df.merge(share_df, on='Quarter', how='inner')\n"
        ),
        user_question=(
            "Here are two tables. One gives the total EV units sold in India by quarter (2020-2022), "
            "and the other gives market share by brand (2021-2022). Find the overlapping time period, "
            "then estimate the number of EVs sold for each brand."
        ),
        helper_name="concat_tables_with_same_headers",
    )

    assert issue is None


def test_market_share_overlap_does_not_false_trigger_temporal_filter_guard():
    advisor = ExecutionSkillPreflightAdvisor(_RuntimeStub())

    issue = advisor.temporal_filter_guard(
        code_action=(
            "result_df = merged.copy()\n"
            "summary_result = summarize_numeric_column(result_df, value_col='Total_EV_Units_thousand')\n"
        ),
        user_question=(
            "Here are two tables. One gives the total EV units sold in India by quarter (2020-2022), "
            "and the other gives market share by brand (2021-2022). Find the overlapping time period."
        ),
        helper_name="build_weighted_share_value_report",
    )

    assert issue is None


def test_self_loading_embedded_summary_helper_blocks_extra_summary_rows(monkeypatch):
    advisor = ExecutionGenericPreflightAdvisor(_RuntimeStub())

    monkeypatch.setattr(
        "backend.stages.execution.skill.generic_preflight.detect_skills",
        lambda _question: [SimpleNamespace(name="financial", output_mode="workbook")],
    )
    monkeypatch.setattr(
        "backend.stages.execution.skill.generic_preflight.select_helper",
        lambda _skill, _question: SimpleNamespace(
            name="build_financial_dashboard_report",
            self_loading=True,
        ),
    )

    issue = advisor.offline_preflight_check(
        code_action=(
            "dashboard_result = build_financial_dashboard_report()\n"
            "create_output_sheet('Output')\n"
            "write_dataframe_to_sheet(dashboard_result['detail_data'], 'Output', 'A1')\n"
            "add_summary_row('Output', len(dashboard_result['detail_data']) + 2, {'Target': 1})\n"
            "saved_file = save_workbook_to(output_path)\n"
        ),
        user_question="Calculate financial dashboard metrics and compare actuals to targets.",
    )

    assert issue is not None
    assert "already returns the final report table" in issue
    assert "Do not add extra `add_summary_row" in issue


def test_self_loading_embedded_summary_helper_blocks_output_df_recalculation(monkeypatch):
    advisor = ExecutionGenericPreflightAdvisor(_RuntimeStub())

    monkeypatch.setattr(
        "backend.stages.execution.skill.generic_preflight.detect_skills",
        lambda _question: [SimpleNamespace(name="financial", output_mode="workbook")],
    )
    monkeypatch.setattr(
        "backend.stages.execution.skill.generic_preflight.select_helper",
        lambda _skill, _question: SimpleNamespace(
            name="build_financial_dashboard_report",
            self_loading=True,
        ),
    )

    issue = advisor.offline_preflight_check(
        code_action=(
            "dashboard_result = build_financial_dashboard_report()\n"
            "output_df = dashboard_result['output_df']\n"
            "output_df['Gross_Profit'] = output_df['Revenue_USD'] - output_df['COGS_USD']\n"
            "create_output_sheet('Output')\n"
            "write_dataframe_to_sheet(output_df, 'Output', 'A1')\n"
            "saved_file = save_workbook_to(output_path)\n"
        ),
        user_question="Calculate financial dashboard metrics and compare actuals to targets.",
    )

    assert issue is not None
    assert "do not treat `output_df` as raw source data" in issue
    assert "Write `report['detail_data']` directly" in issue


def test_text_scan_self_loading_helper_blocks_dataframe_access(monkeypatch):
    advisor = ExecutionGenericPreflightAdvisor(_RuntimeStub())

    monkeypatch.setattr(
        "backend.stages.execution.skill.generic_preflight.detect_skills",
        lambda _question: [SimpleNamespace(name="scan", output_mode="text")],
    )
    monkeypatch.setattr(
        "backend.stages.execution.skill.generic_preflight.select_helper",
        lambda _skill, _question: SimpleNamespace(
            name="build_room_format_report",
            self_loading=True,
        ),
    )

    issue = advisor.offline_preflight_check(
        code_action=(
            "report = build_room_format_report()\n"
            "for row in report['output_df'].values:\n"
            "    print(row)\n"
            "print('FINAL_TEXT:', report['answer'])\n"
        ),
        user_question="Inspect ProductCode for inconsistent formatting.",
    )

    assert issue is not None
    assert "returns a text report, not a DataFrame" in issue
    assert "report['answer']" in issue


def test_fill_missing_blocks_duplicate_table_role_selector(monkeypatch):
    advisor = ExecutionGenericPreflightAdvisor(_RuntimeStub())

    monkeypatch.setattr(
        "backend.stages.execution.skill.generic_preflight.detect_skills",
        lambda _question: [SimpleNamespace(name="merge", output_mode="workbook")],
    )
    monkeypatch.setattr(
        "backend.stages.execution.skill.generic_preflight.select_helper",
        lambda _skill, _question: SimpleNamespace(
            name="fill_missing_from_reference",
            self_loading=False,
        ),
    )

    issue = advisor.offline_preflight_check(
        code_action=(
            "tables = load_all_tables()\n"
            "input01_data = next(table for table in tables if \"EmpID\" in table['df'].columns and \"Department\" in table['df'].columns)\n"
            "input02_data = next(table for table in tables if \"EmpID\" in table['df'].columns and \"Department\" in table['df'].columns)\n"
            "result = fill_missing_from_reference(input01_data['df'], input02_data['df'], key_header='EmpID')\n"
            "create_output_sheet('Output')\n"
            "write_dataframe_to_sheet(result['detail_data'], 'Output', 'A1')\n"
            "saved_file = save_workbook_to(output_path)\n"
        ),
        user_question="Fill missing employee departments using a reference file.",
    )

    assert issue is not None
    assert "same selector" in issue
    assert "find_table_by_headers" in issue


def test_fill_missing_reference_selector_requires_forbidden_headers(monkeypatch):
    advisor = ExecutionGenericPreflightAdvisor(_RuntimeStub())

    monkeypatch.setattr(
        "backend.stages.execution.skill.generic_preflight.detect_skills",
        lambda _question: [SimpleNamespace(name="merge", output_mode="workbook")],
    )
    monkeypatch.setattr(
        "backend.stages.execution.skill.generic_preflight.select_helper",
        lambda _skill, _question: SimpleNamespace(
            name="fill_missing_from_reference",
            self_loading=False,
        ),
    )

    issue = advisor.offline_preflight_check(
        code_action=(
            "tables = load_all_tables()\n"
            "primary_t = find_table_by_headers(tables, required_headers=['EmpID', 'Name', 'Department', 'JobGrade'], preferred_headers=['Name', 'JobGrade'])\n"
            "reference_t = find_table_by_headers(tables, required_headers=['EmpID', 'Department'], preferred_headers=['Department'])\n"
            "result = fill_missing_from_reference(primary_t['df'], reference_t['df'], key_header='EmpID')\n"
            "create_output_sheet('Output')\n"
            "write_dataframe_to_sheet(result['detail_data'], 'Output', 'A1')\n"
            "saved_file = save_workbook_to(output_path)\n"
        ),
        user_question="Fill missing employee departments using a reference file.",
    )

    assert issue is not None
    assert "reference table selection is too broad" in issue
    assert "forbidden_headers" in issue
