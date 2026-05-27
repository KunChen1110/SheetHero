"""Skill registry: builds SkillSpec list and provides detect/select helpers."""

from __future__ import annotations

from functools import lru_cache
import re
from typing import Optional, Sequence

from .models import HelperSpec, SkillSpec
from .detectors import (
    is_merge_request, is_aggregate_request, is_statistical_request,
    is_schedule_request, is_scan_request,
    is_rank_request, is_financial_ratio_request, is_proportion_request,
    is_highlight_request,
    is_fill_missing, is_multi_key_join, is_key_based_join,
    is_time_series, is_regression, is_correlation, is_cycle_detection,
    is_target_feature_correlation,
    is_dependency_schedule, is_missing_data_scan, is_allocation,
    is_weighted_scoring, is_ratio_computation, is_share_computation,
    is_cash_flow_efficiency, is_financial_dashboard, is_inventory_policy,
    is_relational_assignment_schedule, is_region_growth_chart,
    is_market_share_shipment, is_region_share_cost,
    is_two_dimension_mean_count_summary_helper, is_multi_source_group_comparison_helper,
    is_multi_source_utilisation_summary_helper,
)
from .strategies import (
    MERGE_STRATEGY, AGGREGATE_STRATEGY, STATISTICAL_STRATEGY,
    SCHEDULE_STRATEGY, SCAN_STRATEGY,
    RANK_STRATEGY, FINANCIAL_STRATEGY, PROPORTION_STRATEGY,
    HIGHLIGHT_STRATEGY,
)


@lru_cache(maxsize=1)
def _skill_specs() -> tuple[SkillSpec, ...]:
    return (
        SkillSpec(
            name="merge",
            detector=is_merge_request,
            strategy_doc=MERGE_STRATEGY,
            helpers=(
                HelperSpec("fill_missing_from_reference",
                           description="Fill missing values from a reference table",
                           sub_detector=is_fill_missing),
                HelperSpec("build_multi_key_relational_join_report",
                           self_loading=True,
                           description="Join tables on multiple shared keys",
                           sub_detector=is_multi_key_join),
                HelperSpec("build_relational_join_enrichment_report",
                           self_loading=True,
                           description="Join tables on a shared key column",
                           sub_detector=is_key_based_join),
                HelperSpec("build_multi_source_group_comparison_report",
                           self_loading=True,
                           description="Join two related operational tables and produce grouped comparison summaries",
                           sub_detector=is_multi_source_group_comparison_helper),
                HelperSpec("concat_tables_with_same_headers",
                           description="Stack tables with identical columns"),
            ),
        ),
        SkillSpec(
            name="aggregate",
            detector=is_aggregate_request,
            strategy_doc=AGGREGATE_STRATEGY,
            helpers=(
                HelperSpec("build_region_growth_analysis",
                           description="Compute regional averages/growth and create a chart",
                           sub_detector=is_region_growth_chart),
                HelperSpec("build_two_dimension_mean_count_summary_report",
                           self_loading=True,
                           description="Build a two-dimension mean-and-count summary table from one dataset",
                           sub_detector=is_two_dimension_mean_count_summary_helper),
                HelperSpec("build_multi_source_utilisation_summary_report",
                           self_loading=True,
                           description="Aggregate multi-source utilisation ratios and return threshold-based highlight rows",
                           sub_detector=is_multi_source_utilisation_summary_helper),
                HelperSpec("build_time_series_aggregation_report",
                           self_loading=True,
                           description="Aggregate by time period (month, quarter, year)",
                           sub_detector=is_time_series),
                HelperSpec("build_grouped_aggregation_ranking_report",
                           self_loading=True,
                           description="Group by categories and aggregate with ranking"),
            ),
        ),
        SkillSpec(
            name="statistical",
            detector=is_statistical_request,
            strategy_doc=STATISTICAL_STRATEGY,
            helpers=(
                HelperSpec("fit_linear_regression_weights",
                           description="Fit linear regression coefficients",
                           sub_detector=is_regression),
                HelperSpec("compute_feature_correlations",
                           description="Compute feature-to-target correlations",
                           sub_detector=is_target_feature_correlation),
                HelperSpec("build_correlation_matrix_table",
                           description="Compute pairwise correlation matrix",
                           sub_detector=is_correlation),
                HelperSpec("build_cycle_detection_report",
                           description="Detect cycles in directed graphs",
                           sub_detector=is_cycle_detection),
            ),
        ),
        SkillSpec(
            name="schedule",
            detector=is_schedule_request,
            strategy_doc=SCHEDULE_STRATEGY,
            helpers=(
                HelperSpec("build_dependency_schedule",
                           description="Schedule tasks respecting dependency order",
                           sub_detector=is_dependency_schedule),
                HelperSpec("build_capacity_constrained_allocation_report",
                           self_loading=True,
                           description="Allocate entities to resources with capacity limits",
                           sub_detector=is_allocation),
                HelperSpec("build_relational_assignment_schedule_report",
                           self_loading=True,
                           description="Build assignment schedule from relational tables",
                           sub_detector=is_relational_assignment_schedule),
            ),
        ),
        SkillSpec(
            name="scan",
            detector=is_scan_request,
            output_mode="text",
            strategy_doc=SCAN_STRATEGY,
            helpers=(
                HelperSpec("build_missing_data_report",
                           self_loading=True,
                           description="Scan for missing values and report findings",
                           sub_detector=is_missing_data_scan),
                HelperSpec("build_room_format_report",
                           self_loading=True,
                           description="Check identifier format consistency"),
            ),
        ),
        SkillSpec(
            name="rank",
            detector=is_rank_request,
            strategy_doc=RANK_STRATEGY,
            helpers=(
                # compute_weighted_score is the primary enforced helper.
                # add_rank_column is a utility called after scoring; it is
                # available in the sandbox and shown in the strategy_doc but
                # is not a select_helper candidate (helpers are alternatives,
                # not sequential steps).
                HelperSpec("compute_weighted_score",
                           description="Compute weighted composite score across multiple columns"),
            ),
        ),
        SkillSpec(
            name="financial",
            detector=is_financial_ratio_request,
            strategy_doc=FINANCIAL_STRATEGY,
            helpers=(
                HelperSpec("build_cash_flow_efficiency_report",
                           self_loading=True,
                           description="Compute operating cash flow efficiency and free cash flow from financial statements",
                           sub_detector=is_cash_flow_efficiency),
                HelperSpec("build_financial_dashboard_report",
                           self_loading=True,
                           description="Build a period-level financial dashboard from complementary monthly sources",
                           sub_detector=is_financial_dashboard),
                HelperSpec("build_inventory_eoq_report",
                           self_loading=True,
                           description="Build EOQ, reorder-point, and sensitivity scenario tables from an inventory parameter sheet",
                           sub_detector=is_inventory_policy),
                HelperSpec("compute_ratio_column",
                           description="Add a ratio column (numerator / denominator)",
                           sub_detector=is_ratio_computation),
            ),
        ),
        SkillSpec(
            name="proportion",
            detector=is_proportion_request,
            strategy_doc=PROPORTION_STRATEGY,
            helpers=(
                HelperSpec("build_region_share_cost_report",
                           self_loading=True,
                           description="Build a regional population-share and expenditure-per-person summary",
                           sub_detector=is_region_share_cost),
                HelperSpec("build_weighted_share_value_report",
                           description="Estimate brand shipments from market share and total shipment tables",
                           sub_detector=is_market_share_shipment),
                HelperSpec("compute_percentage_share",
                           description="Add a percentage share column (value / total * 100)",
                           sub_detector=is_share_computation),
            ),
        ),
        SkillSpec(
            name="highlight",
            detector=is_highlight_request,
            strategy_doc=HIGHLIGHT_STRATEGY,
            helpers=(),
        ),
    )


_SKILL_PRIORITY = {
    "schedule": 70,
    "statistical": 60,
    "financial": 50,
    "proportion": 45,
    "merge": 40,
    "aggregate": 30,
    "rank": 20,
    "scan": 10,
    "highlight": 0,
}


def all_skills() -> Sequence[SkillSpec]:
    return _skill_specs()


def detect_skill(user_question: str) -> Optional[SkillSpec]:
    """Return the highest-priority matching skill, or None. Use detect_skills() for multi-skill."""
    matched = detect_skills(user_question)
    if not matched:
        return None
    best_skill = matched[0]
    best_explicit = False
    best_priority = _SKILL_PRIORITY.get(best_skill.name, -1)
    for skill in matched:
        _, explicit = _select_helper_with_reason(skill, user_question)
        priority = _SKILL_PRIORITY.get(skill.name, -1)
        if explicit and not best_explicit:
            best_skill = skill
            best_explicit = True
            best_priority = priority
            continue
        if explicit == best_explicit and priority > best_priority:
            best_skill = skill
            best_priority = priority
    return best_skill


def detect_skills(user_question: str) -> list[SkillSpec]:
    """Return all matching skills. A question may belong to multiple skills."""
    matched = [skill for skill in all_skills() if skill.detector(user_question)]
    if not matched:
        from .semantic_router import semantic_detect_skills

        matched = [match.skill for match in semantic_detect_skills(user_question)]
    return sorted(matched, key=lambda skill: _SKILL_PRIORITY.get(skill.name, -1), reverse=True)


def _select_helper_with_reason(skill: SkillSpec, user_question: str) -> tuple[Optional[HelperSpec], bool]:
    def _find_helper(name: str) -> Optional[HelperSpec]:
        return next((helper for helper in skill.helpers if helper.name == name), None)

    def _is_downstream_analytic_join_report(question: str) -> bool:
        q = (question or "").lower()
        if not any(marker in q for marker in ("join", "merge", "using storeid", "using productid", "using id", "using the")):
            return False
        if re.search(r"\b(single|one|combined|merged)\s+(file|table|spreadsheet)\b", q):
            return False
        if not any(marker in q for marker in ("target", "multiple sheets", "three sheets", "two sheets", "sheets:", "category summary")):
            return False
        downstream_groups = 0
        if any(marker in q for marker in ("compute", "calculate", "derive", "net revenue", "gross profit", "ratio", "share")):
            downstream_groups += 1
        if any(marker in q for marker in ("aggregate", "group by", "grouped by", " by region", " by category", "for each")):
            downstream_groups += 1
        if any(marker in q for marker in ("compare", "target", "variance", "against")):
            downstream_groups += 1
        if any(marker in q for marker in ("leaderboard", "top ", "rank", "ranking")):
            downstream_groups += 1
        if any(marker in q for marker in ("summary", "multiple sheets", "three sheets", "two sheets", "sheets:")):
            downstream_groups += 1
        return downstream_groups >= 2

    def _merge_default_helper(question: str) -> Optional[HelperSpec]:
        q = (question or "").lower()
        same_schema_markers = (
            "append",
            "concatenate",
            "concat",
            "stack",
            "stacking",
            "union",
            "combine all",
            "combine the monthly",
            "same headers",
            "same schema",
            "first half",
            "second half",
        )
        summary_followup_markers = (
            "average",
            "mean",
            "total",
            "sum",
            "highlight",
            "highest",
            "lowest",
            "max",
            "min",
        )
        explicit_join_markers = (
            "using the",
            "based on",
            "common key",
            "shared key",
            "shared column",
            "matching",
            " id",
            "column",
        )
        if any(marker in q for marker in same_schema_markers):
            return _find_helper("concat_tables_with_same_headers"), False
        if any(marker in q for marker in summary_followup_markers) and not any(marker in q for marker in explicit_join_markers):
            return _find_helper("concat_tables_with_same_headers"), False
        return (
            _find_helper("build_relational_join_enrichment_report") or _find_helper("concat_tables_with_same_headers"),
            False,
        )

    fallback = None
    for helper in skill.helpers:
        if helper.sub_detector is not None:
            if helper.sub_detector(user_question):
                if helper.name == "build_relational_join_enrichment_report" and _is_downstream_analytic_join_report(user_question):
                    continue
                return helper, True
        elif fallback is None:
            fallback = helper
    if skill.name == "merge":
        if _is_downstream_analytic_join_report(user_question):
            return None, False
        return _merge_default_helper(user_question)
    return fallback, False


def select_helper(skill: SkillSpec, user_question: str) -> Optional[HelperSpec]:
    helper, _ = _select_helper_with_reason(skill, user_question)
    if helper is None:
        from .semantic_router import semantic_select_helper

        helper = semantic_select_helper(skill, user_question)
    return helper
