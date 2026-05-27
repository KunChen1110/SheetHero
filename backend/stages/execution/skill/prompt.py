"""Skill-based execution prompt augmentation helpers."""

from typing import TYPE_CHECKING

from ....log.logger_registry import LoggerRegistry
from ....skills import (
    detect_skills, select_helper,
    build_execution_strict_rules, build_loop_breaker, build_skill_hint,
    build_compact_skill_workflow,
    build_fallback_strategy,
    retrieve_skill_context,
)
from ....skills.prompt_builders import format_plan_log
from ....skills import compose_skill_plan

if TYPE_CHECKING:
    from ..runtime import ExecutionRuntime

logger = LoggerRegistry.setup_logger(__name__)


def _build_first_attempt_plan_contract(composed_plan: list) -> str:
    required_helpers: list[str] = []
    constraints: list[str] = []
    step_names: list[str] = []
    for step in composed_plan:
        step_names.append(step.step_name)
        for helper in step.preferred_helpers:
            if helper not in required_helpers:
                required_helpers.append(helper)
        for constraint in step.constraints:
            if constraint not in constraints:
                constraints.append(constraint)

    if not required_helpers:
        return ""

    helper_lines = "\n".join(f"- `{helper}(...)`" for helper in required_helpers)
    constraint_lines = "\n".join(f"- {constraint}" for constraint in constraints[:8])
    ordered_steps = " -> ".join(step_names)
    return (
        "\n\n**FIRST ATTEMPT PLAN CONTRACT (MANDATORY):**\n"
        "The first execution attempt must satisfy the detected skill plan; do not substitute equivalent hand-written logic for required helpers.\n"
        f"Ordered plan: `{ordered_steps}`\n"
        "Required helper calls:\n"
        f"{helper_lines}\n"
        "Required invariants:\n"
        f"{constraint_lines}\n"
        "- If `summarize_numeric_column(...)` is required, pass the same DataFrame to `write_dataframe_to_sheet(...)` before using `summary_result['highlight_rows']['max']` or `['min']` for highlights.\n"
        "- Replace only helper arguments such as column names with verified runtime headers."
    )


def _build_helper_first_policy_for_plan(composed_plan: list) -> str:
    required_helpers: list[str] = []
    for step in composed_plan:
        for helper in step.preferred_helpers:
            if helper not in required_helpers:
                required_helpers.append(helper)

    if not required_helpers:
        return ""

    substitution_rules = {
        "concat_tables_with_same_headers": "- Do not stack selected same-schema tables with pd.concat; call concat_tables_with_same_headers(tables).",
        "summarize_numeric_column": "- Do not compute final summary/highlight rows with sum(), mean(), max(), idxmax(), argmax(), or DataFrame.index; call summarize_numeric_column(...).",
        "compute_ratio_column": "- Do not compute selected ratio columns with df[a] / df[b]; call compute_ratio_column(...).",
        "compute_percentage_share": "- Do not compute selected share columns with value / total * 100; call compute_percentage_share(...).",
        "compute_weighted_score": "- Do not compute selected weighted scores with manual weighted sums; call compute_weighted_score(...).",
        "add_rank_column": "- Do not compute selected ranks with sort_values(), rank(), or manual counters; call add_rank_column(...).",
        "build_group_summary": "- Do not replace selected grouped summaries with groupby().agg(); call build_group_summary(...).",
        "build_grouped_aggregation_ranking_report": "- Do not replace the selected grouped aggregation report with manual groupby/ranking code; call build_grouped_aggregation_ranking_report(...).",
        "build_time_series_aggregation_report": "- Do not replace the selected time-series aggregation report with manual date grouping; call build_time_series_aggregation_report(...).",
        "build_dependency_schedule": "- Do not write custom topological scheduling; call build_dependency_schedule(...).",
        "build_cycle_detection_report": "- Do not write custom graph-cycle traversal; call build_cycle_detection_report(...).",
        "fit_linear_regression_weights": "- Do not write custom least-squares or external regression code; call fit_linear_regression_weights(...).",
        "compute_feature_correlations": "- Do not write custom target-feature correlation loops; call compute_feature_correlations(...).",
        "build_correlation_matrix_table": "- Do not write custom correlation matrix assembly; call build_correlation_matrix_table(...).",
        "fill_missing_from_reference": "- Do not hand-fill reference values with ad hoc merge/update logic; call fill_missing_from_reference(...).",
    }
    helper_lines = "\n".join(f"- `{helper}(...)`" for helper in required_helpers)
    rule_lines = "\n".join(
        substitution_rules[helper]
        for helper in required_helpers
        if helper in substitution_rules
    )
    if not rule_lines:
        rule_lines = "- Do not replace selected helpers with equivalent pandas logic."
    return (
        "\n\n**HELPER-FIRST POLICY FOR THIS PLAN:**\n"
        "LLM role: orchestrate helper calls, pass verified columns, write outputs, and save. "
        "Do not become the primary algorithm implementer while a selected helper exists.\n"
        "Do not replace selected helpers with equivalent pandas logic.\n"
        "Selected helpers that must appear in the first executable code block:\n"
        f"{helper_lines}\n"
        "Forbidden substitutions:\n"
        f"{rule_lines}\n"
        "Pandas is allowed only as glue code for schema inspection, filtering before helper calls, and light formatting after helper calls."
    )


def _needs_first_attempt_plan_contract(composed_plan: list) -> bool:
    task_steps = {
        step.skill
        for step in composed_plan
        if step.skill not in {"base", "output"}
    }
    return len(task_steps) >= 2


class ExecutionSkillPromptAdvisor:
    """Own skill-based execution prompt augmentation."""

    def __init__(self, runtime: "ExecutionRuntime"):
        self.runtime = runtime

    def augment_initial_prompt(self, user_content: str, user_question: str) -> str:
        runtime = self.runtime
        basenames = runtime._available_workbook_basenames()
        schema_snapshot = runtime._build_schema_snapshot()
        is_offline_strict = bool(getattr(runtime, "_is_offline_strict", False))
        if basenames and not (is_offline_strict and schema_snapshot):
            file_lines = "\n".join(f"- `{name}`" for name in basenames)
            user_content += (
                "\n\n**AVAILABLE INPUT FILES (STRICT):**\n"
                f"{file_lines}\n"
                "Use ONLY these names for input lookups."
            )
        if schema_snapshot:
            user_content += (
                "\n\n**SCHEMA SNAPSHOT (RUNTIME, TRUST THIS):**\n"
                f"{schema_snapshot}\n"
                "Use these real headers for all select/merge operations. Do not invent columns."
            )

        retrieved_skill_context = retrieve_skill_context(user_question)
        if retrieved_skill_context:
            user_content += f"\n\n{retrieved_skill_context}"

        all_matched_skills = detect_skills(user_question)
        skill = all_matched_skills[0] if all_matched_skills else None
        if skill:
            helper = select_helper(skill, user_question)
            if helper is not None:
                observed_headers = sorted(runtime._observed_header_set())

                # --- verbose skill-chain observability ---
                helpers_map = {s.name: select_helper(s, user_question) for s in all_matched_skills}
                composed_plan = compose_skill_plan(all_matched_skills, helpers_map)  # type: ignore[arg-type]
                logger.info(format_plan_log(all_matched_skills, composed_plan))
                # -----------------------------------------

                plan_summary = ""
                try:
                    plan = runtime.question_inference.infer_runtime_plan(
                        skill.name,
                        helper.name,
                        user_question,
                        observed_headers,
                    )
                except Exception:
                    plan = None
                if plan is not None:
                    plan_summary = plan.to_prompt_summary()
                workflow_doc = (
                    build_compact_skill_workflow(skill, helper)
                    if is_offline_strict
                    else build_skill_hint(skill, helper)
                )
                user_content += (
                    f"\n\n**PRIMARY SKILL WORKFLOW [{skill.name.upper()}]:**\n"
                    f"{workflow_doc}"
                )
                user_content += build_execution_strict_rules(
                    skill,
                    helper,
                    plan_summary=plan_summary,
                )
                user_content += build_loop_breaker(
                    skill,
                    helper,
                    plan_summary=plan_summary,
                    extra_skills=all_matched_skills,
                    user_question=user_question,
                )
                if _needs_first_attempt_plan_contract(composed_plan):
                    user_content += _build_helper_first_policy_for_plan(composed_plan)
                    user_content += _build_first_attempt_plan_contract(composed_plan)
            else:
                user_content += f"\n\n{build_fallback_strategy(user_question)}"
                user_content += (
                    "\n\n**NO COVERING JOIN HELPER SELECTED:**\n"
                    "- Use `load_all_tables()` and header-grounded `find_table_by_headers(...)` to assign table roles.\n"
                    "- Use pandas joins only after table roles and join keys are verified from runtime headers.\n"
                    "- For downstream analytical reports, compute the requested grain explicitly before writing each output sheet.\n"
                    "- Do not call generic join helpers just to satisfy helper-first rules when they do not cover the requested final report."
                )
        else:
            # No skill matched — inject signal-aware fallback so the LLM always
            # gets schema grounding rules and relevant computation hints.
            user_content += f"\n\n{build_fallback_strategy(user_question)}"

        return user_content
