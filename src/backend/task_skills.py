"""Skill-based routing for spreadsheet workflows.

Skills are abstract operation categories (merge, aggregate, statistical, etc.).
Each skill owns a list of helpers. Detection uses generic keywords.
Helper selection within a skill uses question analysis + data schema.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, Optional, Sequence


@dataclass(frozen=True)
class HelperSpec:
    """One concrete helper function available within a skill."""
    name: str
    self_loading: bool = False
    description: str = ""
    sub_detector: Optional[Callable[[str], bool]] = None


@dataclass(frozen=True)
class SkillSpec:
    """Abstract spreadsheet operation skill."""
    name: str
    detector: Callable[[str], bool]
    helpers: tuple[HelperSpec, ...]
    output_mode: str = "workbook"


def _is_merge_request(q: str) -> bool:
    q = q.lower()
    join_words = ("merge", "join", "combine", "concatenate", "link", "enrich")
    structure_words = ("file", "files", "table", "tables", "sheet", "sheets",
                       "dataset", "datasets", "spreadsheet")
    fill_words = ("fill missing", "fill any missing", "complete missing",
                  "populate missing", "use the reference", "use another file")
    if any(w in q for w in fill_words):
        return True
    return (any(w in q for w in join_words)
            and any(w in q for w in structure_words))


def _is_aggregate_request(q: str) -> bool:
    q = q.lower()
    agg_words = ("average", "mean", " sum ", "total ",
                 "median", "rank", "ranking")
    # Only explicit grouping phrases — avoid the overly broad " by " which
    # matches "efficiency of Coca-Cola from 2009 to 2018 by calculating".
    # Avoid "by region"/"by country" which collide with domain questions
    # like "diabetes worldwide by region" or "prevalence by country".
    group_words = ("group by", "grouped by", "group the", "grouped the",
                   "by department", "by year", "by month", "by quarter",
                   "by semester", "by brand", "by category",
                   "by store", "by type")
    has_agg = any(w in q for w in agg_words)
    has_group = any(w in q for w in group_words)
    has_sort = any(w in q for w in ("sort", "rank", "descending", "ascending",
                                     "highest", "lowest", "top "))
    return has_agg and (has_group or has_sort)


def _is_statistical_request(q: str) -> bool:
    q = q.lower()
    if "correlation" in q or "regression" in q or "coefficient" in q:
        return True
    if "predict" in q and ("using" in q or "from" in q):
        return True
    if "cycle" in q and "graph" in q:
        return True
    if "contain a cycle" in q or "contains a cycle" in q:
        return True
    return False


def _is_schedule_request(q: str) -> bool:
    q = q.lower()
    if "dependency" in q or "dependencies" in q or "depends on" in q:
        return True
    if "topological" in q or "dag" in q:
        return True
    if ("schedule" in q or "scheduling" in q) and (
        "start time" in q or "end time" in q or "task" in q
    ):
        return True
    alloc_words = ("allocate", "assign", "distribute", "place", "seat")
    capacity_words = ("capacity", "slots", "seat limit", "max students", "quota")
    if any(w in q for w in alloc_words) and any(w in q for w in capacity_words):
        return True
    return False


def _is_scan_request(q: str) -> bool:
    q = q.lower()
    missing_words = ("missing data", "missing values", "missing entries",
                     "blank values", "empty values", "null values")
    action_words = ("identify", "find", "locate", "report", "scan",
                    "check", "detect", "audit", "inspect")
    # "format" alone is too broad ("in the following format" triggers).
    # Require format-specific context: "inconsistenc", "identifier", or
    # "format" next to "check"/"inconsistenc".
    format_words = ("inconsistenc", "identifier", "format inconsistenc",
                    "check for any inconsistenc", "format check")
    has_missing = any(w in q for w in missing_words)
    has_format = any(w in q for w in format_words)
    has_action = any(w in q for w in action_words)
    return (has_missing or has_format) and has_action


def _is_fill_missing(q: str) -> bool:
    q = q.lower()
    return any(w in q for w in (
        "fill missing", "fill any missing", "complete missing",
        "populate missing", "use the reference", "use another file",
    ))


def _is_multi_key_join(q: str) -> bool:
    q = q.lower()
    return any(w in q for w in (
        "composite key", "multi-key", "multiple keys", "two keys", "shared keys",
    ))


def _is_key_based_join(q: str) -> bool:
    q = q.lower()
    key_hints = ("student id", "employee id", "customer id", "order id",
                 "using the", "based on", "on the", "common key",
                 "shared column", "matching", "id column")
    return any(w in q for w in key_hints)


def _is_time_series(q: str) -> bool:
    q = q.lower()
    period_words = ("monthly", "by month", "per month", "yearly", "by year",
                    "per year", "quarterly", "by quarter", "annually",
                    "by semester", "by term", "last 5 years", "past 3 years",
                    "last 3 years", "last 10 years")
    return any(w in q for w in period_words)


def _is_regression(q: str) -> bool:
    q = q.lower()
    return "regression" in q or "coefficient" in q or "weight" in q or (
        "predict" in q and ("using" in q or "from" in q)
    )


def _is_correlation(q: str) -> bool:
    q = q.lower()
    return "correlation" in q


def _is_cycle_detection(q: str) -> bool:
    q = q.lower()
    return "cycle" in q or "circular" in q


def _is_dependency_schedule(q: str) -> bool:
    q = q.lower()
    return ("dependency" in q or "dependencies" in q or "depends on" in q
            or "topological" in q or "dag" in q)


def _is_missing_data_scan(q: str) -> bool:
    q = q.lower()
    return any(w in q for w in ("missing data", "missing values", "blank values",
                                 "null values", "empty values"))


def _is_allocation(q: str) -> bool:
    q = q.lower()
    return any(w in q for w in ("allocate", "capacity", "slots", "seat limit"))


@lru_cache(maxsize=1)
def _skill_specs() -> tuple[SkillSpec, ...]:
    return (
        SkillSpec(
            name="merge",
            detector=_is_merge_request,
            helpers=(
                HelperSpec("fill_missing_from_reference",
                           description="Fill missing values from a reference table",
                           sub_detector=_is_fill_missing),
                HelperSpec("build_multi_key_relational_join_report",
                           self_loading=True,
                           description="Join tables on multiple shared keys",
                           sub_detector=_is_multi_key_join),
                HelperSpec("build_relational_join_enrichment_report",
                           self_loading=True,
                           description="Join tables on a shared key column",
                           sub_detector=_is_key_based_join),
                HelperSpec("concat_tables_with_same_headers",
                           description="Stack tables with identical columns"),
            ),
        ),
        SkillSpec(
            name="aggregate",
            detector=_is_aggregate_request,
            helpers=(
                HelperSpec("build_time_series_aggregation_report",
                           self_loading=True,
                           description="Aggregate by time period (month, quarter, year)",
                           sub_detector=_is_time_series),
                HelperSpec("build_grouped_aggregation_ranking_report",
                           self_loading=True,
                           description="Group by categories and aggregate with ranking"),
            ),
        ),
        SkillSpec(
            name="statistical",
            detector=_is_statistical_request,
            helpers=(
                HelperSpec("fit_linear_regression_weights",
                           description="Fit linear regression coefficients",
                           sub_detector=_is_regression),
                HelperSpec("build_correlation_matrix_table",
                           description="Compute pairwise correlation matrix",
                           sub_detector=_is_correlation),
                HelperSpec("build_cycle_detection_report",
                           description="Detect cycles in directed graphs",
                           sub_detector=_is_cycle_detection),
            ),
        ),
        SkillSpec(
            name="schedule",
            detector=_is_schedule_request,
            helpers=(
                HelperSpec("build_dependency_schedule",
                           description="Schedule tasks respecting dependency order",
                           sub_detector=_is_dependency_schedule),
                HelperSpec("build_capacity_constrained_allocation_report",
                           self_loading=True,
                           description="Allocate entities to resources with capacity limits",
                           sub_detector=_is_allocation),
                HelperSpec("build_relational_assignment_schedule_report",
                           self_loading=True,
                           description="Build assignment schedule from relational tables"),
            ),
        ),
        SkillSpec(
            name="scan",
            detector=_is_scan_request,
            output_mode="text",
            helpers=(
                HelperSpec("build_missing_data_report",
                           self_loading=True,
                           description="Scan for missing values and report findings",
                           sub_detector=_is_missing_data_scan),
                HelperSpec("build_room_format_report",
                           self_loading=True,
                           description="Check identifier format consistency"),
            ),
        ),
    )


def all_skills() -> Sequence[SkillSpec]:
    return _skill_specs()


def detect_skill(user_question: str) -> Optional[SkillSpec]:
    for skill in all_skills():
        if skill.detector(user_question):
            return skill
    return None


def select_helper(skill: SkillSpec, user_question: str) -> Optional[HelperSpec]:
    fallback = None
    for helper in skill.helpers:
        if helper.sub_detector is not None:
            if helper.sub_detector(user_question):
                return helper
        elif fallback is None:
            fallback = helper
    return fallback


def build_execution_strict_rules(skill: SkillSpec, helper: HelperSpec) -> str:
    label = skill.name.upper()
    lines = [
        f"\n\n**{label} SKILL RULES (STRICT):**",
        f"- Use `{helper.name}(...)` for this task.",
        f"- Helper description: {helper.description}",
        "- Do not hand-build manual data processing logic when this helper is available.",
    ]
    if helper.self_loading:
        lines.append(
            "- The helper loads source tables internally; "
            "do not call `read_table_multi(...)`, `find_table_by_headers(...)`, "
            "or `load_all_tables(...)` alongside it."
        )
    return "\n".join(lines) + "\n"


def build_loop_breaker(skill: SkillSpec, helper: HelperSpec) -> str:
    label = skill.name.upper()
    if skill.output_mode == "text":
        return (
            f"\n{label} LOOP BREAKER:\n"
            f"- Use `report = {helper.name}()`\n"
            "- Return `report['answer']` as short text.\n"
            "- Do not create or save an output workbook.\n"
        )
    lines = [
        f"\n{label} LOOP BREAKER:",
        "- Use exactly this helper-first shape:",
        f"  `report = {helper.name}(...)`",
        "  `create_output_sheet('Output')`",
        "  `write_dataframe_to_sheet(report['detail_data'], 'Output', 'A1')`",
        "  `saved_file = save_workbook_to(output_path)`",
        "  `print(f'SAVED_FILE: {saved_file}')`",
        "  `saved_file`",
    ]
    if helper.self_loading:
        lines.append(
            "- Do not call `read_table_multi(...)`, `find_table_by_headers(...)`, "
            "or `load_all_tables(...)` anywhere in the code."
        )
    return "\n".join(lines) + "\n"


def build_skill_hint(skill: SkillSpec, helper: HelperSpec) -> str:
    lines = [
        f"[SKILL DETECTED: {skill.name}]",
        f"Recommended helper: {helper.name}()",
        f"Description: {helper.description}",
        f"Output mode: {skill.output_mode}",
    ]
    if helper.self_loading:
        lines.append("The helper loads data internally. Do not read input files manually.")
    else:
        lines.append("Load data first with load_all_tables(), then pass to the helper.")
    return "\n".join(lines)


# Domain-specific zero-arg helpers available in the sandbox.
# These have no skill detector — the LLM discovers them via this hint.
_DOMAIN_HELPERS: tuple[tuple[str, str], ...] = (
    ("build_financial_dashboard_report", "Quarter-level financial dashboard from P&L/sales/KPI tables"),
    ("build_candidate_screening_report", "Ranked candidate table from multi-file candidate data"),
    ("build_inventory_eoq_report", "Inventory EOQ analysis with sensitivity tables"),
    ("build_hospital_utilisation_report", "Staff/service utilisation by department"),
    ("build_market_share_shipment_report", "Brand shipment estimates from market-share + shipment tables"),
    ("build_cash_flow_efficiency_report", "Yearly OCF/FCF efficiency table from financial statements"),
    ("build_diabetes_region_report", "Regional diabetes summary with global share and avg expenditure"),
    ("build_mobile_reviews_summary_report", "Grouped review summary by country and brand"),
    ("build_store_feature_analysis_report", "Store feature analysis with avg-by-type and holiday comparison"),
    ("build_ecommerce_merge_report", "Merged e-commerce table from relational CSV tables"),
)


def build_available_helpers_hint() -> str:
    """Build a compact hint listing all zero-arg domain helpers available in sandbox."""
    lines = [
        "[AVAILABLE HELPERS]",
        "The sandbox has these ready-to-use helper functions (call with no arguments):",
    ]
    for name, desc in _DOMAIN_HELPERS:
        lines.append(f"- `{name}()` — {desc}")
    lines.append("If one matches the task, plan to use it directly. Do not hand-build the logic.")
    return "\n".join(lines)


_OLD_FAMILY_TO_SKILL_HELPER = {
    "schema_aligned_merge_summary": ("merge", "concat_tables_with_same_headers"),
    "reference_guided_completion": ("merge", "fill_missing_from_reference"),
    "composite_key_relational_join": ("merge", "build_multi_key_relational_join_report"),
    "relational_join_enrichment": ("merge", "build_relational_join_enrichment_report"),
    "relational_flattening_report": ("merge", "build_ecommerce_merge_report"),
    "temporal_aggregation_ranking": ("aggregate", "build_time_series_aggregation_report"),
    "grouped_aggregation_ranking": ("aggregate", "build_grouped_aggregation_ranking_report"),
    "grouped_metric_summary": ("aggregate", "build_mobile_reviews_summary_report"),
    "tabular_regression_analysis": ("statistical", "fit_linear_regression_weights"),
    "pairwise_correlation_matrix": ("statistical", "build_correlation_matrix_table"),
    "graph_consistency_scan": ("statistical", "build_cycle_detection_report"),
    "dependency_constrained_schedule": ("schedule", "build_dependency_schedule"),
    "capacity_constrained_allocation": ("schedule", "build_capacity_constrained_allocation_report"),
    "relational_assignment_schedule": ("schedule", "build_relational_assignment_schedule_report"),
    "missing_data_scan": ("scan", "build_missing_data_report"),
    "identifier_format_scan": ("scan", "build_room_format_report"),
    "multi_source_metric_dashboard": (None, "build_financial_dashboard_report"),
    "entity_ranking_report": (None, "build_candidate_screening_report"),
    "parameter_driven_policy_report": (None, "build_inventory_eoq_report"),
    "capacity_utilisation_report": (None, "build_hospital_utilisation_report"),
    "overlapping_period_alignment_report": (None, "build_market_share_shipment_report"),
    "derived_efficiency_report": (None, "build_cash_flow_efficiency_report"),
    "proportion_and_cost_report": (None, "build_diabetes_region_report"),
    "comparative_multi_sheet_summary": (None, "build_store_feature_analysis_report"),
    "temporal_growth_visual_report": (None, "build_region_growth_analysis"),
}


_HELPER_RUNTIME_MODES = {
    "concat_tables_with_same_headers": "schema_merge_summary",
    "fill_missing_from_reference": "reference_completion",
    "build_relational_join_enrichment_report": "relational_join",
    "build_multi_key_relational_join_report": "composite_relational_join",
    "build_grouped_aggregation_ranking_report": "grouped_aggregation",
    "build_time_series_aggregation_report": "temporal_aggregation",
    "fit_linear_regression_weights": "regression",
    "build_correlation_matrix_table": "correlation",
    "build_cycle_detection_report": "graph_scan",
    "build_dependency_schedule": "dependency_schedule",
    "build_capacity_constrained_allocation_report": "zero_arg_helper",
    "build_relational_assignment_schedule_report": "relational_assignment",
    "build_missing_data_report": "text_scan",
    "build_room_format_report": "text_scan",
    "build_financial_dashboard_report": "zero_arg_helper",
    "build_candidate_screening_report": "zero_arg_helper",
    "build_inventory_eoq_report": "zero_arg_helper",
    "build_hospital_utilisation_report": "zero_arg_helper",
    "build_market_share_shipment_report": "zero_arg_helper",
    "build_cash_flow_efficiency_report": "zero_arg_helper",
    "build_diabetes_region_report": "zero_arg_helper",
    "build_mobile_reviews_summary_report": "zero_arg_helper",
    "build_store_feature_analysis_report": "comparative_multi_sheet",
    "build_region_growth_analysis": "temporal_growth",
    "build_ecommerce_merge_report": "zero_arg_helper",
}

_HELPER_VALIDATION_MODES = {
    "build_capacity_constrained_allocation_report": "allocation",
    "build_dependency_schedule": "dependency_schedule",
    "build_grouped_aggregation_ranking_report": "grouped_aggregation",
    "build_time_series_aggregation_report": "temporal_aggregation",
    "build_multi_key_relational_join_report": "relational_join",
    "build_relational_join_enrichment_report": "relational_join",
    "build_relational_assignment_schedule_report": "relational_assignment",
    "build_region_growth_analysis": "temporal_growth",
    "fit_linear_regression_weights": "regression",
    "build_correlation_matrix_table": "correlation",
    "build_store_feature_analysis_report": "comparative_multi_sheet",
}

_POST_TABLE_SUMMARY_HELPERS = {
    "build_capacity_constrained_allocation_report",
    "concat_tables_with_same_headers",
    "build_dependency_schedule",
    "build_region_growth_analysis",
}


def get_helper_runtime_mode(helper_name: str) -> Optional[str]:
    return _HELPER_RUNTIME_MODES.get(helper_name)


def get_helper_validation_mode(helper_name: str) -> Optional[str]:
    return _HELPER_VALIDATION_MODES.get(helper_name)


def helper_uses_post_table_summary_row(helper_name: str) -> bool:
    return helper_name in _POST_TABLE_SUMMARY_HELPERS
