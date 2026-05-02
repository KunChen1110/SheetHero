"""Generic execution preflight checks shared across skills."""

import ast
import re
from typing import TYPE_CHECKING, Optional

from ....skills import (
    all_helper_names,
    build_execution_strict_rules,
    build_loop_breaker,
    detect_skills,
    helper_embeds_summary_in_primary_table,
    select_helper,
)

if TYPE_CHECKING:
    from ..runtime import ExecutionRuntime


class ExecutionGenericPreflightAdvisor:
    """Own generic bounded-mode preflight checks and header grounding."""

    _COLUMN_ARG_KEYWORDS = {
        "on",
        "left_on",
        "right_on",
        "by",
        "subset",
        "value_col",
        "target_col",
        "date_col",
        "key_header",
        "key_headers",
        "group_cols",
        "feature_cols",
        "columns",
    }

    def __init__(self, runtime: "ExecutionRuntime"):
        self.runtime = runtime

    @staticmethod
    def _has_top_level_return(code: str) -> bool:
        try:
            module = ast.parse(code)
        except SyntaxError:
            return False
        return any(isinstance(node, ast.Return) for node in module.body)

    @staticmethod
    def _string_constant(node) -> Optional[str]:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        return None

    @classmethod
    def _extract_string_literals(cls, node) -> list[str]:
        literal = cls._string_constant(node)
        if literal is not None:
            return [literal]
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            values: list[str] = []
            for elt in node.elts:
                values.extend(cls._extract_string_literals(elt))
            return values
        return []

    @classmethod
    def _candidate_header_literals_from_code(cls, code: str) -> set[str]:
        try:
            module = ast.parse(code)
        except SyntaxError:
            return set()

        candidates: set[str] = set()

        class _Visitor(ast.NodeVisitor):
            def visit_Subscript(self, node: ast.Subscript):
                slice_node = node.slice
                if isinstance(slice_node, ast.Tuple):
                    for elt in slice_node.elts:
                        candidates.update(cls._extract_string_literals(elt))
                else:
                    candidates.update(cls._extract_string_literals(slice_node))
                self.generic_visit(node)

            def visit_Call(self, node: ast.Call):
                for keyword in node.keywords:
                    if keyword.arg in cls._COLUMN_ARG_KEYWORDS:
                        candidates.update(cls._extract_string_literals(keyword.value))

                func_name = None
                if isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr
                elif isinstance(node.func, ast.Name):
                    func_name = node.func.id

                if func_name in {"groupby", "drop_duplicates"} and node.args:
                    candidates.update(cls._extract_string_literals(node.args[0]))
                elif func_name in {"sort_values"} and node.args:
                    candidates.update(cls._extract_string_literals(node.args[0]))
                elif func_name in {"merge"}:
                    for position in node.args[:2]:
                        candidates.update(cls._extract_string_literals(position))

                self.generic_visit(node)

        _Visitor().visit(module)
        return {value for value in candidates if value and len(value.strip()) >= 3}

    @classmethod
    def _named_agg_source_column_guard(cls, code: str, observed_headers: set[str]) -> Optional[str]:
        try:
            module = ast.parse(code)
        except SyntaxError:
            return None

        known_columns: dict[str, set[str]] = {}
        # Tracks columns added via chained subscripts like `report['output_df']['NewCol'] = ...`.
        # Keyed by the chain of names+keys, e.g. ('report', 'output_df').
        subscript_path_columns: dict[tuple[str, ...], set[str]] = {}
        missing_sources: list[str] = []

        def _string_literals(node) -> list[str]:
            return cls._extract_string_literals(node)

        def _subscript_chain(node) -> Optional[tuple[str, ...]]:
            """Walk Subscript(...Subscript(Name(x), Const(k1))..., Const(kN)) → ('x', 'k1', ..., 'kN').

            Returns None if any slice is non-literal or the base isn't a plain Name.
            """
            parts: list[str] = []
            current = node
            while isinstance(current, ast.Subscript):
                slc = _string_literals(current.slice)
                if len(slc) != 1:
                    return None
                parts.append(slc[0])
                current = current.value
            if not isinstance(current, ast.Name):
                return None
            return (current.id, *reversed(parts))

        def _groupby_keys(call: ast.Call) -> set[str]:
            keys: set[str] = set()
            if call.args:
                keys.update(_string_literals(call.args[0]))
            for keyword in call.keywords:
                if keyword.arg == "by":
                    keys.update(_string_literals(keyword.value))
            return keys

        def _known_columns_from_expr(node) -> Optional[set[str]]:
            if isinstance(node, ast.Name):
                return set(known_columns.get(node.id, set())) or None
            if isinstance(node, ast.Subscript):
                chain = _subscript_chain(node)
                if chain is not None and chain in subscript_path_columns:
                    return set(subscript_path_columns[chain])
                literals = _string_literals(node.slice)
                if "output_df" in literals or "df" in literals:
                    return set(observed_headers)
                return None
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in {"copy", "reset_index"}:
                    return _known_columns_from_expr(node.func.value)
                if node.func.attr == "assign":
                    # `df.assign(NewCol=..., Other=...)` carries forward df's columns
                    # plus the keyword names. Without this, a follow-up groupby+agg
                    # using NewCol would falsely flag the column as missing.
                    base = _known_columns_from_expr(node.func.value)
                    base = set(base) if base else set(observed_headers)
                    for keyword in node.keywords:
                        if keyword.arg:
                            base.add(keyword.arg)
                    return base
                if node.func.attr == "agg" and isinstance(node.func.value, ast.Call):
                    groupby_call = node.func.value
                    if isinstance(groupby_call.func, ast.Attribute) and groupby_call.func.attr == "groupby":
                        base_columns = _known_columns_from_expr(groupby_call.func.value) or set(observed_headers)
                        output_columns = _groupby_keys(groupby_call)
                        for keyword in node.keywords:
                            if not keyword.arg:
                                continue
                            output_columns.add(keyword.arg)
                            tuple_literals = _string_literals(keyword.value)
                            if tuple_literals:
                                source_col = tuple_literals[0]
                                if source_col not in base_columns:
                                    missing_sources.append(source_col)
                        return output_columns
            return None

        for statement in module.body:
            if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
                continue
            target = statement.targets[0]
            if isinstance(target, ast.Name):
                inferred_columns = _known_columns_from_expr(statement.value)
                if inferred_columns is not None:
                    known_columns[target.id] = inferred_columns
            elif isinstance(target, ast.Subscript):
                col_literals = _string_literals(target.slice)
                if not col_literals:
                    continue
                if isinstance(target.value, ast.Name):
                    # `df['NewCol'] = ...` registers NewCol on df.
                    df_var = target.value.id
                    existing = known_columns.get(df_var)
                    base = set(existing) if existing else set(observed_headers)
                    base.update(col_literals)
                    known_columns[df_var] = base
                elif isinstance(target.value, ast.Subscript):
                    # `report['output_df']['NewCol'] = ...` — chained dict-of-DataFrame
                    # pattern. Track the inner subscript chain so a later
                    # `report['output_df'].groupby(...).agg(X=('NewCol', 'sum'))`
                    # sees NewCol in scope.
                    chain = _subscript_chain(target.value)
                    if chain is not None:
                        existing = subscript_path_columns.get(chain)
                        base = set(existing) if existing else set(observed_headers)
                        base.update(col_literals)
                        subscript_path_columns[chain] = base

        if not missing_sources:
            return None

        unique_missing = sorted(dict.fromkeys(missing_sources))
        lines = [
            "PREFLIGHT_AGG_SOURCE_COLUMNS: grouped aggregation references source columns that are not available in the current DataFrame flow.",
            "- Do not invent derived columns before creating them.",
            "- Build the intermediate summary DataFrame first, then aggregate from its real output columns.",
        ]
        for value in unique_missing[:4]:
            lines.append(f"- Missing source column: `{value}`.")
        return "\n".join(lines)

    _PLACEHOLDER_COMMENT_PATTERN = re.compile(
        r"#[^\n]*\b(?:placeholder|todo|fixme|hack|xxx|wip|stub|dummy|replace\s*me|fill\s*in\s*later)\b",
        re.IGNORECASE,
    )

    @classmethod
    def _placeholder_comment_guard(cls, code: str) -> Optional[str]:
        """Reject code that admits via comment that a value is a placeholder / TODO / stub.

        When the model writes `GrossProfit = revenue * 0.3  # Placeholder ...`, it has
        explicitly self-flagged that the math is wrong. We bounce that back instead of
        letting it ship — saves a validation round and a user-facing wrong number.
        """
        match = cls._PLACEHOLDER_COMMENT_PATTERN.search(code or "")
        if not match:
            return None
        snippet = match.group(0).strip()
        if len(snippet) > 160:
            snippet = snippet[:157] + "..."
        return (
            "PREFLIGHT_PLACEHOLDER_COMMENT: code contains a self-admitted placeholder/TODO comment.\n"
            f"- Detected: `{snippet}`\n"
            "- Replace the placeholder with the real computation derived from the verified "
            "schema — do NOT submit code with stub values like `revenue * 0.3` or `# TODO`.\n"
            "- If the formula is unclear, derive it from the user question and the column "
            "semantics (e.g. GrossProfit = sum(UnitsSold * (UnitPrice - UnitCost))).\n"
            "- Remove the placeholder comment after fixing the value."
        )

    @staticmethod
    def _duplicate_table_selector_guard(code_action: str, helper_name: str = "") -> Optional[str]:
        if helper_name != "fill_missing_from_reference":
            return None
        assignments = re.findall(
            r"^\s*([A-Za-z_]\w*)\s*=\s*next\s*\(\s*table\s+for\s+table\s+in\s+tables\s+if\s+(.+?)\)\s*$",
            code_action or "",
            flags=re.IGNORECASE | re.MULTILINE,
        )
        seen: dict[str, str] = {}
        for variable, predicate in assignments:
            normalized_predicate = re.sub(r"\s+", " ", predicate).strip().lower()
            if normalized_predicate in seen and seen[normalized_predicate] != variable:
                return (
                    "PREFLIGHT_TABLE_ROLE_SELECTION: two different table variables use the same selector, so they can point to the same input table.\n"
                    "- Select primary and reference tables with distinct role constraints.\n"
                    "- Use `find_table_by_headers(...)` with required/preferred/forbidden headers instead of duplicate `next(...)` predicates.\n"
                    "- Example:\n"
                    "  `primary_t = find_table_by_headers(tables, required_headers=['EmpID'], preferred_headers=['Name', 'JobGrade'])`\n"
                    "  `reference_t = find_table_by_headers(tables, required_headers=['EmpID'], preferred_headers=['Department'], forbidden_headers=['Name', 'JobGrade'])`\n"
                    "  `result = fill_missing_from_reference(primary_t['df'], reference_t['df'], key_header='EmpID', prefer_primary=True)`"
                )
            seen[normalized_predicate] = variable
        return None

    @staticmethod
    def _reference_completion_selector_guard(code_action: str, helper_name: str = "") -> Optional[str]:
        if helper_name != "fill_missing_from_reference":
            return None
        for variable, call_args in re.findall(
            r"^\s*([A-Za-z_]\w*)\s*=\s*find_table_by_headers\s*\(\s*tables\s*,\s*(.+?)\)\s*$",
            code_action or "",
            flags=re.IGNORECASE | re.MULTILINE,
        ):
            if "reference" not in variable.lower():
                continue
            if "forbidden_headers" in call_args:
                continue
            return (
                "PREFLIGHT_REFERENCE_SELECTOR: reference table selection is too broad and can select the primary table.\n"
                "- Add `forbidden_headers` that are present only in the primary table, such as `Name`, `JobGrade`, or other detail columns.\n"
                "- Example:\n"
                "  `reference_t = find_table_by_headers(tables, required_headers=['EmpID'], preferred_headers=['Department'], forbidden_headers=['Name', 'JobGrade'])`\n"
                "- Then call `fill_missing_from_reference(primary_t['df'], reference_t['df'], key_header='EmpID', prefer_primary=True)`."
            )
        return None

    def offline_preflight_check(self, code_action: str, user_question: str) -> Optional[str]:
        code = (code_action or "").strip()
        if not code:
            return "PREFLIGHT_LINEAR: empty code block."
        lower = code.lower()
        all_matched_skills = detect_skills(user_question)
        skill = all_matched_skills[0] if all_matched_skills else None
        helper = select_helper(skill, user_question) if skill else None
        helper_name = helper.name if helper else ""
        uses_registered_helper = bool(helper_name and f"{helper_name.lower()}(" in lower)
        uses_load_all_tables = "load_all_tables(" in lower
        # Check for any known helper function call in the code
        uses_any_known_helper = any(f"{helper_name_candidate.lower()}(" in lower for helper_name_candidate in all_helper_names())

        if self._has_top_level_return(code):
            return (
                "PREFLIGHT_LINEAR: top-level `return` is invalid in execution code.\n"
                "- Do not use `return saved_file`.\n"
                "- End with:\n"
                "  `saved_file = save_workbook_to(output_path)`\n"
                "  `print(f'SAVED_FILE: {saved_file}')`\n"
                "  `saved_file`"
            )

        if re.search(
            r"\[\s*['\"]detail_data['\"]\s*\]\s*\.(columns|values|sum|mean|max|min|groupby|iloc|loc|copy|merge|sort_values)\b",
            code,
            flags=re.IGNORECASE,
        ):
            return (
                "PREFLIGHT_LINEAR: helper `detail_data` was treated like a DataFrame.\n"
                "- `result['detail_data']` is a ready-to-write 2D table payload.\n"
                "- Use `result['output_df']` for DataFrame operations such as `.sum()`, `.mean()`, `.groupby()`, `.iloc`, or `.merge()`.\n"
                "- Use `write_dataframe_to_sheet(result['detail_data'], 'Output', 'A1')` only when writing the final table."
            )

        try:
            ast.parse(code)
        except SyntaxError as exc:
            line_info = f" on line {exc.lineno}" if exc.lineno else ""
            guidance = (
                f"PREFLIGHT_LINEAR: generated code has a syntax error{line_info}.\n"
                f"- Parser message: {exc.msg}\n"
                "- Return one full corrected code block.\n"
                "- Keep string quoting simple and avoid nested double quotes inside f-strings."
            )
            if skill is not None and helper is not None:
                loop_breaker = build_loop_breaker(
                    skill, helper,
                    extra_skills=all_matched_skills,
                    user_question=user_question,
                ).strip()
                if loop_breaker:
                    guidance += f"\n{loop_breaker}"
            return guidance

        placeholder_issue = self._placeholder_comment_guard(code)
        if placeholder_issue is not None:
            return placeholder_issue

        named_agg_issue = self._named_agg_source_column_guard(code, set(self.runtime._observed_header_set()))
        if named_agg_issue is not None:
            return named_agg_issue

        repeated_selector_issue = self._duplicate_table_selector_guard(code, helper_name)
        if repeated_selector_issue is not None:
            return repeated_selector_issue
        reference_selector_issue = self._reference_completion_selector_guard(code, helper_name)
        if reference_selector_issue is not None:
            return reference_selector_issue

        if helper is not None and helper.self_loading:
            if skill is not None and getattr(skill, "output_mode", "") == "text":
                if re.search(r"\[\s*['\"](?:output_df|detail_data)['\"]\s*\]", code, flags=re.IGNORECASE):
                    skill_hint = (build_loop_breaker(skill, helper, user_question=user_question) or "").strip()
                    helper_block = (
                        f"PREFLIGHT_TEXT_SCAN_HELPER: `{helper_name}(...)` returns a text report, not a DataFrame.\n"
                        "- Use only `report['answer']` for the final text answer.\n"
                        "- Do not access `report['output_df']` or `report['detail_data']`.\n"
                        "- Do not create or save a workbook for scan tasks.\n"
                    )
                    if skill_hint:
                        helper_block += f"{skill_hint}\n"
                    return helper_block.rstrip()
            if helper_embeds_summary_in_primary_table(helper_name) and "add_summary_row(" in lower:
                skill_hint = (build_loop_breaker(skill, helper, user_question=user_question) or build_execution_strict_rules(skill, helper) or "").strip()
                helper_block = (
                    f"PREFLIGHT_SELF_LOADING_HELPER: `{helper_name}(...)` already returns the final report table with summary/target rows embedded.\n"
                    "- Do not add extra `add_summary_row(...)` calls after writing this helper's `detail_data`.\n"
                    "- Write `report['detail_data']` directly, save the workbook, and print `RESULT_SUMMARY:` from `report['summary']` or the final `output_df` if available.\n"
                )
                if skill_hint:
                    helper_block += f"{skill_hint}\n"
                return helper_block.rstrip()
            if helper_embeds_summary_in_primary_table(helper_name) and re.search(
                rf"{re.escape(helper_name)}\s*\(\s*\).*?\[\s*['\"]output_df['\"]\s*\]",
                code,
                flags=re.IGNORECASE | re.DOTALL,
            ):
                skill_hint = (build_loop_breaker(skill, helper, user_question=user_question) or build_execution_strict_rules(skill, helper) or "").strip()
                helper_block = (
                    f"PREFLIGHT_SELF_LOADING_HELPER: `{helper_name}(...)` returns a final report table; do not treat `output_df` as raw source data.\n"
                    "- Write `report['detail_data']` directly to `Output` and save.\n"
                    "- Do not recalculate metrics from `report['output_df']`; the helper already prepared the dashboard/report values.\n"
                    "- For final text, rely on workbook inspection or `report['summary']` if available.\n"
                )
                if skill_hint:
                    helper_block += f"{skill_hint}\n"
                return helper_block.rstrip()
            positional_arg_match = re.search(
                rf"{re.escape(helper_name)}\s*\(\s*(?!\)|\w+\s*=)([^,)]+)",
                code,
                flags=re.IGNORECASE,
            )

            if positional_arg_match:
                skill_hint = (build_loop_breaker(skill, helper, user_question=user_question) or build_execution_strict_rules(skill, helper) or "").strip()
                helper_block = (
                    f"PREFLIGHT_SELF_LOADING_HELPER: `{helper_name}(...)` must not be called with positional arguments.\n"
                    "- This helper discovers the runtime tables on its own.\n"
                    "- Call it as `report = "
                    f"{helper_name}()` or use only optional named args like `range_ref=...`.\n"
                )
                if skill_hint:
                    helper_block += f"{skill_hint}\n"
                return helper_block.rstrip()
            manual_reader_patterns = ("read_table_multi(", "find_table_by_headers(", "load_all_tables(")
            # Only complain when the registered helper was NOT used. If the helper IS in
            # the code, treating any incidental load_all_tables()/read_table_multi() call as a
            # blocker is a false positive — models commonly use them just to print/inspect
            # before delegating the real work to the self-loading helper.
            if any(pattern in lower for pattern in manual_reader_patterns) and not uses_registered_helper:
                skill_hint = (build_loop_breaker(skill, helper, user_question=user_question) or build_execution_strict_rules(skill, helper) or "").strip()
                helper_block = (
                    f"PREFLIGHT_SELF_LOADING_HELPER: `{helper_name}(...)` already loads and prepares the source tables for the `{skill.name}` skill.\n"
                    "- Do not hand-build table loading or reconstruction logic for this task.\n"
                    "- Remove manual `read_table_multi(...)`, `find_table_by_headers(...)`, and `load_all_tables(...)` calls from execution code.\n"
                    "- Call the helper directly first.\n"
                    "- If the task needs more processing after the join, continue from `report['output_df']`.\n"
                    "- Use `report['detail_data']` only when writing a final sheet.\n"
                )
                if skill_hint:
                    helper_block += f"{skill_hint}\n"
                return helper_block.rstrip()

        skill_grounding_issue = self.skill_helper_header_grounding_guard(code_action, user_question)
        if skill_grounding_issue is not None:
            return skill_grounding_issue

        header_alias_issue = self.header_alias_grounding_guard(code_action)
        if header_alias_issue is not None:
            return header_alias_issue

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

        if re.search(r"^\s*from\s+your_[a-z_]+\s+import\s+", code, flags=re.IGNORECASE | re.MULTILINE):
            return (
                "PREFLIGHT_LINEAR: do not import placeholder helper modules.\n"
                "- Helper functions are already injected into the sandbox globals.\n"
                "- Remove imports like `from your_spreadsheet_helpers import *`.\n"
                "- Call injected helpers directly: `build_relational_join_enrichment_report(...)`, "
                "`create_output_sheet(...)`, `write_dataframe_to_sheet(...)`, `save_workbook_to(output_path)`."
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

    def header_alias_grounding_guard(self, code_action: str) -> Optional[str]:
        code = code_action or ""
        observed_headers = sorted(self.runtime._observed_header_set())
        if not observed_headers:
            return None

        infer = self.runtime.question_inference
        normalized_observed = {
            infer.normalize_header_name_for_grounding(header): header
            for header in observed_headers
        }
        observed_keys = set(normalized_observed.keys())
        candidate_literals = self._candidate_header_literals_from_code(code)

        suggestions: list[tuple[str, str]] = []
        for literal in sorted(candidate_literals):
            normalized_literal = infer.normalize_header_name_for_grounding(literal)
            if not normalized_literal or normalized_literal in observed_keys:
                continue
            close_matches = [
                actual
                for normalized_actual, actual in normalized_observed.items()
                if normalized_actual.startswith(normalized_literal)
                or normalized_literal.startswith(normalized_actual)
            ]
            if len(close_matches) == 1:
                suggestions.append((literal, close_matches[0]))

        if not suggestions:
            return None

        lines = [
            "PREFLIGHT_HEADER_GROUNDING: code references column names that do not exactly match the runtime schema.",
            "- Use the exact observed headers from the schema snapshot/runtime tables.",
        ]
        for requested, actual in suggestions[:4]:
            lines.append(f"- Replace `{requested}` with `{actual}`.")
        return "\n".join(lines)

    def skill_helper_header_grounding_guard(self, code_action: str, user_question: str) -> Optional[str]:
        all_matched_skills = detect_skills(user_question)
        skill = all_matched_skills[0] if all_matched_skills else None
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
            extractor = getattr(infer, "extract_string_list_kwarg", None)
            if extractor is None:
                continue
            for value in extractor(code_action, kwarg):
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
        suggested_call = infer.build_skill_grounded_call_hint(helper.name, user_question, observed_headers)
        if suggested_call:
            guidance += f"- Recommended grounded helper call:\n  `{suggested_call}`\n"
        guidance += build_loop_breaker(skill, helper, extra_skills=all_matched_skills, user_question=user_question)
        return guidance.rstrip()
