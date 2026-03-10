"""Pure task-intent detectors for execution routing.

These helpers are intentionally stateless so they can be reused by the
execution runtime without inflating the core loop implementation.
"""

from __future__ import annotations

import re


def is_regression_request(user_question: str) -> bool:
    q = (user_question or "").lower()
    markers = ("regression", "coefficient", "coefficients", "weight", "weights", "predict")
    return any(m in q for m in markers)


def is_simple_horizontal_merge_request(user_question: str) -> bool:
    q = (user_question or "").lower()
    return bool(re.search(r"merge the (two|three|four) files into a single file", q))


def is_fill_missing_request(user_question: str) -> bool:
    q = (user_question or "").lower()
    return ("fill any missing" in q or "fill missing" in q) and "using" in q


def is_missing_data_scan_request(user_question: str) -> bool:
    q = (user_question or "").lower()
    return "missing data" in q and ("identify where" in q or "where values are missing" in q or "check the file" in q)


def is_room_inconsistency_request(user_question: str) -> bool:
    q = (user_question or "").lower()
    return "room identifiers" in q or ("room" in q and "inconsistenc" in q) or "c80" in q or "c 80" in q


def is_region_growth_chart_request(user_question: str) -> bool:
    q = (user_question or "").lower()
    return "line chart" in q and "growth rate" in q and "region" in q and ("penetration" in q or "internet" in q)


def is_correlation_matrix_request(user_question: str) -> bool:
    q = (user_question or "").lower()
    return "correlation matrix" in q or ("matrix" in q and "correlation" in q)


def is_cycle_detection_request(user_question: str) -> bool:
    q = (user_question or "").lower()
    return "contain a cycle" in q or "contains a cycle" in q or ("cycle" in q and "graph" in q)


def is_financial_dashboard_request(user_question: str) -> bool:
    q = (user_question or "").lower()
    markers = (
        "gross profit",
        "net profit",
        "gross profit margin",
        "net profit margin",
        "customer acquisition cost",
        "marketing efficiency ratio",
    )
    return sum(1 for marker in markers if marker in q) >= 4


def is_candidate_screening_request(user_question: str) -> bool:
    q = (user_question or "").lower()
    markers = (
        "rank the candidates",
        "candidate information",
        "working experience",
        "number of skills",
        "personality score",
    )
    return sum(1 for marker in markers if marker in q) >= 4


def is_inventory_eoq_request(user_question: str) -> bool:
    q = (user_question or "").lower()
    return ("economic order quantity" in q or "eoq" in q) and "reorder point" in q


def is_hospital_utilisation_request(user_question: str) -> bool:
    q = (user_question or "").lower()
    markers = ("staff utilisation", "service utilisation", "patient load", "department")
    return sum(1 for marker in markers if marker in q) >= 3


def is_market_share_shipment_request(user_question: str) -> bool:
    q = (user_question or "").lower()
    markers = ("market share", "smartphone", "shipment", "overlapping time period")
    return sum(1 for marker in markers if marker in q) >= 3


def is_cash_flow_efficiency_request(user_question: str) -> bool:
    q = (user_question or "").lower()
    markers = ("operating cash flow", "net income", "free cash flow", "cash flow efficiency")
    return sum(1 for marker in markers if marker in q) >= 2


def is_diabetes_region_request(user_question: str) -> bool:
    q = (user_question or "").lower()
    markers = ("diabetics worldwide by region", "share of global", "avg expenditure per person", "diabetes-related health expenditure")
    return sum(1 for marker in markers if marker in q) >= 2


def is_mobile_reviews_summary_request(user_question: str) -> bool:
    q = (user_question or "").lower()
    markers = ("smartphone reviews", "average rating", "number of reviews", "country", "brand")
    return sum(1 for marker in markers if marker in q) >= 4


def is_store_feature_analysis_request(user_question: str) -> bool:
    q = (user_question or "").lower()
    markers = ("store type", "holiday", "weekly sales", "feature1", "feature2")
    return sum(1 for marker in markers if marker in q) >= 3


def is_ecommerce_merge_request(user_question: str) -> bool:
    q = (user_question or "").lower()
    markers = ("e-commerce", "customers", "orders", "payments", "reviews", "products")
    return sum(1 for marker in markers if marker in q) >= 4


def is_same_schema_merge_summary_request(user_question: str) -> bool:
    q = (user_question or "").lower()
    return (
        "merge" in q
        and ("average" in q or "total" in q or "sum" in q)
        and ("highlight" in q or "red" in q or "most" in q or "max" in q)
    )


def is_dependency_schedule_request(user_question: str) -> bool:
    q = (user_question or "").lower()
    if "dependency" in q or "dependencies" in q or "topological" in q or "dag" in q:
        return True
    if "depends on" in q or "task id" in q:
        return True
    if ("schedule" in q or "scheduling" in q) and (
        "start time" in q
        or "end time" in q
        or "depends on" in q
        or "task id" in q
    ):
        return True
    return False


def header_is_target_like(header: str) -> bool:
    h = (header or "").strip().lower()
    target_markers = ("sales", "target", "label", "outcome", "revenue", "y")
    return any(m in h for m in target_markers)


def header_is_non_feature_like(header: str) -> bool:
    h = (header or "").strip().lower()
    non_feature_markers = ("id", "date", "time", "timestamp", "note", "comment")
    return any(m in h for m in non_feature_markers)
