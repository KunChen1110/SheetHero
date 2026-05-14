"""Keyword-based detectors for skills and helper sub-selection.

Each public function returns True when the user question matches the
corresponding skill or helper. No LLM calls — pure string matching.
"""

from __future__ import annotations

import re

from ..stages.execution.analysis.task_intents import (
    is_cash_flow_efficiency_request,
    is_region_growth_chart_request,
    is_relational_assignment_schedule_request,
    is_weighted_share_value_alignment_request,
)


# ---------------------------------------------------------------------------
# Skill-level detectors
# ---------------------------------------------------------------------------

def is_merge_request(q: str) -> bool:
    q = q.lower()
    single_table_column_ops = (
        "within one table",
        "into one column",
        "columns in the table",
        "columns within",
        "two columns",
        "first name and last name",
        "full address",
    )
    if any(marker in q for marker in single_table_column_ops):
        return False
    fill_words = ("fill missing", "fill the missing", "fill any missing", "complete missing",
                  "populate missing", "use the reference", "use another file")
    if any(w in q for w in fill_words):
        return True
    # Explicit multi-source patterns — no join verb required.
    # These are the safest indicators of cross-table/cross-file intent.
    both_multi_patterns = (
        "both files", "both tables", "both sheets", "both workbooks", "both datasets",
        "multiple files", "multiple tables", "multiple sheets", "multiple workbooks",
        "from both", "across both",
        "two files", "two tables", "two workbooks", "two spreadsheets", "two datasets",
        "another file", "other file", "the second file", "second file",
    )
    if any(p in q for p in both_multi_patterns):
        return True
    # Join verb must appear alongside a PLURAL data-source noun to avoid false
    # positives for single-table column/cell operations (e.g. "merge cells",
    # "combine columns in the table", "stack bar chart in the spreadsheet").
    # Singular nouns ("table", "sheet") are intentionally excluded here.
    join_words = ("merge", "merging", "join", "joining", "combine", "combining",
                  "concatenate", "link", "enrich", "append", "appending",
                  "stack", "stacking", "union", "stitch", "stitching")
    plural_structure_words = ("files", "tables", "sheets", "datasets",
                              "workbooks", "spreadsheets")
    if any(w in q for w in join_words) and any(w in q for w in plural_structure_words):
        return True
    singular_structure_words = (
        " file", " table", " sheet", " dataset", " workbook",
        " data", " information", " details", " records",
    )
    join_context_words = ("using", "based on", "on the", "common key", "shared key", " id", " column")
    if any(w in q for w in join_words):
        if (" with " in q or any(word in q for word in join_context_words)) and any(
            word in q for word in singular_structure_words
        ):
            return True
    return False


def is_aggregate_request(q: str) -> bool:
    q = q.lower()
    if is_region_growth_chart_request(q):
        return True
    if is_two_dimension_mean_count_summary(q) or is_multi_source_utilisation_summary(q):
        return True
    agg_words = ("average", "mean", " sum ", "total ", "totals", "median",
                 "summary", "summarize", "summarise", "breakdown", "stats", "statistics")
    # Only explicit grouping phrases — avoid overly broad " by " which collides
    # with domain phrases like "efficiency … by calculating" or "by region".
    group_words = ("group by", "grouped by", "group the", "grouped the",
                   "by department", "by year", "by month", "by quarter",
                   "by semester", "by brand", "by category",
                   "by store", "by type", "by product", "by region",
                   "by country", "by team", "by class", "by subject",
                   "per department", "per year", "per month", "per quarter",
                   "per semester", "per brand", "per category",
                   "per store", "per type", "per product", "per region",
                   "per country", "per team", "per class", "per subject",
                   "by day", "per day", "daily", "each day",
                   "by week", "per week", "weekly",
                   "by hour", "per hour", "hourly",
                   "for each department", "for each category", "for each product",
                   "for each region", "for each store", "for each team",
                   "for each day", "for each week", "for each student",
                   "for each class", "for each subject")
    sort_words = ("sort", "descending", "ascending", "highest", "lowest", "top ")
    # Temporal group qualifiers: "in November", "for Q3", "during January", etc.
    # Uses prefix+name patterns to avoid false positives (e.g. "may" as modal verb).
    _month_names = (
        "january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "november", "december",
        "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "oct", "nov", "dec",
    )
    _temporal_prefixes = ("in ", "for ", "during ", "of ")
    # "in November", "for November" etc. — requires prefix to avoid "may" as modal verb
    has_temporal_group = any(
        f"{prefix}{month}" in q
        for prefix in _temporal_prefixes
        for month in _month_names
    ) or any(w in q for w in ("q1", "q2", "q3", "q4", "quarter", "semester"))
    # Unambiguous full month names can appear without prefix (e.g. "November stats").
    # Exclude "march" (common verb) and "august" (common adjective) to avoid false positives
    # like "march toward the total" or "august summary of the data".
    _unambiguous_months = (
        "january", "february", "april", "june", "july",
        "september", "october", "november", "december",
    )
    if not has_temporal_group:
        has_temporal_group = any(month in q for month in _unambiguous_months)
    has_agg = any(w in q for w in agg_words)
    has_group = any(w in q for w in group_words)
    has_sort = any(w in q for w in sort_words)
    return has_agg and (has_group or has_sort or has_temporal_group)


def is_statistical_request(q: str) -> bool:
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


def is_schedule_request(q: str) -> bool:
    q = q.lower()
    if is_relational_assignment_schedule_request(q):
        return True
    if "dependency" in q or "dependencies" in q or "depends on" in q:
        return True
    if "topological" in q or "dag" in q:
        return True
    if ("schedule" in q or "scheduling" in q) and (
        "start time" in q or "end time" in q or "task" in q
        or "assigned" in q or "meeting slot" in q or "availability" in q
    ):
        return True
    if "roster" in q and any(w in q for w in ("advisor", "advisee", "slot", "venue", "availability")):
        return True
    alloc_words = ("allocate", "assign", "distribute", "place", "seat")
    capacity_words = ("capacity", "capacities", "available seats", "remaining capacity", "slots", "seat limit", "max students", "quota")
    return any(w in q for w in alloc_words) and any(w in q for w in capacity_words)


def is_scan_request(q: str) -> bool:
    q = q.lower()
    missing_words = ("missing data", "missing values", "missing entries",
                     "blank values", "empty values", "null values",
                     "have missing", "has missing", "with missing",
                     "contain missing", "are missing", "any missing")
    action_words = ("identify", "find", "locate", "report", "scan",
                    "check", "detect", "audit", "inspect", "which", "show")
    # "format" alone is too broad — require identifier/code-like context or explicit inconsistency wording.
    format_words = (
        "inconsistenc",
        "inconsistent",
        "identifier",
        "code format",
        "format inconsistenc",
        "formatting inconsistenc",
        "naming inconsistenc",
        "standardiz",
        "normaliz",
        "variant",
        "same value",
        "same identifier",
    )
    has_missing = any(w in q for w in missing_words)
    has_format = any(w in q for w in format_words) and any(
        marker in q
        for marker in (
            "format",
            "code",
            "codes",
            "identifier",
            "identifiers",
            "naming",
            "spelling",
            "standard",
            "normalize",
            "normalise",
            "standardize",
            "standardise",
            "inconsistent",
        )
    )
    has_action = any(w in q for w in action_words)
    return (has_missing or has_format) and has_action


# ---------------------------------------------------------------------------
# Helper sub-detectors  (used inside HelperSpec.sub_detector)
# ---------------------------------------------------------------------------

def is_fill_missing(q: str) -> bool:
    q = q.lower()
    return any(w in q for w in (
        "fill missing", "fill the missing", "fill any missing", "complete missing",
        "populate missing", "use the reference", "use another file",
    ))


def is_financial_dashboard(q: str) -> bool:
    q = q.lower()
    metric_markers = (
        "gross profit",
        "net profit",
        "gross profit margin",
        "net profit margin",
        "customer acquisition cost",
        "marketing efficiency ratio",
        "dashboard",
        "actuals to targets",
    )
    return (
        "dashboard" in q
        and any(marker in q for marker in ("target", "targets", "actuals"))
        and sum(1 for marker in metric_markers if marker in q) >= 2
    ) or (
        sum(1 for marker in metric_markers if marker in q) >= 2
        and "target" in q
    )


def is_inventory_policy(q: str) -> bool:
    q = q.lower()
    return (
        "eoq" in q
        or (
            "reorder point" in q
            and any(marker in q for marker in ("orders per year", "cycle time", "annual cost"))
        )
        or (
            "sensitivity analysis" in q
            and any(marker in q for marker in ("order quantity", "annual demand", "reorder point"))
        )
    )


def is_region_share_and_cost_report(q: str) -> bool:
    q = q.lower()
    population_markers = (
        "regional population",
        "population by region",
        "population",
        "count by region",
        "people by region",
    )
    cost_markers = (
        "healthcare expenditure",
        "health care expenditure",
        "regional expenditure",
        "cost by region",
        "expenditure per person",
        "average expenditure per person",
        "usd per person",
    )
    share_markers = (
        "share of global",
        "share of the global",
        "global share",
        "percentage of global",
    )
    return (
        "region" in q
        and any(marker in q for marker in population_markers)
        and any(marker in q for marker in cost_markers)
        and any(marker in q for marker in share_markers)
    )


def is_two_dimension_mean_count_summary(q: str) -> bool:
    q = q.lower()
    return (
        any(marker in q for marker in ("average", "avg", "mean"))
        and any(marker in q for marker in ("count", "number of", "review count"))
        and any(marker in q for marker in ("for each", "group by", "grouped by", "by "))
        and any(marker in q for marker in ("type", "category", "brand", "country", "region", "department"))
    )


def is_multi_source_group_comparison_report(q: str) -> bool:
    q = q.lower()
    return (
        any(marker in q for marker in ("merge", "join", "combine"))
        and any(marker in q for marker in ("weekly sales", "sales", "features", "metrics", "information"))
        and any(marker in q for marker in ("type", "category", "group"))
        and any(marker in q for marker in ("holiday", "non-holiday", "non holiday"))
        and any(marker in q for marker in ("temperature", "fuel price", "fuel"))
    )


def is_multi_source_utilisation_summary(q: str) -> bool:
    q = q.lower()
    department_utilisation = (
        any(marker in q for marker in ("utilisation", "utilization"))
        and "department" in q
        and "service" in q
        and "staff" in q
    )
    university_utilisation = (
        any(marker in q for marker in ("utilisation", "utilization"))
        and "section" in q
        and "instructor" in q
        and "room" in q
        and any(marker in q for marker in ("fill rate", "waitlist rate", "waitlisted count", "scheduled hours"))
    )
    return department_utilisation or university_utilisation


def is_multi_key_join(q: str) -> bool:
    q = q.lower()
    if any(w in q for w in (
        "composite key", "multi-key", "multiple keys", "two keys", "shared keys",
    )):
        return True
    return re.search(r"\bshared\s+[\w\s]+?\s+and\s+[\w\s]+?\s+keys?\b", q) is not None


def is_key_based_join(q: str) -> bool:
    q = q.lower()
    if is_multi_source_group_comparison_report(q) or is_multi_source_utilisation_summary(q):
        return False
    key_hints = ("student id", "employee id", "customer id", "order id",
                 "using the", "based on", "on the", "common key",
                 "shared column", "matching", "id column")
    if any(w in q for w in key_hints):
        return True
    return re.search(r"\b(?:using|on|by)\s+[a-z0-9_ ]*id\b", q) is not None


def is_time_series(q: str) -> bool:
    q = q.lower()
    period_words = ("monthly", "by month", "per month", "yearly", "by year",
                    "per year", "quarterly", "by quarter", "annually",
                    "by semester", "by term", "yyyy-mm", "year-month",
                    "time period", "date column", "latest 5 years",
                    "last 5 years", "past 3 years", "last 3 years", "last 10 years")
    return any(w in q for w in period_words)


def is_regression(q: str) -> bool:
    q = q.lower()
    if "correlation coefficient" in q:
        return False
    return "regression" in q or "coefficient" in q or "weight" in q or (
        "predict" in q and ("using" in q or "from" in q)
    )


def is_correlation(q: str) -> bool:
    return "correlation" in q.lower()


def is_target_feature_correlation(q: str) -> bool:
    q = q.lower()
    if "correlation matrix" in q:
        return False
    if "correlation coefficient" in q:
        return True
    return (
        "correlation" in q
        and any(marker in q for marker in ("survival", "target", "other factors", "feature"))
        and any(marker in q for marker in ("between", "with"))
    )


def is_cycle_detection(q: str) -> bool:
    q = q.lower()
    return "cycle" in q or "circular" in q


def is_dependency_schedule(q: str) -> bool:
    q = q.lower()
    return ("dependency" in q or "dependencies" in q or "depends on" in q
            or "topological" in q or "dag" in q)


def is_missing_data_scan(q: str) -> bool:
    q = q.lower()
    return any(w in q for w in ("missing data", "missing values", "blank values",
                                 "null values", "empty values"))


def is_allocation(q: str) -> bool:
    q = q.lower()
    return any(w in q for w in ("allocate", "capacity", "capacities", "available seats", "remaining capacity", "slots", "seat limit"))


def is_highlight_request(q: str) -> bool:
    """Tasks that explicitly ask to color-mark or highlight rows in output."""
    q = q.lower()
    if is_multi_source_utilisation_summary(q):
        return False
    return any(w in q for w in (
        "highlight", "highlighted", "color", "colour",
        "mark in red", "mark the", "in red",
        "bold", "bold the",
    ))


def is_rank_request(q: str) -> bool:
    """Weighted or multi-criteria ranking (not a simple single-column sort)."""
    q = q.lower()
    weighted = ("weighted score", "weighted criteria", "composite score",
                "overall score", "combined score", "rank by weighted",
                "score and rank", "rank candidates", "rank employees",
                "rank applicants", "rank suppliers", "rank products by score",
                "score each", "scoring criteria")
    if any(w in q for w in weighted):
        return True
    if ("rank" in q or "score" in q) and re.search(r"\b\d+(?:\.\d+)?\s*\*\s*[a-z]", q):
        return True
    return False


def is_financial_ratio_request(q: str) -> bool:
    """Ratio computation or year-over-year financial comparison."""
    q = q.lower()
    ratio_words = ("efficiency ratio", "ocf", "free cash flow", "cash flow efficiency",
                   "operating cash flow", "net income ratio", "profit margin",
                   "return on", "as a ratio", "divide by revenue", "over net income")
    yoy_words = ("year over year", "yoy", "year-on-year", "year-to-year",
                 "annual growth rate", "yearly comparison", "year-by-year")
    return (
        any(w in q for w in ratio_words)
        or any(w in q for w in yoy_words)
        or is_financial_dashboard(q)
        or is_inventory_policy(q)
    )


def is_proportion_request(q: str) -> bool:
    """Percentage share or distribution breakdown."""
    q = q.lower()
    if is_weighted_share_value_alignment_request(q):
        return True
    if is_region_share_and_cost_report(q):
        return True
    prop_words = ("percentage of total", "share of total", "proportion of",
                  "percentage share", "market share", "contribution to total",
                  "as a percentage", "as a proportion", "breakdown by share",
                  "distribution by percentage", "% of total", "percent of total",
                  "global share", "relative share")
    return any(w in q for w in prop_words)


# ---------------------------------------------------------------------------
# Sub-detectors for new skill helpers
# ---------------------------------------------------------------------------

def is_weighted_scoring(q: str) -> bool:
    q = q.lower()
    return any(w in q for w in ("weighted score", "weighted criteria",
                                 "composite score", "score each", "scoring criteria"))


def is_ratio_computation(q: str) -> bool:
    q = q.lower()
    if is_cash_flow_efficiency_request(q):
        return False
    return any(w in q for w in ("ratio", "efficiency", "ocf", "margin",
                                 "return on", "divided by", "over net income"))


def is_cash_flow_efficiency(q: str) -> bool:
    return is_cash_flow_efficiency_request(q)


def is_share_computation(q: str) -> bool:
    q = q.lower()
    return any(w in q for w in ("share", "proportion", "percentage of",
                                 "% of total", "contribution"))


def is_relational_assignment_schedule(q: str) -> bool:
    return is_relational_assignment_schedule_request(q)


def is_region_growth_chart(q: str) -> bool:
    return is_region_growth_chart_request(q)


def is_market_share_shipment(q: str) -> bool:
    return is_weighted_share_value_alignment_request(q)


def is_region_share_cost(q: str) -> bool:
    return is_region_share_and_cost_report(q)


def is_two_dimension_mean_count_summary_helper(q: str) -> bool:
    return is_two_dimension_mean_count_summary(q)


def is_multi_source_group_comparison_helper(q: str) -> bool:
    return is_multi_source_group_comparison_report(q)


def is_multi_source_utilisation_summary_helper(q: str) -> bool:
    return is_multi_source_utilisation_summary(q)
