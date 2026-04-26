"""Strategy documents injected into LLM prompts per skill.

Each constant is a concise, structured guide telling the LLM *how* to approach
a class of problems — which helpers to use, in what order, and what to watch
out for. Kept as plain strings so they can be edited without touching logic.
"""

MERGE_STRATEGY = """\
[SKILL: CROSS-TABLE] Load and combine data from multiple files or sheets.

Same-schema vertical stack:
  tables = load_all_tables()
  concat_result = concat_tables_with_same_headers(tables)
  combined_df = concat_result["output_df"]
  print(combined_df.columns.tolist(), len(combined_df))
  # -> pass combined_df to aggregate/highlight steps as needed

Horizontal join on shared key:
  tables = load_all_tables()
  key = infer_common_key(tables)
  result = fill_missing_from_reference(tables[0]["df"], tables[1]["df"], key_header=key, prefer_primary=True)
  # -> write result["detail_data"]

Enrichment join (one main table + one reference):
  tables = load_all_tables()
  result = build_relational_join_enrichment_report(key_header="...", how="inner")
  # -> write result["detail_data"]

Rules:
  - Always print columns + shape before any select/merge.
  - Classify tables by observed headers, not file order or filename.
  - Write DataFrames directly; do not hand-build data_2d.
  - This skill only covers loading and joining. Aggregate/highlight steps are separate.\
"""

HIGHLIGHT_STRATEGY = """\
[SKILL: HIGHLIGHT] Mark rows in the Output sheet by color.

Using row numbers from a summary helper (preferred):
  summary_result = summarize_numeric_column(df, value_col="...")
  row_numbers = summary_result["output_row_numbers"]   # already 1-based, header-offset included
  highlight_rows("Output", row_numbers, {"fill_color": "red"})

Computing row numbers manually:
  # 1-based row in the Output sheet = DataFrame position (0-based) + 2 (1 for 1-based, 1 for header)
  max_val = df["col"].max()
  row_numbers = [i + 2 for i, v in enumerate(df["col"]) if v == max_val]
  highlight_rows("Output", row_numbers, {"fill_color": "red"})

Rules:
  - Always call write_dataframe_to_sheet before highlight_rows.
  - highlight_rows expects a plain list of 1-based integers.
  - Do not reassign the name `highlight_rows` to a variable in your code.
  - Prefer summary_result["output_row_numbers"] over manual enumeration when available.
  - The DataFrame passed to write_dataframe_to_sheet and to summarize_numeric_column
    must have a reset (0-based) index, or row numbers will be wrong.\
"""

AGGREGATE_STRATEGY = """\
[SKILL: AGGREGATE] Compute summary metrics, rankings, or time-period breakdowns.

Numeric column summary (total / average / max on a verified table):
  tables = load_all_tables()
  df = tables[0]["df"]
  print(df.columns.tolist(), len(df))
  result = summarize_numeric_column(df, value_col="...")
  total_value = result["total"]
  average_value = result["average"]
  -> use result["summary"] for add_summary_row(); result["output_row_numbers"] for highlight_rows()

Grouped summary:
  tables = load_all_tables()
  df = tables[0]["df"]
  result = build_group_summary(df, group_cols=["..."], aggregations={"col": "sum", ...})
  -> write result["detail_data"]

Period-block table with messy headers:
  all_files = list_all_workbooks()
  table = read_table_multi(all_files[0], get_workbook(all_files[0]).sheetnames[0], "A1:Z300")
  raw_rows = [table["header"]] + table["rows"]
  period_cell = find_first_period_cell(raw_rows, match_regex=r"^\\d{4}$")
  header_row = raw_rows[period_cell[0] - 1]
  value_columns = select_contiguous_labeled_columns(header_row, start_col_idx=period_cell[1] + 1, stop_markers=("In %",))
  records = extract_period_records(
      raw_rows[period_cell[0]:],
      period_col_idx=period_cell[1],
      labeled_columns=value_columns,
      match_regex=r"^\\d{4}$",
      cast_period="int",
      period_key="Year",
  )
  df = pd.DataFrame(records)
  # then filter the requested years, compute growth/averages, and write Output

Rules:
  - Pick one verified table shape, then compose the calculation from shared helpers / pandas.
  - Parse dates with pd.to_datetime(..., errors="coerce"). Never hard-code year values.
  - Prefer period extraction helpers for messy multi-row headers instead of rebuilding schema by guesswork.
  - Optional finishing step: add_rank_column(df, sort_col="value_col") to append a rank column.\
"""

STATISTICAL_STRATEGY = """\
[SKILL: STATISTICAL] Regression, correlation, or graph-cycle analysis.

Linear regression weights:
  result = fit_linear_regression_weights(df, target_col="...", feature_cols=[...])
  print("USED_FEATURES:", result["used_features"])
  -> write result["detail_data"]
  Include all numeric predictors; map binary categoricals (yes/no) to 1/0.

Correlation matrix:
  result = build_correlation_matrix_table(df, numeric_columns=[...])
  -> write result["detail_data"]

Target-vs-feature correlations:
  result = compute_feature_correlations(df, target_col="...", feature_cols=[...])
  -> write result["detail_data"]

Cycle detection:
  result = build_cycle_detection_report(df, from_col="...", to_col="...")
  -> write result["detail_data"]\
"""

SCHEDULE_STRATEGY = """\
[SKILL: SCHEDULE] Dependency-ordered scheduling, capacity allocation, or assignment.

Dependency scheduling:
  tables = load_all_tables()
  task_t  = find_table_by_headers(tables, required_headers=["Task ID"], forbidden_headers=["Depends on"])
  dep_t   = find_table_by_headers(tables, required_headers=["Task ID", "Depends on"])
  result  = build_dependency_schedule(task_t["df"], dep_t["df"], start_time="08:00")
  print("TASK_ID_SET:", ..., "SCHEDULED_TASK_IDS:", ...)  # assert equality before save
  -> write result["detail_data"] and result["summary"]

Relational assignment schedule:
  tables = load_all_tables()
  assignment_t = find_table_by_headers(
      tables,
      required_headers=["Assigned Tutor"],
      preferred_headers=["Student", "Student Name"],
  )
  schedule_t = find_table_by_headers(
      tables,
      required_headers=["Tutor Name", "Time Slot", "Room"],
  )
  output_df = build_grouped_assignment_join(
      assignment_df=assignment_t["df"],
      assignment_col="Assigned Tutor",
      entity_col="Student",
      schedule_df=schedule_t["df"],
      resource_col="Tutor Name",
      schedule_cols=["Time Slot", "Room"],
  )
  -> write output_df to Output

Capacity allocation:
  tables = load_all_tables()
  # inspect the real headers first, then either compose with pandas or call a generic allocation helper when appropriate

Rules: Identify table roles from observed headers, not filenames or file order.
  Different schemas between task/dependency tables are expected.\
"""

SCAN_STRATEGY = """\
[SKILL: SCAN] Audit data quality or identifier format consistency. Output is TEXT, not a workbook.

Missing-data scan:
  report = build_missing_data_report()
  -> return report["answer"] as the final text answer. Do NOT save a workbook.

Identifier format scan:
  report = build_room_format_report()
  -> return report["answer"] as the final text answer. Do NOT save a workbook.

Rules: Never call save_workbook_to() for scan tasks. Print the answer text directly.\
"""

RANK_STRATEGY = """\
[SKILL: RANK] Score and rank entities by weighted multi-criteria.

Weighted composite score:
  tables = load_all_tables()
  df = concat_tables_with_same_headers(tables)["output_df"]  # multi-file
  # or: df = tables[0]["df"]  # single file
  print(df.columns.tolist())  # verify score column names
  df = compute_weighted_score(df,
      score_cols=["col_a", "col_b", "col_c"],  # infer from actual headers
      weights=[0.5, 0.3, 0.2],                 # equal weights if unspecified
      output_col="score")
  df = add_rank_column(df, sort_col="score")
  -> write df[["name_col", "rank", "score", ...]] to Output

Single-criterion top-N:
  output_df = df.nlargest(N, "sort_col")
  output_df = add_rank_column(output_df, sort_col="sort_col")
  -> write output_df to Output

Rules:
  - Always print df.columns before selecting score_cols.
  - Drop rows where name/key column is blank before scoring.
  - Weights are auto-normalized to sum to 1.\
"""

FINANCIAL_STRATEGY = """\
[SKILL: FINANCIAL] Ratio computation and year-over-year comparisons.

Efficiency ratio per row:
  tables = load_all_tables()
  df = tables[0]["df"]
  print(df.columns.tolist())  # verify numerator/denominator column names
  df = compute_ratio_column(df,
      numerator_col="Operating Cash Flow",   # use real header
      denominator_col="Net Income",
      output_col="OCF/NI Ratio")
  -> write df to Output

Year-over-year percentage change:
  df = df.sort_values("Year")
  df["YoY Change %"] = df["value_col"].pct_change().mul(100).round(2)
  -> write df to Output

Rules:
  - Verify numerator_col and denominator_col exist in df.columns before calling.
  - Helper produces NaN on division-by-zero, never crashes.
  - Cast to numeric first: pd.to_numeric(df["col"], errors="coerce").\
"""

PROPORTION_STRATEGY = """\
[SKILL: PROPORTION] Compute percentage share or distribution breakdown.

Share of overall total:
  tables = load_all_tables()
  df = tables[0]["df"]
  print(df.columns.tolist())
  df = compute_percentage_share(df, value_col="sales", output_col="share_pct")
  -> write df to Output

Share within group:
  df = compute_percentage_share(df,
      value_col="sales",
      output_col="share_pct",
      group_col="region")        # each row shows % within its group
  -> write df to Output

Market-share plus total-shipment composition:
  # Parse the market-share period table and the shipment period table separately
  market_share_records = extract_period_records(...)
  shipment_records = extract_period_records(...)
  overlap_df = merge_on_shared_period(market_share_records, shipment_records, period_col="Time")
  output_df = build_weighted_period_output(
      overlap_df,
      period_col="Time",
      value_columns=["Brand A", "Brand B", "..."],
      weight_col="Shipment",
      output_period_col="Year",
      output_label_template="{name} (Unit shipment)",
  )
  -> write output_df to Output

Rules:
  - Helper coerces value_col to numeric and rounds share_pct to 2 dp automatically.
  - If question says "% of total by X", set group_col="X".
  - For two-table period problems, join on the verified shared period instead of assuming aligned row order.\
"""
