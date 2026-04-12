"""Skill registry: builds SkillSpec list and provides detect/select helpers."""

from __future__ import annotations

from functools import lru_cache
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
    is_cash_flow_efficiency,
    is_relational_assignment_schedule, is_region_growth_chart,
    is_market_share_shipment,
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
                HelperSpec("build_market_share_shipment_report",
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


def all_skills() -> Sequence[SkillSpec]:
    return _skill_specs()


def detect_skill(user_question: str) -> Optional[SkillSpec]:
    """Return the first matching skill, or None. Use detect_skills() for multi-skill."""
    for skill in all_skills():
        if skill.detector(user_question):
            return skill
    return None


def detect_skills(user_question: str) -> list[SkillSpec]:
    """Return all matching skills. A question may belong to multiple skills."""
    return [skill for skill in all_skills() if skill.detector(user_question)]


def select_helper(skill: SkillSpec, user_question: str) -> Optional[HelperSpec]:
    fallback = None
    for helper in skill.helpers:
        if helper.sub_detector is not None:
            if helper.sub_detector(user_question):
                return helper
        elif fallback is None:
            fallback = helper
    return fallback
