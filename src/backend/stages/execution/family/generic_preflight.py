"""Generic execution preflight checks shared across task families."""

import ast
import re
from typing import TYPE_CHECKING, Optional

from ....task_skills import detect_skill, select_helper, build_loop_breaker, build_execution_strict_rules, get_helper_runtime_mode

if TYPE_CHECKING:
    from ..runtime import ExecutionRuntime


class ExecutionGenericPreflightAdvisor:
    """Own generic bounded-mode preflight checks and header grounding."""

    def __init__(self, runtime: "ExecutionRuntime"):
        self.runtime = runtime

    def offline_preflight_check(self, code_action: str, user_question: str) -> Optional[str]:
        code = (code_action or "").strip()
        if not code:
            return "PREFLIGHT_LINEAR: empty code block."
        lower = code.lower()
        skill = detect_skill(user_question)
        helper = select_helper(skill, user_question) if skill else None
        helper_name = helper.name if helper else ""
        uses_registered_helper = bool(helper_name and f"{helper_name.lower()}(" in lower)
        uses_load_all_tables = "load_all_tables(" in lower
        # Check for any known helper function call in the code
        _ALL_KNOWN_HELPERS = (
            "build_region_growth_analysis", "build_financial_dashboard_report",
            "build_candidate_screening_report", "build_inventory_eoq_report",
            "build_hospital_utilisation_report", "build_market_share_shipment_report",
            "build_cash_flow_efficiency_report", "build_diabetes_region_report",
            "build_mobile_reviews_summary_report", "build_store_feature_analysis_report",
            "build_ecommerce_merge_report", "build_missing_data_report",
            "build_room_format_report", "build_relational_assignment_schedule_report",
            "build_dependency_schedule", "build_correlation_matrix_table",
            "build_cycle_detection_report", "build_grouped_aggregation_ranking_report",
            "build_time_series_aggregation_report", "build_multi_key_relational_join_report",
            "build_relational_join_enrichment_report", "build_capacity_constrained_allocation_report",
            "fit_linear_regression_weights", "concat_tables_with_same_headers",
            "fill_missing_from_reference",
        )
        uses_any_known_helper = any(f"{h}(" in lower for h in _ALL_KNOWN_HELPERS)

        top_level_returns = [
            line.strip()
            for line in code.splitlines()
            if line.strip().startswith("return ")
        ]
        if top_level_returns:
            return (
                "PREFLIGHT_LINEAR: top-level `return` is invalid in execution code.\n"
                "- Do not use `return saved_file`.\n"
                "- End with:\n"
                "  `saved_file = save_workbook_to(output_path)`\n"
                "  `print(f'SAVED_FILE: {saved_file}')`\n"
                "  `saved_file`"
            )

        try:
            ast.parse(code)
        except SyntaxError as exc:
            line_info = f" on line {exc.lineno}" if exc.lineno else ""
            return (
                f"PREFLIGHT_LINEAR: generated code has a syntax error{line_info}.\n"
                f"- Parser message: {exc.msg}\n"
                "- Return one full corrected code block.\n"
                "- Keep string quoting simple and avoid nested double quotes inside f-strings."
            )

        if skill is not None and helper_name and not uses_registered_helper:
            skill_hint = (build_loop_breaker(skill, helper) or build_execution_strict_rules(skill, helper) or "").strip()
            helper_block = (
                f"PREFLIGHT_SKILL_HELPER: detected the `{skill.name}` skill, so execution must call the runtime helper `{helper_name}(...)`.\n"
                f"- Required helper: `{helper_name}(...)`\n"
                "- Do not replace the helper with ad-hoc pandas logic, manual joins, or manual date parsing.\n"
            )
            if skill_hint:
                helper_block += f"{skill_hint}\n"
            return helper_block.rstrip()

        if helper is not None and helper.self_loading and uses_registered_helper:
            manual_reader_patterns = ("read_table_multi(", "find_table_by_headers(", "load_all_tables(")
            if any(pattern in lower for pattern in manual_reader_patterns):
                skill_hint = (build_loop_breaker(skill, helper) or build_execution_strict_rules(skill, helper) or "").strip()
                helper_block = (
                    f"PREFLIGHT_SELF_LOADING_HELPER: `{helper_name}(...)` already loads and prepares the source tables for the `{skill.name}` skill.\n"
                    "- Remove manual `read_table_multi(...)`, `find_table_by_headers(...)`, and `load_all_tables(...)` calls from execution code.\n"
                    "- Call the helper directly, write its returned detail data, then save.\n"
                )
                if skill_hint:
                    helper_block += f"{skill_hint}\n"
                return helper_block.rstrip()

        family_grounding_issue = self.family_helper_header_grounding_guard(code_action, user_question)
        if family_grounding_issue is not None:
            return family_grounding_issue

        if "list_all_workbooks(" not in lower and not uses_load_all_tables and not uses_registered_helper and not uses_any_known_helper:
            return (
                "PREFLIGHT_LINEAR: code must read runtime inputs via `load_all_tables()` or `list_all_workbooks()`.\n"
                "- Preferred: `tables = load_all_tables()`\n"
                "- Or add: `all_files = list_all_workbooks()` and resolve file_path from runtime."
            )

        requires_saved_workbook = not (
            (skill is not None and skill.output_mode == "text")
        )
        if requires_saved_workbook and not re.search(r"save_workbook_to\s*\(\s*output_path\s*\)", code, flags=re.IGNORECASE):
            return (
                "PREFLIGHT_LINEAR: code must save with save_workbook_to(output_path).\n"
                "- End with:\n"
                "  saved_file = save_workbook_to(output_path)\n"
                "  print(\"SAVED_FILE:\", saved_file)\n"
                "  saved_file"
            )

        if re.search(r"^\s*from\s+(runtime|runtime_path|graph_helper|excel_output|workbook_helper)\s+import\s+", code, flags=re.IGNORECASE | re.MULTILINE):
            return (
                "PREFLIGHT_LINEAR: do not import runtime helper modules.\n"
                "- Helper functions are already injected into the sandbox globals.\n"
                "- Call them directly: `load_all_tables()`, `build_cycle_detection_report(...)`, "
                "`create_output_sheet(...)`, `write_dataframe_to_sheet(...)`, `save_workbook_to(output_path)`.\n"
                "- Remove all `from runtime...`, `from graph_helper...`, `from excel_output...`, and `from workbook_helper...` imports."
            )

        if re.search(r"^\s*output_path\s*=\s*['\"][^'\"]+['\"]", code, flags=re.IGNORECASE | re.MULTILINE):
            return (
                "PREFLIGHT_LINEAR: do not assign a literal output path in execution code.\n"
                "- Use the injected runtime variable only: `save_workbook_to(output_path)`.\n"
                "- Do not redefine `output_path`."
            )

        if "read_table_multi(" not in lower and not uses_load_all_tables and not uses_registered_helper and not uses_any_known_helper:
            return (
                "PREFLIGHT_LINEAR: code must read tabular content via `load_all_tables()` or `read_table_multi(...)`.\n"
                "- Preferred: `tables = load_all_tables()`\n"
                "- Manual fallback: `table = read_table_multi(file_path, sheet_name, \"A1:Z200\")`\n"
                "- Then build DataFrame with: `pd.DataFrame(table['rows'], columns=table['header'])`"
            )

        if re.search(r"read_table_multi\s*\([^)]*\)\s*\[\s*['\"]df['\"]\s*\]", code, flags=re.IGNORECASE | re.DOTALL):
            return (
                "PREFLIGHT_LINEAR: read_table_multi() does not return a `df` key.\n"
                "- Use: `table = read_table_multi(file_path, sheet_name, \"A1:Z200\")`\n"
                "- Then build DataFrame explicitly:\n"
                "  `df = pd.DataFrame(table['rows'], columns=table['header'])`"
            )

        uses_rows = re.search(r"\[\s*['\"]rows['\"]\s*\]", code) is not None
        uses_header = re.search(r"\[\s*['\"]header['\"]\s*\]", code) is not None
        if uses_rows and not uses_header:
            return (
                "PREFLIGHT_LINEAR: read_table_multi() output must use both `rows` and `header`.\n"
                "- `table['header']` is the header row.\n"
                "- `table['rows']` already contains data rows only.\n"
                "- Build DataFrame with: `pd.DataFrame(table['rows'], columns=table['header'])`.\n"
                "- Do not hard-code headers or slice `rows[1:]`."
            )

        if re.search(r"\[\s*['\"]rows['\"]\s*\]\s*\[\s*1\s*:\s*\]", code):
            return (
                "PREFLIGHT_LINEAR: `table['rows']` already excludes the header row.\n"
                "- Remove `[1:]` after `table['rows']`.\n"
                "- Use all rows directly when building the DataFrame."
            )

        if re.search(r"\binspector_multi\s*\(", code):
            return (
                "PREFLIGHT_LINEAR: `inspector_multi()` is disabled for execution.\n"
                "- Use cleaned table reader only:\n"
                "  all_files = list_all_workbooks()\n"
                "  for file_path in all_files:\n"
                "      wb = get_workbook(file_path)\n"
                "      sheet_name = wb.sheetnames[0]\n"
                "      table = read_table_multi(file_path, sheet_name, \"A1:Z200\")"
            )

        if re.search(r"\binspector\s*\(", code):
            return (
                "PREFLIGHT_LINEAR: `inspector()` is disabled for execution.\n"
                "- Use a single deterministic read path only:\n"
                "  all_files = list_all_workbooks()\n"
                "  for file_path in all_files:\n"
                "      wb = get_workbook(file_path)\n"
                "      sheet_name = wb.sheetnames[0]\n"
                "      table = read_table_multi(file_path, sheet_name, \"A1:Z200\")"
            )

        return None

    def family_helper_header_grounding_guard(self, code_action: str, user_question: str) -> Optional[str]:
        skill = detect_skill(user_question)
        if skill is None:
            return None
        helper = select_helper(skill, user_question)
        if helper is None:
            return None
        helper_name = helper.name
        lower = (code_action or "").lower()
        if f"{helper_name.lower()}(" not in lower:
            return None

        observed_headers = sorted(self.runtime._observed_header_set())
        if not observed_headers:
            return None

        infer = self.runtime.question_inference
        normalized_headers = {
            infer.normalize_header_name_for_grounding(header): header
            for header in observed_headers
        }

        unknown_args: list[tuple[str, str]] = []
        for kwarg in ("date_col", "value_col", "target_col", "key_header"):
            value = infer.extract_single_string_kwarg(code_action, kwarg)
            if not value:
                continue
            if infer.normalize_header_name_for_grounding(value) not in normalized_headers:
                unknown_args.append((kwarg, value))
        for kwarg in ("group_cols", "feature_cols", "key_headers"):
            for value in infer.extract_string_list_kwarg(code_action, kwarg):
                if infer.normalize_header_name_for_grounding(value) not in normalized_headers:
                    unknown_args.append((kwarg, value))

        if not unknown_args:
            return None

        unknown_text = ", ".join(f"`{kwarg}={value}`" for kwarg, value in unknown_args)
        observed_text = ", ".join(f"`{header}`" for header in observed_headers[:20])
        guidance = (
            f"PREFLIGHT_SKILL_GROUNDING: the helper call for the `{skill.name}` skill references column header(s) not present in the loaded workbook.\n"
            f"- Unknown helper arguments: {unknown_text}\n"
            f"- Observed headers: {observed_text}\n"
            "- Replace those arguments with real headers from the workbook.\n"
            "- If the correct grouping/value/date column is obvious but uncertain, prefer `group_cols=None` or `value_col=None`.\n"
        )
        suggested_call = infer.build_family_grounded_call_hint(skill.name, user_question, observed_headers)
        if suggested_call:
            guidance += f"- Recommended grounded helper call:\n  `{suggested_call}`\n"
        guidance += build_loop_breaker(skill, helper)
        return guidance.rstrip()
