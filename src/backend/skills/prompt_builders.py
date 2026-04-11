"""Prompt-building helpers: skill hints, execution rules, loop breakers."""

from __future__ import annotations

from .models import HelperSpec, SkillSpec
from .helper_metadata import get_helper_documented_result_keys, helper_result_variable_name


def build_skill_hint(skill: SkillSpec, helper: HelperSpec) -> str:
    """Return the skill strategy doc for injection into the understanding prompt."""
    doc = skill.strategy_doc or (
        f"[SKILL: {skill.name.upper()}]\n"
        f"Recommended helper: `{helper.name}()`\n"
        f"Description: {helper.description}"
    )
    return doc


def build_compact_skill_workflow(skill: SkillSpec, helper: HelperSpec) -> str:
    name = skill.name.lower()
    label = skill.name.upper()

    workflows = {
        "merge": (
            f"[{label} WORKFLOW]\n"
            "- Load runtime tables and print real headers.\n"
            "- Classify same-schema concat vs shared-key join from observed columns.\n"
            "- Same-schema stack tasks: `concat_result = concat_tables_with_same_headers(tables)` then use `combined_df = concat_result['output_df']`.\n"
            "- If the question asks for totals/averages/max highlight, compute them with `summarize_numeric_column(summary_df, value_col='...')` after any verified filter.\n"
            "- Write the DataFrame directly with `write_dataframe_to_sheet(df, 'Output', 'A1')`; do not hand-build `data_2d`.\n"
            "- Put any summary row strictly below the written table, keep `highlight_rows(...)` as the function name, then save."
        ),
        "aggregate": (
            f"[{label} WORKFLOW]\n"
            "- Identify the main table and verified group/date/value columns.\n"
            "- For messy period blocks, use shared extraction helpers before aggregating.\n"
            "- Compute the requested summary/ranking/chart data.\n"
            "- Then write Output and save."
        ),
        "schedule": (
            f"[{label} WORKFLOW]\n"
            "- Load all runtime tables and classify table roles by headers, not filenames.\n"
            "- Dependency tasks: select task/dependency tables, then schedule.\n"
            "- Relational assignment tasks: use `find_table_by_headers(...)` for the assignment/schedule tables.\n"
            "- Prefer `Assigned Tutor` + entity headers like `Student Name`/`Name`, then join to `Tutor Name` + `Time Slot` + `Room`.\n"
            "- Then write the 5-column Output table and save."
        ),
        "statistical": (
            f"[{label} WORKFLOW]\n"
            "- Verify numeric/target columns from runtime schema.\n"
            "- Use shared statistical helpers or concise pandas math.\n"
            "- Write the resulting table to Output and save."
        ),
        "proportion": (
            f"[{label} WORKFLOW]\n"
            "- Verify value/group or shared-period columns from runtime schema.\n"
            "- For two period tables, classify the wider table with many brand columns as market share and the narrower table with one numeric value column as shipment.\n"
            "- Normalize both tables to a shared `Time` column, then rename the shipment table's single numeric value column to `Shipment`.\n"
            "- Align overlap with `merge_on_shared_period(...)`, then scale brand columns with `build_weighted_period_output(...)`.\n"
            "- Write Output and save."
        ),
        "rank": (
            f"[{label} WORKFLOW]\n"
            "- Verify score columns and weights from runtime schema.\n"
            "- Compute score, add rank, then write Output and save."
        ),
        "financial": (
            f"[{label} WORKFLOW]\n"
            "- Verify numerator/denominator or year/value columns.\n"
            "- Compute ratio or YoY change, then write Output and save."
        ),
        "scan": (
            f"[{label} WORKFLOW]\n"
            "- Inspect runtime tables for the requested audit condition.\n"
            "- Return concise text only; do not save a workbook."
        ),
    }
    workflow = workflows.get(name)
    if workflow:
        return workflow
    return (
        f"[{label} WORKFLOW]\n"
        f"- Treat `{skill.name}` as the primary skill and `{helper.name}` as the matched helper family.\n"
        "- Ground every step in runtime headers.\n"
        "- Compose the transformation, then write Output and save."
    )


def build_execution_strict_rules(skill: SkillSpec, helper: HelperSpec, plan_summary: str = "") -> str:
    label = skill.name.upper()
    lines = [
        f"\n\n**{label} SKILL RULES (STRICT):**",
        f"- Treat `{skill.name}` as the primary task skill.",
        "- Build the solution from shared runtime helpers and verified schema.",
        "- Compose the task step by step: read/inspect -> transform/analyze -> write Output -> save workbook.",
        "- Choose helpers that fit the observed tables and requested output, not the benchmark title.",
    ]
    if plan_summary:
        lines.extend(
            [
                "**RUNTIME PLAN (TRUST THIS):**",
                plan_summary,
            ]
        )
    if helper.name == "build_relational_assignment_schedule_report":
        lines.extend(
            [
                "- For relational assignment schedules, never choose source tables from filenames, literal basenames, or `tables[0]` / `tables[1]`.",
                "- Use `find_table_by_headers(...)` to identify the assignment table from `Assigned Tutor` plus entity headers like `Student Name` / `Name` / `Student`.",
                "- Use `find_table_by_headers(...)` to identify the schedule table from `Tutor Name` + `Time Slot` + `Room`.",
                "- You may call `build_relational_assignment_schedule_report()` directly when that matched helper fits the observed headers.",
            ]
        )
    elif helper.name == "build_dependency_schedule":
        lines.extend(
            [
                "- For dependency scheduling, classify the task table and dependency table by verified headers, not filenames or file order.",
                "- Use `find_table_by_headers(...)` to select the task table with `Task ID` and without `Depends on`.",
                "- Use `find_table_by_headers(...)` to select the dependency table with `Task ID` + `Depends on`.",
                "- Call `build_dependency_schedule(task_table['df'], dependency_table['df'], start_time='08:00')` instead of hand-writing DAG traversal.",
                "- Print `TASK_ID_SET` and `SCHEDULED_TASK_IDS` before saving so schedule coverage stays grounded in the runtime tables.",
                "- Write `schedule_result['detail_data']`, then add the total-duration summary from `schedule_result['summary']` before saving.",
            ]
        )
    elif helper.name == "concat_tables_with_same_headers":
        lines.extend(
            [
                "- For same-schema merge + summary tasks, prefer `concat_tables_with_same_headers(tables)` plus `summarize_numeric_column(...)` over hand-written `pd.concat(...)` bookkeeping.",
                "- Write the result DataFrame directly with `write_dataframe_to_sheet(df, 'Output', 'A1')`; do not hand-build `data_2d` from headers + values.",
                "- Add any summary row strictly below the written table, and do not shadow sandbox function names like `highlight_rows`.",
                "- Do not replace the whole task with a single task-shaped helper shortcut.",
            ]
        )
    elif helper.name == "build_market_share_shipment_report":
        lines.extend(
            [
                "- Do NOT call `build_market_share_shipment_report()` directly.",
                "- Build a generic share table and shipment table from observed period columns, not from an assumed exact `Shipment` header.",
                "- The market-share table is the wider one with many brand columns; the shipment table is the narrower one with a single numeric value column.",
                "- Rename that single numeric shipment column to `Shipment` before the weighted merge.",
                "- Align the overlap with `merge_on_shared_period(...)` before computing the weighted output.",
                "- Use `build_weighted_period_output(...)` to scale the share columns by the shipment column into the final output table.",
            ]
        )
    elif helper.name == "build_region_growth_analysis":
        lines.extend(
            [
                "- For messy region/year penetration sheets, prefer `build_region_growth_analysis(...)` over hand-written header-row parsing.",
                "- Write `region_growth_result['output_df']` to `Output`, add `region_growth_result['summary']`, and embed the line chart with `save_plot_to_excel(...)`.",
                "- If the requested start year is unavailable, shrink the helper year window to the available requested years instead of interpolating.",
            ]
        )
    elif helper.name == "compute_feature_correlations":
        lines.extend(
            [
                "- For target-vs-feature correlation tasks, infer the target and feature columns from the runtime plan and current runtime schema, not from a benchmark recipe.",
                "- Prefer `compute_feature_correlations(...)` over a full correlation matrix when the question asks for one target versus several factors.",
                "- Keep preprocessing schema-driven: apply binary coercion or categorical encoding only when the selected feature columns require it.",
                "- Use pairwise deletion naturally by leaving missing values as NaN; do not drop the whole table because one selected feature has gaps.",
                "- Write a one-row output table with the selected feature headers, not a `Feature | Correlation` long-form table, unless the user explicitly asks for long form.",
            ]
        )
    else:
        lines.append("- Do not replace the whole task with a single task-shaped helper shortcut.")
    if helper.description and helper.name != "build_relational_assignment_schedule_report":
        lines.append(
            f"- Matched helper family for reference only: `{helper.name}` ({helper.description})."
        )
    return "\n".join(lines) + "\n"


def build_loop_breaker(skill: SkillSpec, helper: HelperSpec, plan_summary: str = "") -> str:
    label = skill.name.upper()
    if skill.output_mode == "text":
        return (
            f"\n{label} LOOP BREAKER:\n"
            "- Read the relevant tables, compute the text answer, and print `FINAL_TEXT:`.\n"
            "- Do not create or save an output workbook.\n"
            "- Do not collapse the task into a single task-shaped helper call.\n"
        )
    if helper.name == "build_relational_assignment_schedule_report":
        return (
            f"\n{label} LOOP BREAKER:\n"
            "- Use this grounded workflow shape:\n"
            "  `tables = load_all_tables()`\n"
            "  `assignment_t = find_table_by_headers(tables, required_headers=['Assigned Tutor'], preferred_headers=['Student Name', 'Name', 'Student'])`\n"
            "  `schedule_t = find_table_by_headers(tables, required_headers=['Tutor Name', 'Time Slot', 'Room'])`\n"
            "  `output_df = build_grouped_assignment_join(assignment_t['df'], 'Assigned Tutor', 'Name', schedule_t['df'], 'Tutor Name', ['Time Slot', 'Room'])`\n"
            "  `# or call build_relational_assignment_schedule_report() when the matched helper fits exactly`\n"
            "  `create_output_sheet('Output')`\n"
            "  `write_dataframe_to_sheet(output_df, 'Output', 'A1')`\n"
            "  `saved_file = save_workbook_to(output_path)`\n"
            "  `print(f'SAVED_FILE: {saved_file}')`\n"
            "  `saved_file`\n"
        )
    if helper.name == "build_dependency_schedule":
        return (
            f"\n{label} LOOP BREAKER:\n"
            "- Use this grounded workflow shape for dependency scheduling:\n"
            "  `tables = load_all_tables()`\n"
            "  `task_table = find_table_by_headers(tables, required_headers=['Task ID'], forbidden_headers=['Depends on'])`\n"
            "  `dependency_table = find_table_by_headers(tables, required_headers=['Task ID', 'Depends on'])`\n"
            "  `schedule_result = build_dependency_schedule(task_table['df'], dependency_table['df'], start_time='08:00')`\n"
            "  `print('TASK_ID_SET:', sorted(schedule_result['task_id_set']))`\n"
            "  `print('SCHEDULED_TASK_IDS:', sorted(schedule_result['scheduled_task_ids']))`\n"
            "  `create_output_sheet('Output')`\n"
            "  `write_dataframe_to_sheet(schedule_result['detail_data'], 'Output', 'A1')`\n"
            "  `summary_row = len(schedule_result['detail_data']) + 2`\n"
            "  `add_summary_row('Output', summary_row, schedule_result['summary'])`\n"
            "  `saved_file = save_workbook_to(output_path)`\n"
            "  `print(f'SAVED_FILE: {saved_file}')`\n"
            "  `saved_file`\n"
        )
    if helper.name == "concat_tables_with_same_headers":
        return (
            f"\n{label} LOOP BREAKER:\n"
            "- Use this helper-grounded workflow shape for same-schema merge/summary tasks:\n"
            "  `tables = load_all_tables()`\n"
            "  `concat_result = concat_tables_with_same_headers(tables)`\n"
            "  `combined_df = concat_result['output_df']`\n"
            "  `summary_df = combined_df  # or a verified filtered subset before summarizing`\n"
            "  `summary_result = summarize_numeric_column(summary_df, value_col='...')`\n"
            "  `create_output_sheet('Output')`\n"
            "  `write_dataframe_to_sheet(summary_df, 'Output', 'A1')`\n"
            "  `summary_row = len(summary_df) + 2`\n"
            "  `add_summary_row('Output', summary_row, summary_result['summary'])`\n"
            "  `row_numbers = summary_result['output_row_numbers']`\n"
            "  `highlight_rows('Output', row_numbers, {'fill_color': 'red'})`\n"
            "  `saved_file = save_workbook_to(output_path)`\n"
            "  `print(f'SAVED_FILE: {saved_file}')`\n"
            "  `saved_file`\n"
            "- Write the DataFrame directly; do not hand-build `data_2d`.\n"
            "- If you highlight a different written frame than `summary_df`, recompute row numbers against the written frame instead of reusing `output_row_numbers`.\n"
        )
    if helper.name == "build_market_share_shipment_report":
        return (
            f"\n{label} LOOP BREAKER:\n"
            "- Use this grounded skeleton for title-heavy period sheets:\n"
            "  ```python\n"
            "  tables = load_all_tables(require_primary_key=False, stop_at_note_row=False)\n"
            "  for t in tables:\n"
            "      print(t['file_name'], t.get('sheet_name'), t['df'].columns.tolist())\n"
            "  share_t = max(tables, key=lambda t: len(t['df'].columns))  # many brand columns\n"
            "  shipment_t = min(tables, key=lambda t: len(t['df'].columns))  # single numeric value column\n"
            "  share_df = share_t['df'].copy()\n"
            "  shipment_df = shipment_t['df'].copy()\n"
            "  if 'Year' in share_df.columns:\n"
            "      share_df = share_df.rename(columns={'Year': 'Time'})\n"
            "  if 'Year' in shipment_df.columns:\n"
            "      shipment_df = shipment_df.rename(columns={'Year': 'Time'})\n"
            "  shipment_value_cols = [c for c in shipment_df.columns if c != 'Time']\n"
            "  shipment_value_col = shipment_value_cols[0]\n"
            "  shipment_df = shipment_df.rename(columns={shipment_value_col: 'Shipment'})\n"
            "  overlap_df = merge_on_shared_period(share_df, shipment_df[['Time', 'Shipment']], period_col='Time')\n"
            "  brand_cols = [c for c in share_df.columns if c != 'Time']\n"
            "  output_df = build_weighted_period_output(\n"
            "      overlap_df,\n"
            "      period_col='Time',\n"
            "      value_columns=brand_cols,\n"
            "      weight_col='Shipment',\n"
            "      output_period_col='Time',\n"
            "      output_label_template='{name} (Unit shipment)',\n"
            "  )\n"
            "  create_output_sheet('Output')\n"
            "  write_dataframe_to_sheet(output_df, 'Output', 'A1')\n"
            "  saved_file = save_workbook_to(output_path)\n"
            "  print(f'SAVED_FILE: {saved_file}')\n"
            "  saved_file\n"
            "  ```\n"
            "- The market-share table is the wider one with many brand columns.\n"
            "- The shipment table is the one with `Time` plus a single numeric value column; rename that column to `Shipment`.\n"
            "- Do not return prose; return one runnable code block.\n"
        )
    if helper.name == "build_region_growth_analysis":
        return (
            f"\n{label} LOOP BREAKER:\n"
            "- Use the runtime region-growth helper instead of parsing the multi-row header yourself:\n"
            "  ```python\n"
            "  region_growth_result = build_region_growth_analysis(sheet_name='Data', start_year=2021, end_year=2024)\n"
            "  create_output_sheet('Output')\n"
            "  write_dataframe_to_sheet(region_growth_result['output_df'], 'Output', 'A1')\n"
            "  summary_row = len(region_growth_result['output_df']) + 2\n"
            "  add_summary_row('Output', summary_row, region_growth_result['summary'])\n"
            "  plt.figure(figsize=(8, 4))\n"
            "  chart_df = region_growth_result['chart_df']\n"
            "  for region in region_growth_result['region_columns']:\n"
            "      plt.plot(chart_df['Year'], chart_df[region], marker='o', label=region)\n"
            "  plt.xlabel('Year')\n"
            "  plt.ylabel('Penetration Rate')\n"
            "  plt.legend()\n"
            "  save_plot_to_excel('Output', 'F2')\n"
            "  saved_file = save_workbook_to(output_path)\n"
            "  print(f'SAVED_FILE: {saved_file}')\n"
            "  saved_file\n"
            "  ```\n"
            "- If 2020 is unavailable, shrink the helper window to the available requested years and state that adjustment in the summary/output.\n"
        )
    if helper.name == "compute_feature_correlations":
        return (
            f"\n{label} LOOP BREAKER:\n"
            "- Use this grounded workflow shape for one-target feature correlations:\n"
            "  `tables = load_all_tables()`\n"
            "  `df = tables[0]['df'].copy()`\n"
            "  Set `target_col` from the runtime plan summary above.\n"
            "  Set `feature_cols` from the runtime plan summary above.\n"
            "  `correlation_result = compute_feature_correlations(df, target_col=target_col, feature_cols=feature_cols, round_digits=3)`\n"
            "  `create_output_sheet('Output')`\n"
            "  `write_dataframe_to_sheet(correlation_result['output_df'], 'Output', 'A1')`\n"
            "  `saved_file = save_workbook_to(output_path)`\n"
            "  `print(f'SAVED_FILE: {saved_file}')`\n"
            "  `saved_file`\n"
            "- Keep the output as one row whose selected feature columns appear once in order.\n"
            "- Do not switch to a square matrix unless the user explicitly asks for a correlation matrix.\n"
        )
    lines = [
        f"\n{label} LOOP BREAKER:",
        "- Use exactly this workflow shape:",
        "  `tables = load_all_tables()` or grounded `read_table_multi(...)`",
        "  `# compose transformation steps with shared helpers / pandas`",
        "  `create_output_sheet('Output')`",
        "  `write_dataframe_to_sheet(result_df_or_rows, 'Output', 'A1')`",
        "  `saved_file = save_workbook_to(output_path)`",
        "  `print(f'SAVED_FILE: {saved_file}')`",
        "  `saved_file`",
        "- Do not collapse the whole task into a single task-shaped helper call.",
    ]
    return "\n".join(lines) + "\n"



def build_fallback_strategy(question: str) -> str:
    """Return a compact, signal-aware strategy for questions that matched no skill.

    Always includes baseline schema-grounding rules; adds temporal / multi-file /
    numeric guidance when the question signals suggest it.  Kept short (~100 tokens)
    so it does not crowd out the execution rules in the prompt.
    """
    q = question.lower()

    multi_file = any(w in q for w in (
        "multiple files", "two files", "both files", "from files",
        "across files", "all files", "each file", "another file",
        "second file", "other file",
    ))
    temporal = any(w in q for w in (
        "monthly", "yearly", "quarterly", "by month", "by year",
        "per year", "per month", "date", "period", "over time",
        "annually", "semester", "week",
        "last year", "last month", "last quarter", "past year",
        "this year", "this month", "year to date",
    ))
    numeric = any(w in q for w in (
        "calculate", "compute", "average", "total", "sum", "count",
        "percent", "percentage", "ratio", "rate", "growth",
    ))
    ranking = any(w in q for w in (
        "top ", "top-", "bottom ", "highest", "lowest", "best", "worst",
        "rank", "ranking", "most ", "least ", "largest", "smallest",
    ))
    filtering = any(w in q for w in (
        "filter", "where ", "condition", "above ", "below ", "threshold",
        "greater than", "less than", "at least", "at most",
        "only rows", "only show", "exclude", "include only",
    ))
    comparison = any(w in q for w in (
        "compare", "versus", " vs ", "vs.", "difference between",
        "gap between", "change between", "contrast",
    ))

    lines = [
        "[GENERAL GUIDANCE]",
        "Schema grounding before any computation:",
        "  tables = load_all_tables()  # prints basenames, sheets, columns, row count",
        "  # verify df.columns.tolist() before any select/merge/compute",
    ]

    if multi_file:
        lines += [
            "",
            "Multi-file rules:",
            "  - Classify tables by observed headers, NOT by filename or file order.",
            "  - Print both column lists before any join.",
            "  - Different schemas between files are expected and NOT an error.",
        ]

    if temporal:
        lines += [
            "",
            "Temporal rules:",
            "  df['col'] = pd.to_datetime(df['col'], errors='coerce')",
            "  - Never hardcode year values; use .dt.year / .dt.month.",
        ]

    if numeric:
        lines += [
            "",
            "Numeric rules:",
            "  pd.to_numeric(df['col'], errors='coerce')  # before aggregation",
            "  - Handle NaN explicitly (fillna or dropna) before computing.",
        ]

    if ranking:
        lines += [
            "",
            "Ranking rules:",
            "  df.nlargest(N, 'col')  # top N by column",
            "  df.sort_values('col', ascending=False).head(N)  # with full control",
            "  - Verify column name before sorting.",
        ]

    if filtering:
        lines += [
            "",
            "Filtering rules:",
            "  df[df['col'] > threshold]  # numeric condition",
            "  df[df['col'].str.contains('pattern', na=False)]  # string condition",
            "  - Always verify column dtype before filtering.",
        ]

    if comparison:
        lines += [
            "",
            "Comparison rules:",
            "  - Compute delta: df['diff'] = df['col_a'] - df['col_b']",
            "  - Group-level compare: df.groupby('group')['val'].mean().reset_index()",
            "  - Pivot if needed: df.pivot_table(index='row', columns='group', values='val')",
        ]

    lines += [
        "",
        "Output (mandatory):",
        "  create_output_sheet('Output')",
        "  write_dataframe_to_sheet(result_df, 'Output', 'A1')",
        "  saved_file = save_workbook_to(output_path)",
        "  print('SAVED_FILE:', saved_file)",
        "  saved_file",
    ]

    return "\n".join(lines)
