"""Question- and schema-driven inference helpers for execution."""

import re
from typing import TYPE_CHECKING, Optional

import pandas as pd

from ....skills import RuntimeExecutionPlan, get_helper_grounding_mode
from ..analysis.task_intents import (
    header_is_non_feature_like,
    header_is_target_like,
)

if TYPE_CHECKING:
    from ..runtime import ExecutionRuntime


class ExecutionQuestionInferenceAdvisor:
    """Infer helper arguments from natural-language questions and observed schema."""

    def __init__(self, runtime: "ExecutionRuntime"):
        self.runtime = runtime

    @staticmethod
    def normalize_question_text(value: str) -> str:
        return re.sub(r"\s+", " ", (value or "").strip().lower())

    @staticmethod
    def normalize_header_name_for_grounding(value: str) -> str:
        text = str(value or "")
        text = re.sub(r"_x[0-9A-Fa-f]{4}_", "", text)
        text = re.sub(r"[_\W]+", " ", text, flags=re.UNICODE)
        text = re.sub(r"\s+", " ", text)
        return text.strip().lower()

    def expected_regression_predictors(self) -> list[str]:
        headers = sorted(self.runtime._observed_header_set())
        if not headers:
            return []
        target_like = [h for h in headers if header_is_target_like(h)]
        predictors: list[str] = []
        for header in headers:
            if header in target_like:
                continue
            if header_is_non_feature_like(header):
                continue
            predictors.append(header)
        return predictors

    @staticmethod
    def extract_feature_cols_literal(code: str) -> list[str]:
        match = re.search(r"feature_cols\s*=\s*\[([^\]]*)\]", code, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            return []
        return [s.strip() for s in re.findall(r"['\"]([^'\"]+)['\"]", match.group(1))]

    @staticmethod
    def extract_single_string_kwarg(code: str, kwarg: str) -> Optional[str]:
        match = re.search(
            rf"{kwarg}\s*=\s*['\"]([^'\"]+)['\"]",
            code,
            flags=re.IGNORECASE,
        )
        if not match:
            return None
        return match.group(1).strip()

    @staticmethod
    def extract_string_list_kwarg(code: str, kwarg: str) -> list[str]:
        match = re.search(
            rf"{kwarg}\s*=\s*\[([^\]]*)\]",
            code,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not match:
            return []
        return [item.strip() for item in re.findall(r"['\"]([^'\"]+)['\"]", match.group(1))]

    def infer_sort_desc_from_question(self, user_question: str) -> bool:
        q = self.normalize_question_text(user_question)
        if any(marker in q for marker in ("lowest to highest", "ascending", "smallest to largest", "lowest first")):
            return False
        return True

    def infer_top_n_from_question(self, user_question: str) -> Optional[int]:
        q = self.normalize_question_text(user_question)
        patterns = (
            r"\btop\s+(\d+)\b",
            r"\bhighest\s+(\d+)\b",
            r"\bfirst\s+(\d+)\b",
        )
        for pattern in patterns:
            match = re.search(pattern, q)
            if match:
                try:
                    value = int(match.group(1))
                except Exception:
                    continue
                if value > 0:
                    return value
        return None

    def infer_aggregate_from_question(self, user_question: str) -> str:
        q = self.normalize_question_text(user_question)
        aggregate_markers = (
            ("median", "median"),
            ("average", "mean"),
            ("mean", "mean"),
            ("sum", "sum"),
            ("total", "sum"),
            ("count", "count"),
            ("minimum", "min"),
            ("min", "min"),
            ("maximum", "max"),
            ("max", "max"),
        )
        for marker, aggregate in aggregate_markers:
            if marker in q:
                return aggregate
        return "mean"

    def headers_mentioned_in_question(self, observed_headers: list[str], user_question: str) -> list[str]:
        q = self.normalize_question_text(user_question)
        mentioned: list[tuple[int, str]] = []
        for header in observed_headers:
            normalized = self.normalize_header_name_for_grounding(header)
            if not normalized:
                continue
            position = q.find(normalized)
            if position >= 0:
                mentioned.append((position, header))
        mentioned.sort(key=lambda item: (item[0], item[1]))
        return [header for _, header in mentioned]

    @staticmethod
    def _grounding_mode(skill_route_name: str) -> str:
        return get_helper_grounding_mode(skill_route_name) or skill_route_name

    def infer_join_key_headers_from_question(
        self,
        observed_headers: list[str],
        user_question: str,
        *,
        multi_key: bool,
    ) -> list[str]:
        question = self.normalize_question_text(user_question)
        mentioned = self.headers_mentioned_in_question(observed_headers, user_question)

        def _score(header: str) -> float:
            normalized = self.normalize_header_name_for_grounding(header)
            score = 0.0
            if header in mentioned:
                score += 50.0
            if any(marker in normalized for marker in ("id", "code", "number", "key")):
                score += 40.0
            if any(marker in normalized for marker in ("term", "semester", "date", "year", "month", "section", "class", "group", "session", "slot", "room")):
                score += 20.0
            if any(marker in question for marker in ("join by", "join on", "match by", "match on", "group by", "using")):
                score += 5.0
            if any(marker in normalized for marker in ("score", "grade", "amount", "price", "cost", "sales", "revenue", "count", "quantity", "hours", "capacity", "instructor", "teacher", "professor")):
                score -= 15.0
            return score

        ranked = sorted(((_score(header), header) for header in observed_headers), key=lambda item: (-item[0], item[1]))
        selected = [header for score, header in ranked if score > 0]
        return selected[:2] if multi_key else selected[:1]

    def infer_runtime_plan(
        self,
        skill_name: str,
        helper_name: str,
        user_question: str,
        observed_headers: list[str],
    ) -> RuntimeExecutionPlan:
        mentioned = self.headers_mentioned_in_question(observed_headers, user_question)

        if helper_name == "compute_feature_correlations":
            question = self.normalize_question_text(user_question)
            feature_cols = tuple(
                header for header in mentioned
                if not header_is_non_feature_like(header)
            )
            target_candidates = [
                header for header in observed_headers
                if header not in feature_cols and not header_is_non_feature_like(header)
            ]

            target_col = next((header for header in mentioned if header_is_target_like(header)), None)
            if target_col is None:
                target_col = next((header for header in observed_headers if header_is_target_like(header)), None)
            if target_col is None and (
                "other factors" in question
                or "other features" in question
                or "factors such as" in question
                or "features such as" in question
            ):
                if len(target_candidates) == 1:
                    target_col = target_candidates[0]
            if target_col is None:
                normalized_question = self.normalize_header_name_for_grounding(user_question)

                def _target_score(header: str) -> tuple[int, str]:
                    normalized_header = self.normalize_header_name_for_grounding(header)
                    prefix_bonus = 1 if any(
                        token and token in normalized_question
                        for token in normalized_header.split()
                    ) else 0
                    surviv_prefix_bonus = 1 if (
                        normalized_header.startswith("surviv") and "surviv" in normalized_question
                    ) else 0
                    return (prefix_bonus + surviv_prefix_bonus, header)

                scored = sorted(
                    (_target_score(header) for header in target_candidates),
                    key=lambda item: (-item[0], item[1]),
                )
                if scored and scored[0][0] > 0:
                    target_col = scored[0][1]
            feature_cols = tuple(header for header in feature_cols if header != target_col)
            return RuntimeExecutionPlan(
                skill_name=skill_name,
                task_type="target_feature_correlation",
                table_roles={"primary_table": "runtime_selected"},
                target_col=target_col,
                feature_cols=feature_cols,
                categorical_cols_to_encode=feature_cols,
                numeric_cols_to_coerce=feature_cols,
                output_contract={"kind": "ranked_rows", "sheet_name": "Output"},
            )

        return RuntimeExecutionPlan(
            skill_name=skill_name,
            task_type=helper_name,
            table_roles={},
            output_contract={"kind": "workbook", "sheet_name": "Output"},
        )

    def build_skill_grounded_call_hint(
        self,
        skill_route_name: str,
        user_question: str,
        observed_headers: list[str],
    ) -> str:
        question = self.normalize_question_text(user_question)
        grounding_mode = self._grounding_mode(skill_route_name)

        def _header_score(header: str, role: str) -> float:
            normalized = self.normalize_header_name_for_grounding(header)
            tokens = [token for token in normalized.split(" ") if token]
            score = 0.0
            for token in tokens:
                if token in question:
                    score += 10.0
            if normalized and normalized in question:
                score += 20.0
            if role == "group":
                if any(marker in normalized for marker in ("category", "group", "type", "department", "course", "subject", "program", "semester", "term", "class", "region", "room", "faculty", "professor", "instructor", "tutor")):
                    score += 15.0
            elif role == "value":
                if any(marker in normalized for marker in ("score", "grade", "rating", "amount", "spending", "expense", "cost", "price", "salary", "revenue", "sales", "hours", "count", "quantity", "capacity", "utilisation", "utilization")):
                    score += 15.0
            elif role == "date":
                if any(marker in normalized for marker in ("date", "time", "year", "month", "quarter", "day")):
                    score += 20.0
            return score

        def _best_header(role: str) -> Optional[str]:
            scored = [(_header_score(header, role), header) for header in observed_headers]
            scored.sort(key=lambda item: (-item[0], item[1]))
            if not scored or scored[0][0] <= 0:
                return None
            return scored[0][1]

        if grounding_mode == "grouped_aggregation":
            group_header = _best_header("group")
            value_header = _best_header("value")
            if group_header and value_header and group_header != value_header:
                return (
                    "report = build_grouped_aggregation_ranking_report("
                    f"file_path=None, group_cols=['{group_header}'], value_col='{value_header}', "
                    "aggregate='mean', top_n=None, sort_desc=True)"
                )
            return ""

        if grounding_mode == "temporal_aggregation":
            date_header = _best_header("date")
            value_header = _best_header("value")
            if date_header and value_header and date_header != value_header:
                return (
                    "report = build_time_series_aggregation_report("
                    f"file_path=None, date_col='{date_header}', value_col='{value_header}', "
                    "period='month', aggregate='mean', window_years=5, period_mode='year_month', sort_desc=True)"
                )
            return ""

        if grounding_mode in {"multi_key_join", "single_key_join"}:
            key_candidates = self.infer_join_key_headers_from_question(
                observed_headers,
                user_question,
                multi_key=grounding_mode == "multi_key_join",
            )
            if grounding_mode == "multi_key_join":
                if len(key_candidates) >= 2:
                    key_list = ", ".join(f"'{header}'" for header in key_candidates[:2])
                    return (
                        "report = build_multi_key_relational_join_report("
                        f"range_ref='A1:Z200000', key_headers=[{key_list}], how='inner')"
                    )
                return (
                    "report = build_multi_key_relational_join_report("
                    "range_ref='A1:Z200000', key_headers=None, how='inner')"
                )
            key_header = key_candidates[0] if key_candidates else None
            if key_header:
                return (
                    "report = build_relational_join_enrichment_report("
                    f"range_ref='A1:Z200000', key_header='{key_header}', how='inner')"
                )
            return (
                "report = build_relational_join_enrichment_report("
                "range_ref='A1:Z200000', key_header=None, how='inner')"
            )

        return ""

    def infer_group_headers_from_question(
        self,
        observed_headers: list[str],
        user_question: str,
    ) -> list[str]:
        mentioned = self.headers_mentioned_in_question(observed_headers, user_question)
        selected: list[str] = []
        for header in mentioned:
            normalized = self.normalize_header_name_for_grounding(header)
            if any(
                marker in normalized
                for marker in (
                    "date", "time", "year", "month", "quarter", "day",
                    "score", "grade", "amount", "spending", "expense", "cost",
                    "price", "salary", "revenue", "sales", "count", "quantity",
                    "hours", "rate", "ratio", "percent", "pct", "utilisation", "utilization",
                )
            ):
                continue
            selected.append(header)
        if selected:
            return selected[:2]
        best = self.build_skill_grounded_call_hint(
            "build_grouped_aggregation_ranking_report",
            user_question,
            observed_headers,
        )
        match = re.search(r"group_cols=\[([^\]]*)\]", best)
        if not match:
            return []
        return re.findall(r"['\"]([^'\"]+)['\"]", match.group(1))[:2]

    def infer_value_header_from_question(
        self,
        observed_headers: list[str],
        user_question: str,
        skill_route_name: str,
    ) -> Optional[str]:
        mentioned = self.headers_mentioned_in_question(observed_headers, user_question)
        for header in mentioned:
            normalized = self.normalize_header_name_for_grounding(header)
            if any(
                marker in normalized
                for marker in (
                    "score", "grade", "amount", "spending", "expense", "cost",
                    "price", "salary", "revenue", "sales", "count", "quantity",
                    "hours", "utilisation", "utilization", "capacity", "rate",
                    "ratio", "pct", "percent",
                )
            ):
                return header
        hinted_call = self.build_skill_grounded_call_hint(skill_route_name, user_question, observed_headers)
        match = re.search(r"value_col=['\"]([^'\"]+)['\"]", hinted_call)
        return match.group(1) if match else None

    def infer_date_header_from_question(
        self,
        observed_headers: list[str],
        user_question: str,
    ) -> Optional[str]:
        mentioned = self.headers_mentioned_in_question(observed_headers, user_question)
        for header in mentioned:
            normalized = self.normalize_header_name_for_grounding(header)
            if any(marker in normalized for marker in ("date", "time", "year", "month", "quarter", "day")):
                return header
        hinted_call = self.build_skill_grounded_call_hint(
            "build_time_series_aggregation_report",
            user_question,
            observed_headers,
        )
        match = re.search(r"date_col=['\"]([^'\"]+)['\"]", hinted_call)
        return match.group(1) if match else None

    def infer_numeric_like_headers_from_df(self, df: pd.DataFrame) -> list[str]:
        numeric_headers: list[str] = []
        for header in df.columns:
            header_text = str(header)
            if header_is_non_feature_like(header_text):
                continue
            series = pd.to_numeric(df[header], errors="coerce")
            non_null = int(series.notna().sum())
            if non_null >= max(2, min(len(df), 3)):
                numeric_headers.append(header_text)
        return numeric_headers

    def infer_regression_columns_from_df(
        self,
        df: pd.DataFrame,
        user_question: str,
    ) -> tuple[Optional[str], list[str]]:
        numeric_headers = self.infer_numeric_like_headers_from_df(df)
        if len(numeric_headers) < 2:
            return None, []
        mentioned = self.headers_mentioned_in_question(numeric_headers, user_question)
        question = self.normalize_question_text(user_question)

        def _target_score(header: str) -> float:
            normalized = self.normalize_header_name_for_grounding(header)
            score = 0.0
            if header in mentioned:
                score += 40.0
            if header_is_target_like(header):
                score += 20.0
            for marker in ("predict", "target", "outcome", "dependent"):
                if marker in question:
                    score += 2.0
            for marker in ("sales", "revenue", "price", "cost", "score", "grade", "rating", "amount", "spending"):
                if marker in normalized:
                    score += 8.0
            return score

        scored = sorted(((_target_score(header), header) for header in numeric_headers), key=lambda item: (-item[0], item[1]))
        target_col = scored[0][1]
        feature_cols = [header for header in numeric_headers if header != target_col]
        return target_col, feature_cols

    def infer_correlation_columns_from_df(
        self,
        df: pd.DataFrame,
        user_question: str,
    ) -> tuple[list[str], Optional[str], Optional[str]]:
        numeric_headers = self.infer_numeric_like_headers_from_df(df)
        mentioned_numeric = self.headers_mentioned_in_question(numeric_headers, user_question)
        numeric_columns = mentioned_numeric if len(mentioned_numeric) >= 2 else numeric_headers

        filter_column: Optional[str] = None
        filter_value: Optional[str] = None
        question = self.normalize_question_text(user_question)
        for header in df.columns:
            header_text = str(header)
            if header_text in numeric_columns or header_is_non_feature_like(header_text):
                continue
            unique_values = [
                str(value).strip()
                for value in df[header].dropna().astype(str).unique().tolist()
                if str(value).strip()
            ]
            if not unique_values or len(unique_values) > 20:
                continue
            for value in unique_values:
                normalized_value = self.normalize_question_text(value)
                if normalized_value and normalized_value in question:
                    filter_column = header_text
                    filter_value = value
                    break
            if filter_column is not None:
                break
        return numeric_columns, filter_column, filter_value

    def infer_period_from_question(self, user_question: str) -> str:
        q = self.normalize_question_text(user_question)
        if "quarter" in q or "quarterly" in q:
            return "quarter"
        if "year" in q or "yearly" in q or "annual" in q:
            return "year"
        return "month"

    def infer_period_mode_from_question(self, user_question: str, period: str) -> str:
        q = self.normalize_question_text(user_question)
        if period == "month":
            if any(marker in q for marker in ("month-of-year", "calendar month", "all january", "all february", "across years by month")):
                return "month_of_year"
            return "year_month"
        if period == "quarter":
            if any(marker in q for marker in ("quarter-of-year", "calendar quarter", "across years by quarter")):
                return "quarter_of_year"
        return "year_month"

    def infer_window_years_from_question(self, user_question: str) -> Optional[int]:
        q = self.normalize_question_text(user_question)
        patterns = (
            r"(?:last|latest|recent)\s+(\d+)\s+years?",
            r"within\s+the\s+latest\s+(\d+)\s+years?",
            r"past\s+(\d+)\s+years?",
        )
        for pattern in patterns:
            match = re.search(pattern, q)
            if match:
                try:
                    value = int(match.group(1))
                except Exception:
                    continue
                if value > 0:
                    return value
        return None

    def infer_explicit_year_bounds_from_question(self, user_question: str) -> tuple[int, int]:
        q = self.normalize_question_text(user_question)
        preferred_patterns = (
            r"over the years\s+(19\d{2}|20\d{2}|21\d{2})\s*[–-]\s*(19\d{2}|20\d{2}|21\d{2})",
            r"from\s+(19\d{2}|20\d{2}|21\d{2})\s+to\s+(19\d{2}|20\d{2}|21\d{2})",
            r"between\s+(19\d{2}|20\d{2}|21\d{2})\s+and\s+(19\d{2}|20\d{2}|21\d{2})",
            r"year\s*\(?\s*(19\d{2}|20\d{2}|21\d{2})\s*(?:to|[–-])\s*(19\d{2}|20\d{2}|21\d{2})",
        )
        for pattern in preferred_patterns:
            match = re.search(pattern, q)
            if not match:
                continue
            try:
                start_year = int(match.group(1))
                end_year = int(match.group(2))
            except Exception:
                continue
            return min(start_year, end_year), max(start_year, end_year)

        years = [int(value) for value in re.findall(r"\b(19\d{2}|20\d{2}|21\d{2})\b", q)]
        unique_years: list[int] = []
        for year in years:
            if year not in unique_years:
                unique_years.append(year)
        if len(unique_years) >= 2:
            return min(unique_years), max(unique_years)
        return 2020, 2024
