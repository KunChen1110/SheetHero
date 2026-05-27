"""skills package — skill-based routing for spreadsheet workflows.

Skills are abstract operation categories (merge, aggregate, statistical, etc.).
Each skill carries a strategy_doc injected into LLM prompts and owns a list of helpers.

Detection: hybrid rule matching plus conservative semantic retrieval.
Helper selection: rule sub-detectors first, semantic helper retrieval as a
    fallback; schema grounding happens downstream in the execution stage.
"""

from .models import HelperSpec, SkillSpec
from .registry import all_skills, detect_skill, detect_skills, select_helper
from .semantic_router import retrieve_skill_context, semantic_detect_skills
from .runtime_plan import RuntimeExecutionPlan, parse_plan_summary, WorkflowStep, compose_skill_plan
from .prompt_builders import (
    build_skill_hint,
    build_compact_skill_workflow,
    build_execution_strict_rules,
    build_loop_breaker,
    build_fallback_strategy,
    format_plan_log,
)
from .helper_metadata import (
    all_helper_names,
    get_helper_metadata,
    get_helper_runtime_mode,
    get_helper_output_mode,
    get_helper_validation_mode,
    get_helper_grounding_mode,
    get_helper_preflight_guard_names,
    get_helper_final_response_label,
    get_helper_text_preview_inspector_name,
    get_helper_saved_workbook_inspector_name,
    get_helper_code_inspector_name,
    get_helper_rule_inspector_name,
    get_helper_documented_result_keys,
    helper_uses_post_table_summary_row,
    helper_embeds_summary_in_primary_table,
    helper_scalar_answer_keywords,
    helper_requires_chart_embedding,
    helper_supports_highlight_rows,
    helper_bounded_error_signatures,
    helper_bounded_error_task_label,
    helper_bounded_error_extra_note,
    helper_name_for_bounded_error,
    helper_result_variable_name,
)

__all__ = [
    "HelperSpec",
    "SkillSpec",
    "all_skills",
    "detect_skill",
    "detect_skills",
    "select_helper",
    "retrieve_skill_context",
    "semantic_detect_skills",
    "RuntimeExecutionPlan",
    "parse_plan_summary",
    "WorkflowStep",
    "compose_skill_plan",
    "build_skill_hint",
    "build_compact_skill_workflow",
    "build_execution_strict_rules",
    "build_loop_breaker",
    "build_fallback_strategy",
    "format_plan_log",
    "all_helper_names",
    "get_helper_metadata",
    "get_helper_runtime_mode",
    "get_helper_output_mode",
    "get_helper_validation_mode",
    "get_helper_grounding_mode",
    "get_helper_preflight_guard_names",
    "get_helper_final_response_label",
    "get_helper_text_preview_inspector_name",
    "get_helper_saved_workbook_inspector_name",
    "get_helper_code_inspector_name",
    "get_helper_rule_inspector_name",
    "get_helper_documented_result_keys",
    "helper_uses_post_table_summary_row",
    "helper_embeds_summary_in_primary_table",
    "helper_scalar_answer_keywords",
    "helper_requires_chart_embedding",
    "helper_supports_highlight_rows",
    "helper_bounded_error_signatures",
    "helper_bounded_error_task_label",
    "helper_bounded_error_extra_note",
    "helper_name_for_bounded_error",
    "helper_result_variable_name",
]
