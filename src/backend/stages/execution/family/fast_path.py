"""Deterministic family fast-path execution helpers."""

from typing import TYPE_CHECKING, Any, Dict, Optional

from ....log.logger_registry import LoggerRegistry
from ....task_skills import (
    detect_skill, select_helper,
    get_helper_runtime_mode,
    helper_uses_post_table_summary_row,
)

if TYPE_CHECKING:
    from ..runtime import ExecutionRuntime


logger = LoggerRegistry.setup_logger(__name__)


class ExecutionFamilyFastPathRunner:
    """Own deterministic family execution and text-preview rendering."""

    def __init__(self, runtime: "ExecutionRuntime"):
        self.runtime = runtime

    def _text_output_mode_enabled(self) -> bool:
        preferences = getattr(self.runtime.sandbox, "output_preferences", {}) or {}
        return str(preferences.get("mode", "file")).strip().lower() == "text"

    @staticmethod
    def _compact_preview_cell(value: Any) -> str:
        if value in (None, ""):
            return ""
        return " ".join(str(value).strip().split())

    @classmethod
    def _render_tabular_preview(
        cls,
        rows: list[list[Any]],
        *,
        max_rows: int = 20,
        max_cols: int = 8,
    ) -> tuple[str, bool, int, int]:
        non_empty_rows = [row for row in rows if any(cell not in (None, "") for cell in row)]
        if not non_empty_rows:
            return "", False, 0, 0

        body_rows = non_empty_rows[1:]
        truncated = len(body_rows) > max_rows
        preview_body = body_rows[:max_rows]

        def _effective_width(row: list[Any]) -> int:
            width = 0
            for idx, cell in enumerate(row, start=1):
                if cell not in (None, ""):
                    width = idx
            return width

        observed_rows = [non_empty_rows[0]] + preview_body
        effective_width = max((_effective_width(row) for row in observed_rows), default=0)
        visible_cols = min(max(effective_width, 1), max_cols)
        col_truncated = effective_width > max_cols

        header = [cls._compact_preview_cell(cell) for cell in non_empty_rows[0][:visible_cols]]
        lines = [" | ".join(header + (["..."] if col_truncated else []))]
        for row in preview_body:
            compact_row = [cls._compact_preview_cell(cell) for cell in row[:visible_cols]]
            if col_truncated:
                compact_row.append("...")
            lines.append(" | ".join(compact_row))

        return "\n".join(lines), truncated or col_truncated, len(preview_body), len(body_rows)

    @classmethod
    def _build_text_preview_payload(
        cls,
        rows: list[list[Any]],
        *,
        sheet_name: str = "Output",
        extra_sheet_names: Optional[list[str]] = None,
        file_mode_hint: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        preview_text, truncated, preview_rows, total_rows = cls._render_tabular_preview(rows)
        if not preview_text:
            return None

        note_parts: list[str] = []
        if truncated:
            note_parts.append(
                "Preview truncated to the first 20 rows and 8 columns where needed. "
                "Please enable file mode for the full output."
            )
        if extra_sheet_names:
            note_parts.append(
                "Additional sheets available in file mode: " + ", ".join(extra_sheet_names) + "."
            )
        if file_mode_hint:
            note_parts.append(file_mode_hint)

        note = f"\n\n{' '.join(note_parts)}" if note_parts else ""
        normalized_rows = [row for row in rows if any(cell not in (None, "") for cell in row)]
        headers = [
            cls._compact_preview_cell(cell)
            for cell in (normalized_rows[0] if normalized_rows else [])
            if cls._compact_preview_cell(cell)
        ]
        return {
            "rendered_text": f"Text preview of generated output ({sheet_name or 'Output'}):\n{preview_text}{note}",
            "truncated": truncated,
            "preview_rows": preview_rows,
            "total_rows": total_rows,
            "headers": headers,
            "sheet_name": sheet_name or "Output",
            "extra_sheet_names": extra_sheet_names or [],
        }

    def execute(self, helper_name_param: str, runtime_mode: str, user_question: str) -> Optional[dict]:
        runtime = self.runtime
        globals_dict = getattr(runtime.sandbox, "code_globals", {}) or {}
        infer = runtime.question_inference
        observed_headers = sorted(runtime._observed_header_set())
        create_output_sheet = globals_dict.get("create_output_sheet")
        write_dataframe_to_sheet = globals_dict.get("write_dataframe_to_sheet")
        save_workbook_to = globals_dict.get("save_workbook_to")
        add_summary_row = globals_dict.get("add_summary_row")
        output_path = globals_dict.get("output_path")
        if runtime_mode == "text_scan":
            create_output_sheet = None
            write_dataframe_to_sheet = None
            save_workbook_to = None
        elif not all((create_output_sheet, write_dataframe_to_sheet, save_workbook_to, output_path)):
            return None

        helper_messages: list[str] = []
        report = None
        helper_name = ""
        output_sheet_name = "Output"
        extra_sheet_payloads: list[tuple[str, Any]] = []
        if runtime_mode == "grouped_aggregation":
            helper = globals_dict.get("build_grouped_aggregation_ranking_report")
            if helper is None:
                return None
            group_cols = infer.infer_group_headers_from_question(observed_headers, user_question) or None
            value_col = infer.infer_value_header_from_question(
                observed_headers,
                user_question,
                helper_name_param,
            )
            report = helper(
                file_path=None,
                group_cols=group_cols,
                value_col=value_col,
                aggregate=infer.infer_aggregate_from_question(user_question),
                top_n=infer.infer_top_n_from_question(user_question),
                sort_desc=infer.infer_sort_desc_from_question(user_question),
            )
            helper_name = "build_grouped_aggregation_ranking_report"
        elif runtime_mode == "temporal_aggregation":
            helper = globals_dict.get("build_time_series_aggregation_report")
            if helper is None:
                return None
            period = infer.infer_period_from_question(user_question)
            report = helper(
                file_path=None,
                date_col=infer.infer_date_header_from_question(observed_headers, user_question) or "Date",
                value_col=infer.infer_value_header_from_question(
                    observed_headers,
                    user_question,
                    helper_name_param,
                ),
                period=period,
                aggregate=infer.infer_aggregate_from_question(user_question),
                window_years=infer.infer_window_years_from_question(user_question),
                period_mode=infer.infer_period_mode_from_question(user_question, period),
                sort_desc=infer.infer_sort_desc_from_question(user_question),
            )
            helper_name = "build_time_series_aggregation_report"
        elif runtime_mode == "reference_completion":
            load_all_tables = globals_dict.get("load_all_tables")
            infer_common_key = globals_dict.get("infer_common_key")
            fill_missing_from_reference = globals_dict.get("fill_missing_from_reference")
            if not all((load_all_tables, infer_common_key, fill_missing_from_reference)):
                return None
            tables = load_all_tables(require_primary_key=False)
            if len(tables) < 2:
                raise ValueError("Reference-guided completion requires at least two tables.")
            key_header = infer_common_key(tables)
            report = fill_missing_from_reference(
                tables[0]["df"],
                tables[1]["df"],
                key_header=key_header,
                prefer_primary=True,
            )
            helper_name = "fill_missing_from_reference"
        elif runtime_mode == "schema_merge_summary":
            load_all_tables = globals_dict.get("load_all_tables")
            concat_tables = globals_dict.get("concat_tables_with_same_headers")
            summarize_numeric_column = globals_dict.get("summarize_numeric_column")
            highlight_rows_fn = globals_dict.get("highlight_rows")
            if not all((load_all_tables, concat_tables, summarize_numeric_column, add_summary_row)):
                return None
            tables = load_all_tables()
            concat_result = concat_tables(tables)
            combined_df = concat_result["output_df"]
            grounded_value_col = infer.infer_value_header_from_question(
                observed_headers,
                user_question,
                helper_name_param,
            )
            summary_result = summarize_numeric_column(combined_df, grounded_value_col or "...")
            report = {
                "detail_data": concat_result["detail_data"],
                "highlight_rows": summary_result.get("output_row_numbers", []),
                "summary": summary_result.get("summary", {}),
            }
            helper_name = "concat_tables_with_same_headers + summarize_numeric_column"
        elif runtime_mode == "composite_relational_join":
            helper = globals_dict.get("build_multi_key_relational_join_report")
            if helper is None:
                return None
            mentioned = infer.headers_mentioned_in_question(observed_headers, user_question)
            key_headers = []
            seen = set()
            for header in mentioned:
                normalized = infer.normalize_header_name_for_grounding(header)
                if any(
                    marker in normalized
                    for marker in ("id", "code", "number", "term", "semester", "date", "year", "month", "section", "class", "group", "session", "slot", "room", "course")
                ) and normalized not in seen:
                    seen.add(normalized)
                    key_headers.append(header)
            report = helper(
                range_ref="A1:Z200000",
                key_headers=key_headers[:2] if len(key_headers) >= 2 else None,
                how="inner",
            )
            helper_name = "build_multi_key_relational_join_report"
        elif runtime_mode == "relational_join":
            helper = globals_dict.get("build_relational_join_enrichment_report")
            if helper is None:
                return None
            key_header = None
            mentioned = infer.headers_mentioned_in_question(observed_headers, user_question)
            for header in mentioned:
                normalized = infer.normalize_header_name_for_grounding(header)
                if any(marker in normalized for marker in ("id", "code", "number")):
                    key_header = header
                    break
            report = helper(range_ref="A1:Z200000", key_header=key_header, how="inner")
            helper_name = "build_relational_join_enrichment_report"
        elif runtime_mode == "regression":
            load_all_tables = globals_dict.get("load_all_tables")
            helper = globals_dict.get("fit_linear_regression_weights")
            if not all((load_all_tables, helper)):
                return None
            tables = load_all_tables()
            if not tables:
                return None
            df = tables[0]["df"]
            target_col, feature_cols = infer.infer_regression_columns_from_df(df, user_question)
            if not target_col or not feature_cols:
                return None
            report = helper(df, target_col=target_col, feature_cols=feature_cols)
            helper_name = "fit_linear_regression_weights"
        elif runtime_mode == "correlation":
            load_all_tables = globals_dict.get("load_all_tables")
            helper = globals_dict.get("build_correlation_matrix_table")
            if not all((load_all_tables, helper)):
                return None
            tables = load_all_tables()
            if not tables:
                return None
            df = tables[0]["df"]
            numeric_columns, filter_column, filter_value = infer.infer_correlation_columns_from_df(df, user_question)
            if len(numeric_columns) < 2:
                return None
            report = helper(
                df,
                numeric_columns=numeric_columns,
                filter_column=filter_column,
                filter_value=filter_value,
            )
            helper_name = "build_correlation_matrix_table"
        elif runtime_mode == "temporal_growth":
            list_all_workbooks = globals_dict.get("list_all_workbooks")
            helper = globals_dict.get("build_region_growth_analysis")
            get_workbook = globals_dict.get("get_workbook")
            save_plot_to_excel = globals_dict.get("save_plot_to_excel")
            highlight_rows_fn = globals_dict.get("highlight_rows")
            plt = globals_dict.get("plt")
            if not all((list_all_workbooks, helper, get_workbook, save_plot_to_excel, add_summary_row, create_output_sheet, write_dataframe_to_sheet)) or plt is None:
                return None
            all_files = list_all_workbooks()
            if not all_files:
                return None
            file_path = all_files[0]
            workbook = get_workbook(file_path)
            sheet_name = "Data" if "Data" in workbook.sheetnames else workbook.sheetnames[0]
            start_year, end_year = infer.infer_explicit_year_bounds_from_question(user_question)
            report = helper(
                file_path,
                sheet_name=sheet_name,
                start_year=start_year,
                end_year=end_year,
            )
            report = dict(report)
            report["highlight_rows"] = report.get("fastest_growth_rows", [])
            helper_name = "build_region_growth_analysis"
            chart_df = report.get("chart_df")
            region_columns = report.get("region_columns") or []
            if chart_df is not None and not chart_df.empty and region_columns:
                plt.figure(figsize=(7, 4))
                for region_name in region_columns:
                    if region_name in chart_df.columns:
                        plt.plot(chart_df["Year"], chart_df[region_name], marker="o", label=region_name)
                plt.xlabel("Year")
                plt.ylabel("Penetration")
                plt.title("Regional Growth")
                plt.legend(loc="best")
                plt.tight_layout()
                helper_messages.append(save_plot_to_excel(output_sheet_name, "F2"))
                plt.close()
        elif runtime_mode == "graph_scan":
            load_all_tables = globals_dict.get("load_all_tables")
            helper = globals_dict.get("build_cycle_detection_report")
            if not all((load_all_tables, helper)):
                return None
            tables = load_all_tables()
            report = helper(tables, from_col="Node From", to_col="Node To")
            helper_name = "build_cycle_detection_report"
        elif runtime_mode == "text_scan" and helper_name_param == "build_missing_data_report":
            helper = globals_dict.get("build_missing_data_report")
            if helper is None:
                return None
            report = helper()
            helper_name = "build_missing_data_report"
        elif runtime_mode == "text_scan" and helper_name_param == "build_room_format_report":
            helper = globals_dict.get("build_room_format_report")
            if helper is None:
                return None
            report = helper()
            helper_name = "build_room_format_report"
        elif runtime_mode == "relational_assignment":
            helper = globals_dict.get("build_relational_assignment_schedule_report")
            if helper is None:
                return None
            report = helper()
            helper_name = "build_relational_assignment_schedule_report"
        elif runtime_mode == "dependency_schedule":
            load_all_tables = globals_dict.get("load_all_tables")
            find_table_by_headers = globals_dict.get("find_table_by_headers")
            helper = globals_dict.get("build_dependency_schedule")
            if not all((load_all_tables, find_table_by_headers, helper, add_summary_row)):
                return None
            tables = load_all_tables()
            task_table = find_table_by_headers(
                tables,
                required_headers=["Task ID"],
                preferred_headers=["Task Name", "Duration (hours)", "Priority"],
                forbidden_headers=["Depends on"],
            )
            dependency_table = find_table_by_headers(
                tables,
                required_headers=["Task ID", "Depends on"],
            )
            report = helper(
                task_table["df"],
                dependency_table["df"],
                start_time="08:00",
            )
            helper_name = "build_dependency_schedule"
        elif runtime_mode == "comparative_multi_sheet":
            helper = globals_dict.get("build_store_feature_analysis_report")
            if helper is None:
                return None
            report = helper()
            helper_name = "build_store_feature_analysis_report"
            extra_sheet_payloads = [
                ("AvgByStoreType", report.get("avg_by_type_detail_data")),
                ("HolidayVsNonHoliday", report.get("holiday_detail_data")),
            ]
        elif runtime_mode == "zero_arg_helper":
            helper_fn = globals_dict.get(helper_name_param)
            if helper_fn is None:
                return None
            report = helper_fn()
            helper_name = helper_name_param
        else:
            return None

        if runtime_mode == "text_scan":
            final_text = str((report or {}).get("answer") or "").strip()
            if not final_text:
                return None
            step = {
                "turn": 1,
                "code": f"DETERMINISTIC_FAMILY_FAST_PATH: {helper_name}(...) -> FINAL_TEXT",
                "result": f"FINAL_TEXT: {final_text}",
                "success": True,
            }
            return {
                "success": True,
                "answer": final_text,
                "total_turns": 1,
                "conversation_history": runtime.history_formatter.format_history(runtime.conversation_history),
                "execution_summary": runtime.summary_builder.build([step], final_text),
                "_family_fast_path": helper_name_param,
            }

        if not isinstance(report, dict) or "detail_data" not in report:
            if runtime_mode != "comparative_multi_sheet":
                return None

        if self._text_output_mode_enabled():
            preview_payload: Optional[Dict[str, Any]]
            if runtime_mode == "comparative_multi_sheet":
                primary_sheet_name = extra_sheet_payloads[0][0] if extra_sheet_payloads else output_sheet_name
                primary_rows = extra_sheet_payloads[0][1] if extra_sheet_payloads else report.get("detail_data")
                preview_payload = self._build_text_preview_payload(
                    primary_rows or [],
                    sheet_name=primary_sheet_name,
                    extra_sheet_names=[name for name, _payload in extra_sheet_payloads[1:]],
                )
            else:
                preview_payload = self._build_text_preview_payload(
                    report["detail_data"],
                    sheet_name=output_sheet_name,
                    file_mode_hint=(
                        "Chart embedding is only available in file mode."
                        if runtime_mode == "temporal_growth"
                        else None
                    ),
                )
            if preview_payload is None:
                return None

            final_text = str(preview_payload["rendered_text"])
            metadata = report.get("metadata") if isinstance(report, dict) else None
            result_text = f"FINAL_TEXT: {final_text}"
            if isinstance(metadata, dict) and metadata:
                result_text += f"\nFAMILY_METADATA: {metadata}"
            step = {
                "turn": 1,
                "code": f"DETERMINISTIC_FAMILY_FAST_PATH: {helper_name}(...) -> FINAL_TEXT_PREVIEW",
                "result": result_text,
                "success": True,
            }
            return {
                "success": True,
                "answer": final_text,
                "total_turns": 1,
                "conversation_history": runtime.history_formatter.format_history(runtime.conversation_history),
                "execution_summary": runtime.summary_builder.build([step], final_text),
                "_family_fast_path": helper_name_param,
                "_text_preview_only": True,
                "_text_preview_truncated": bool(preview_payload["truncated"]),
                "_text_preview_rows": preview_payload["preview_rows"],
                "_text_total_rows": preview_payload["total_rows"],
                "_text_preview_headers": preview_payload["headers"],
                "_text_preview_sheet_name": preview_payload["sheet_name"],
                "_text_preview_extra_sheet_names": preview_payload["extra_sheet_names"],
            }

        if runtime_mode == "comparative_multi_sheet":
            for sheet_name, sheet_payload in extra_sheet_payloads:
                if not sheet_payload:
                    return None
                helper_messages.append(create_output_sheet(sheet_name))
                helper_messages.append(write_dataframe_to_sheet(sheet_payload, sheet_name, "A1"))
        else:
            helper_messages.append(create_output_sheet(output_sheet_name))
            helper_messages.append(write_dataframe_to_sheet(report["detail_data"], output_sheet_name, "A1"))
        highlight_rows_payload = report.get("highlight_rows") or []
        if highlight_rows_payload and "highlight_rows_fn" in locals() and highlight_rows_fn is not None:
            helper_messages.append(highlight_rows_fn(output_sheet_name, highlight_rows_payload, {"fill_color": "red"}))
        elif helper_name_param == "concat_tables_with_same_headers":
            helper_messages.append("NO_HIGHLIGHT_ROWS: []")
        if helper_uses_post_table_summary_row(helper_name_param):
            summary_payload = report.get("summary") or {}
            if summary_payload:
                helper_messages.append(add_summary_row(output_sheet_name, len(report["detail_data"]) + 2, summary_payload))
        saved_file = save_workbook_to(output_path)
        helper_messages.append(f"SAVED_FILE: {saved_file}")

        result_text = "\n".join(str(message) for message in helper_messages if message)
        metadata = report.get("metadata") if isinstance(report, dict) else None
        if isinstance(metadata, dict) and metadata:
            result_text += f"\nFAMILY_METADATA: {metadata}"

        step = {
            "turn": 1,
            "code": (
                f"DETERMINISTIC_FAMILY_FAST_PATH: {helper_name}(...) -> "
                "create_output_sheet('Output') -> write_dataframe_to_sheet(...) -> save_workbook_to(output_path)"
            ),
            "result": result_text,
            "success": True,
        }
        return {
            "success": True,
            "answer": saved_file,
            "total_turns": 1,
            "conversation_history": runtime.history_formatter.format_history(runtime.conversation_history),
            "execution_summary": runtime.summary_builder.build([step], saved_file),
            "_family_fast_path": helper_name_param,
        }

    def try_run(self, user_question: str) -> Optional[dict]:
        skill = detect_skill(user_question)
        if skill is None:
            return None
        helper = select_helper(skill, user_question)
        if helper is None:
            return None
        runtime_mode = get_helper_runtime_mode(helper.name)
        if runtime_mode is None:
            return None
        try:
            return self.execute(helper.name, runtime_mode, user_question)
        except Exception as exc:
            self.runtime._log_to_file(
                f"\n**Deterministic skill fast-path skipped:**\n{helper.name}: {exc}\n"
            )
            logger.info("Deterministic skill fast-path failed for %s: %s", helper.name, exc)
            return None
