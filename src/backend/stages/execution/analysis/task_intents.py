"""Pure task-intent detectors for execution routing.

These helpers are intentionally stateless so they can be reused by the
execution runtime without inflating the core loop implementation.
"""

from __future__ import annotations

import re


def is_regression_request(user_question: str) -> bool:
    q = (user_question or "").lower()
    markers = ("regression", "coefficient", "coefficients", "weight", "weights")
    if any(m in q for m in markers):
        return True
    if "predict" in q and ("using" in q or "from" in q):
        return True
    if "fit a model" in q and ("predict" in q or "target" in q or "outcome" in q):
        return True
    if ("influence" in q or "affect" in q) and ("score" in q or "sales" in q or "outcome" in q or "target" in q):
        return True
    return False


def is_simple_horizontal_merge_request(user_question: str) -> bool:
    q = (user_question or "").lower()
    return bool(re.search(r"merge the (two|three|four) files into a single file", q))


def is_relational_join_request(user_question: str) -> bool:
    q = (user_question or "").lower()
    join_markers = (
        "merge",
        "join",
        "combine",
        "match",
        "link",
        "enrich",
    )
    structure_markers = (
        "file",
        "files",
        "table",
        "tables",
        "sheet",
        "sheets",
        "dataset",
        "datasets",
    )
    if not any(marker in q for marker in join_markers):
        return False
    if not any(marker in q for marker in structure_markers):
        return False
    if "same schema" in q or "fill missing" in q or "missing value" in q:
        return False
    if "correlation" in q or "regression" in q or "cycle" in q or "depends on" in q:
        return False
    return True


def is_multi_key_relational_join_request(user_question: str) -> bool:
    q = (user_question or "").lower()
    if not is_relational_join_request(user_question):
        return False

    explicit_markers = (
        "composite key",
        "multi-key",
        "multi key",
        "multiple keys",
        "two keys",
        "shared keys",
    )
    if any(marker in q for marker in explicit_markers):
        return True

    pattern = re.compile(
        r"(?:using|on|based on|matching on|matched by|join on|merge on)\s+([a-z0-9 _/-]{1,80})\s+and\s+([a-z0-9 _/-]{1,80})"
    )
    keyish_tokens = (
        "id",
        "code",
        "number",
        "date",
        "day",
        "month",
        "year",
        "term",
        "semester",
        "quarter",
        "section",
        "class",
        "group",
        "session",
        "slot",
        "room",
        "program",
        "course",
    )
    for match in pattern.finditer(q):
        left = match.group(1).strip()
        right = match.group(2).strip()
        if any(token in left for token in keyish_tokens) and any(token in right for token in keyish_tokens):
            return True
    if "both" in q and any(token in q for token in keyish_tokens) and ("using" in q or "based on" in q or "matched by" in q):
        return True
    return False


def is_relational_assignment_schedule_request(user_question: str) -> bool:
    q = (user_question or "").lower()
    legacy_markers = (
        "students and their tutors",
        "students and tutors",
        "students attending",
        "tutor meeting",
        "meeting time and location",
        "assigned tutor",
    )
    if sum(1 for marker in legacy_markers if marker in q) >= 2:
        return True

    assigned_markers = (
        "assigned tutor",
        "assigned professor",
        "assigned teacher",
        "assigned advisor",
        "assigned mentor",
        "assigned supervisor",
        "assigned instructor",
        "assigned room",
        "assigned seat",
        "assigned lab",
        "assigned group",
        "assigned session",
    )
    scheduling_markers = (
        "schedule",
        "meeting",
        "session",
        "time slot",
        "time",
        "day",
        "date",
        "location",
        "room",
        "seat",
        "lab",
        "office hour",
        "availability",
        "venue",
        "roster",
    )
    entity_markers = (
        "student",
        "students",
        "professor",
        "teacher",
        "tutor",
        "candidate",
        "participant",
        "attendee",
        "group",
        "advisee",
        "cohort",
    )
    return (
        any(marker in q for marker in assigned_markers)
        and any(marker in q for marker in scheduling_markers)
        and any(marker in q for marker in entity_markers)
    )


def is_capacity_constrained_allocation_request(user_question: str) -> bool:
    q = (user_question or "").lower()
    action_markers = (
        "allocate",
        "assign",
        "distribute",
        "place",
        "seat",
    )
    capacity_markers = (
        "capacity",
        "capacities",
        "slots",
        "seat limit",
        "seat limits",
        "seats available",
        "available seats",
        "max students",
        "max participants",
        "room capacity",
        "quota",
        "quotas",
        "remaining capacity",
        "remaining capacities",
        "remaining slots",
        "available slots",
        "available capacity",
        "supervision capacity",
    )
    resource_markers = (
        "room",
        "rooms",
        "classroom",
        "classrooms",
        "venue",
        "venues",
        "group",
        "groups",
        "section",
        "sections",
        "lab",
        "labs",
        "seat",
        "seats",
        "session",
        "sessions",
        "professor",
        "advisor",
        "mentor",
        "supervisor",
        "instructor",
        "resource",
        "resources",
    )
    entity_markers = (
        "student",
        "students",
        "candidate",
        "candidates",
        "participant",
        "participants",
        "attendee",
        "attendees",
        "applicant",
        "applicants",
        "team",
        "teams",
        "member",
        "members",
        "advisee",
        "advisees",
        "cohort",
        "cohorts",
    )
    if not any(marker in q for marker in action_markers):
        return False
    if not any(marker in q for marker in capacity_markers):
        return False
    if not any(marker in q for marker in resource_markers):
        return False
    if not any(marker in q for marker in entity_markers):
        return False
    if any(marker in q for marker in ("merge", "join", "correlation", "regression", "depends on")):
        return False
    return True


def is_fill_missing_request(user_question: str) -> bool:
    q = (user_question or "").lower()
    fill_markers = (
        "fill any missing",
        "fill missing",
        "fill the missing",
        "fill missing values",
        "fill missing data",
        "complete missing",
        "populate missing",
        "use the reference",
        "use another file to complete",
    )
    if not any(marker in q for marker in fill_markers):
        return False
    if "using" not in q and "from" not in q:
        return False
    reference_markers = (
        "reference file",
        "reference table",
        "another file",
        "another table",
        "shared",
        "lookup",
        "information from file",
        "information from another file",
        "using information from file",
        "using information from another file",
    )
    return any(marker in q for marker in reference_markers)


def is_missing_data_scan_request(user_question: str) -> bool:
    q = (user_question or "").lower()
    missing_markers = (
        "missing data",
        "missing values",
        "missing entries",
        "blank values",
        "empty values",
        "null values",
        "nulls",
    )
    action_markers = (
        "identify",
        "find",
        "locate",
        "report",
        "scan",
        "check",
        "detect",
        "audit",
    )
    if not any(marker in q for marker in missing_markers):
        return False
    return (
        any(marker in q for marker in action_markers)
        or "where values are missing" in q
        or "which fields are missing" in q
    )


def is_room_inconsistency_request(user_question: str) -> bool:
    q = (user_question or "").lower()
    return "room identifiers" in q or "room identifier" in q or "c80" in q or "c 80" in q


def is_region_growth_chart_request(user_question: str) -> bool:
    q = (user_question or "").lower()
    return "line chart" in q and "growth rate" in q and "region" in q and ("penetration" in q or "internet" in q)


def is_correlation_matrix_request(user_question: str) -> bool:
    q = (user_question or "").lower()
    if "correlation matrix" in q or ("matrix" in q and "correlation" in q):
        return True
    if "correlat" in q and any(marker in q for marker in ("between", "among", "across")):
        return True
    if ("relationship" in q or "related" in q) and "matrix" in q:
        return True
    return False


def is_cycle_detection_request(user_question: str) -> bool:
    q = (user_question or "").lower()
    return "contain a cycle" in q or "contains a cycle" in q or ("cycle" in q and "graph" in q)


def is_market_share_shipment_request(user_question: str) -> bool:
    q = (user_question or "").lower()
    markers = ("market share", "smartphone", "shipment", "overlapping time period")
    return sum(1 for marker in markers if marker in q) >= 3


def is_time_series_aggregation_request(user_question: str) -> bool:
    q = (user_question or "").lower()
    aggregate_markers = (
        "average",
        "mean",
        "sum",
        "total",
        "count",
        "median",
        "minimum",
        "maximum",
        "min",
        "max",
    )
    period_markers = (
        "monthly",
        "by month",
        "per month",
        "each month",
        "year-month",
        "yyyy-mm",
        "quarterly",
        "by quarter",
        "per quarter",
        "yearly",
        "by year",
        "per year",
    )
    time_window_markers = (
        "last 5 years",
        "last 3 years",
        "recent years",
        "latest years",
        "past 5 years",
        "past 3 years",
        "latest 5 years",
        "latest 3 years",
    )
    ordering_markers = ("sort", "rank", "ordered", "descending", "ascending")
    if not any(marker in q for marker in aggregate_markers):
        return False
    if not (any(marker in q for marker in period_markers) or any(marker in q for marker in time_window_markers)):
        return False
    if not any(marker in q for marker in ordering_markers):
        return False
    if any(marker in q for marker in ("date", "month", "year", "quarter", "time", "semester", "term")):
        return True
    return False


def is_grouped_aggregation_request(user_question: str) -> bool:
    q = (user_question or "").lower()
    aggregate_markers = (
        "average",
        "mean",
        "sum",
        "total",
        "count",
        "median",
        "minimum",
        "maximum",
        "min",
        "max",
    )
    grouping_markers = (
        "grouped by",
        "group by",
        "for each",
        "per ",
        " by ",
        "each ",
        "for every",
    )
    summary_markers = (
        "sort",
        "rank",
        "ordered",
        "descending",
        "ascending",
        "summary",
        "report",
        "for each",
    )
    if not any(marker in q for marker in aggregate_markers):
        return False
    if not any(marker in q for marker in grouping_markers):
        return False
    if "correlation" in q or "regression" in q or "depends on" in q or "cycle" in q:
        return False
    return any(marker in q for marker in summary_markers)


def is_cash_flow_efficiency_request(user_question: str) -> bool:
    q = (user_question or "").lower()
    markers = ("operating cash flow", "net income", "free cash flow", "cash flow efficiency")
    return sum(1 for marker in markers if marker in q) >= 2



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
    tokenized = re.sub(r"[_\W]+", " ", h, flags=re.UNICODE).split()
    target_markers = ("sales", "target", "label", "outcome", "revenue")
    if any(marker in h for marker in target_markers):
        return True
    return h == "y" or "y" in tokenized


def header_is_non_feature_like(header: str) -> bool:
    h = (header or "").strip().lower()
    non_feature_markers = ("id", "date", "time", "timestamp", "note", "comment")
    return any(m in h for m in non_feature_markers)
