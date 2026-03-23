"""Routing logic for whether to run the diagnose stage."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd

from ..log.logger_registry import LoggerRegistry
from ..prompt.prompt_builder import PromptBuilder
from ..task_families import should_skip_diagnose
from ..environment.spreadsheet.tools.cross_workbook import extract_sheet_table

logger = LoggerRegistry.setup_logger(__name__)


@dataclass
class DiagnoseDecision:
    should_diagnose: bool
    reasons: List[str] = field(default_factory=list)
    issues: List[Dict[str, Any]] = field(default_factory=list)


class DiagnoseRouter:
    """Decide whether the diagnose stage should run."""

    _QUESTION_STOPWORDS = {
        "a", "an", "and", "are", "as", "at", "be", "by", "calculate",
        "compute", "create", "do", "for", "from", "get", "how", "i",
        "in", "into", "is", "it", "make", "me", "month", "new", "of",
        "on", "or", "output", "please", "results", "sheet", "spreadsheet",
        "table", "task", "that", "the", "this", "to", "use", "what",
        "with", "you", "your",
    }
    _IDENTIFIER_HINTS = ("date", "id", "name", "task", "employee", "customer", "order", "room", "tutor")
    _METRIC_HINTS = {
        "average": ("average", "avg", "mean", "spending", "amount", "price", "cost", "value", "score", "rate"),
        "total": ("total", "sum", "spending", "amount", "price", "cost", "value", "sales", "revenue"),
        "count": ("count", "number", "total", "qty", "quantity", "students", "orders"),
        "max": ("max", "maximum", "highest", "largest", "top", "best"),
        "min": ("min", "minimum", "lowest", "smallest", "least"),
    }

    def __init__(self, client, deployment: str, progress_logger=None,
                 prompt_profile: str = "online_rich"):
        self.client = client
        self.deployment = deployment
        self.progress_logger = progress_logger
        self.prompt_builder = PromptBuilder(profile=prompt_profile)

    def decide(self, user_question: str, understanding_output: str,
               workbook_view) -> DiagnoseDecision:
        evidence_issues = self._detect_blocking_data_issues(workbook_view, user_question)
        if evidence_issues:
            should_diagnose = True
            reasons = [f"data_evidence:{len(evidence_issues)}"]
            issues = evidence_issues
        else:
            should_diagnose = self._deterministic_fallback_decision(user_question)
            reasons = [f"deterministic:{'YES' if should_diagnose else 'NO'}"]
            issues = []

        use_llm_fallback = os.getenv("SHEETHERO_ROUTER_LLM_FALLBACK", "0").strip() == "1"
        if use_llm_fallback and not evidence_issues:
            prompt = self.prompt_builder.build_diagnose_router_prompt(
                user_question=user_question,
                understanding_output=understanding_output
            )
            llm_decision = self._ask_llm(prompt)
            if llm_decision is not None:
                should_diagnose = llm_decision
                reasons = [f"llm:{'YES' if should_diagnose else 'NO'}"]

        if self.progress_logger:
            self.progress_logger.log(
                f"[ROUTER] Diagnose decision={should_diagnose} ({reasons[0]})",
                to_terminal=False
            )
            if should_diagnose and issues:
                descriptions = [str(issue.get("description") or issue) for issue in issues]
                self.progress_logger.log_raw(
                    "\n".join(["### [ROUTER DATA EVIDENCE]"] + [f"- {issue}" for issue in descriptions])
                )

        return DiagnoseDecision(
            should_diagnose=should_diagnose,
            reasons=reasons,
            issues=issues,
        )

    @staticmethod
    def _deterministic_fallback_decision(user_question: str) -> Optional[bool]:
        text = (user_question or "").strip().lower()
        if not text:
            return False

        def has_phrase(phrase: str) -> bool:
            escaped = re.escape(phrase.lower())
            return re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", text) is not None

        if ("fill any missing" in text or "fill missing" in text) and "using" in text and "file" in text:
            return False

        candidate_screening_markers = (
            "rank the candidates",
            "candidate information",
            "working experience",
            "personality score",
        )
        if sum(1 for marker in candidate_screening_markers if marker in text) >= 3:
            return False

        explicit_cleaning_markers = (
            "clean",
            "cleaning",
            "normalize",
            "normalise",
            "standardize",
            "standardise",
            "deduplicate",
            "de-duplicate",
            "fix data",
            "impute",
            "fill blank",
            "fill blanks",
            "remove duplicates",
            "resolve inconsistency",
            "resolve inconsistencies",
        )
        return any(has_phrase(marker) for marker in explicit_cleaning_markers)

    @staticmethod
    def _normalize_header_name(text: str) -> str:
        value = (text or "").strip().lower()
        value = re.sub(r"_x[0-9a-f]{4}_", "", value)
        value = re.sub(r"[\s_\-]+", " ", value)
        return value.strip()

    @staticmethod
    def _normalize_cell_text(text: Any) -> str:
        if text is None:
            return ""
        try:
            if pd.isna(text):
                return ""
        except Exception:
            pass
        value = str(text)
        value = re.sub(r"_x[0-9a-f]{4}_", "", value, flags=re.IGNORECASE)
        value = value.strip()
        value = re.sub(r"\s+", " ", value)
        return value

    @classmethod
    def _is_self_reporting_issue_task(cls, user_question: str) -> bool:
        q = (user_question or "").lower()
        if "missing data" in q and ("identify where" in q or "where values are missing" in q or "check the file" in q):
            return True
        if "room identifiers" in q or "room identifier" in q or "c80" in q or "c 80" in q:
            return True
        return False

    @classmethod
    def _coerce_workbook_view(cls, workbook_view) -> Dict[str, pd.DataFrame]:
        if not isinstance(workbook_view, dict):
            return {}
        if any(isinstance(value, pd.DataFrame) for value in workbook_view.values()):
            return {
                str(key): value for key, value in workbook_view.items()
                if value is not None and hasattr(value, "columns")
            }

        view: Dict[str, pd.DataFrame] = {}
        for path, workbook in workbook_view.items():
            if workbook is None or not hasattr(workbook, "worksheets"):
                continue
            file_key = os.path.basename(str(path))
            for sheet in workbook.worksheets:
                extracted = extract_sheet_table(
                    sheet,
                    "A1:Z200",
                    drop_blank_rows=False,
                    drop_empty_primary_key=False,
                    stop_at_note_row=True,
                )
                if not extracted.get("header"):
                    df = pd.DataFrame()
                else:
                    df = pd.DataFrame(extracted["rows"], columns=extracted["header"])
                    df.attrs["excel_rows"] = list(extracted.get("excel_rows", []))
                    df.attrs["header_excel_row"] = extracted.get("header_excel_row")
                    df.attrs["overflow_excel_rows"] = list(extracted.get("overflow_excel_rows", []))
                view[f"{file_key}::{sheet.title}"] = df
        return view

    @classmethod
    def _excel_row_number(cls, df: pd.DataFrame, row_index: int) -> int:
        excel_rows = getattr(df, "attrs", {}).get("excel_rows")
        if isinstance(excel_rows, list) and 0 <= row_index < len(excel_rows):
            return int(excel_rows[row_index])
        header_excel_row = getattr(df, "attrs", {}).get("header_excel_row")
        if isinstance(header_excel_row, int):
            return header_excel_row + row_index + 1
        return row_index + 2

    @classmethod
    def _extract_sheet_parts(cls, sheet_key: str) -> tuple[str, str]:
        if "::" not in sheet_key:
            return sheet_key, "Sheet1"
        file_name, sheet_name = sheet_key.split("::", 1)
        return file_name, sheet_name

    @classmethod
    def _normalize_question_tokens(cls, user_question: str) -> List[str]:
        raw_tokens = re.findall(r"[a-z0-9]+", (user_question or "").lower())
        normalized: list[str] = []
        expansions = {
            "opex": ["operating", "expenses", "operating expenses"],
            "ebitda": ["operating", "expenses", "revenue", "profit"],
            "ctr": ["ctr", "click", "through", "rate", "percentage", "percent"],
            "cvr": ["cvr", "conversion", "rate", "percentage", "percent"],
            "pnl": ["profit", "loss", "revenue", "expenses"],
        }
        for token in raw_tokens:
            if token in cls._QUESTION_STOPWORDS:
                continue
            normalized.append(token)
            normalized.extend(expansions.get(token, []))
        return normalized

    @classmethod
    def _column_relevance_score(cls, column_name: str, user_question: str) -> int:
        normalized = cls._normalize_header_name(column_name)
        if not normalized:
            return 0
        question = (user_question or "").lower()
        tokens = set(cls._normalize_question_tokens(user_question))
        header_tokens = set(normalized.split())
        score = 0

        if normalized in question:
            score += 5
        score += 2 * len(tokens & header_tokens)

        for trigger, hints in cls._METRIC_HINTS.items():
            if trigger in question and any(hint in normalized for hint in hints):
                score += 3

        if any(hint in normalized for hint in ("date", "time", "day")) and any(word in question for word in ("date", "time", "day", "month")):
            score += 2
        if any(hint in normalized for hint in ("name", "id", "code")) and any(word in question for word in ("name", "id", "tutor", "student", "employee", "customer")):
            score += 2
        if any(hint in normalized for hint in ("depends", "dependency", "prerequisite", "predecessor")) and any(
            word in question for word in ("depend", "dependency", "dependencies", "schedule", "prerequisite", "predecessor")
        ):
            score += 4

        return score

    @classmethod
    def _relevant_columns(cls, df: pd.DataFrame, user_question: str) -> List[str]:
        scored: List[tuple[int, str]] = []
        for column_name in map(str, getattr(df, "columns", [])):
            score = cls._column_relevance_score(column_name, user_question)
            if score > 0:
                scored.append((score, column_name))
        scored.sort(key=lambda item: (-item[0], item[1].lower()))
        return [column_name for _, column_name in scored[:4]]

    @classmethod
    def _is_missing_value(cls, value: Any) -> bool:
        try:
            if pd.isna(value):
                return True
        except Exception:
            pass
        if value is None:
            return True
        if isinstance(value, str) and value.strip() == "":
            return True
        return False

    @classmethod
    def _row_has_any_data(cls, row: pd.Series) -> bool:
        for value in row.tolist():
            if not cls._is_missing_value(value):
                return True
        return False

    @classmethod
    def _guess_identifier_column(cls, df: pd.DataFrame, problem_column: str) -> Optional[str]:
        columns = [str(col) for col in getattr(df, "columns", []) if str(col) != str(problem_column)]
        preferred = [
            col for col in columns
            if any(token in cls._normalize_header_name(col) for token in cls._IDENTIFIER_HINTS)
        ]
        for column_name in preferred + columns:
            non_empty = df[column_name].map(cls._normalize_cell_text)
            if (non_empty != "").any():
                return column_name
        return None

    @classmethod
    def _row_context_label(cls, df: pd.DataFrame, row_index: int, problem_column: str) -> str:
        if row_index < 0 or row_index >= len(df):
            return ""
        identifier_column = cls._guess_identifier_column(df, problem_column)
        if not identifier_column:
            return ""
        value = cls._normalize_cell_text(df.iloc[row_index][identifier_column])
        if not value:
            return ""
        return f"{identifier_column} = {value}"

    @classmethod
    def _select_preview_columns(cls, df: pd.DataFrame, focus_columns: Optional[List[str]] = None) -> List[str]:
        all_columns = [str(col) for col in getattr(df, "columns", [])]
        if not all_columns:
            return []
        if len(all_columns) <= 8:
            return all_columns

        focus_columns = [str(col) for col in (focus_columns or []) if str(col) in all_columns]
        if not focus_columns:
            return all_columns[:8]

        focus_indices = sorted(all_columns.index(column_name) for column_name in focus_columns)
        start = max(0, focus_indices[0] - 2)
        end = min(len(all_columns), start + 8)
        start = max(0, end - 8)
        return all_columns[start:end]

    @classmethod
    def _format_preview_value(cls, value: Any) -> str:
        if cls._is_missing_value(value):
            return ""
        return cls._normalize_cell_text(value)

    @classmethod
    def _build_markdown_preview(cls, df: pd.DataFrame, row_indices: List[int], focus_columns: Optional[List[str]] = None) -> str:
        if df is None or df.empty:
            return ""

        usable_indices = []
        for row_index in row_indices:
            if 0 <= row_index < len(df) and row_index not in usable_indices:
                usable_indices.append(row_index)
        if not usable_indices:
            return ""

        # Always include one comparison row when possible so the user can
        # interpret the issue against nearby data, even if the issue is on the
        # first visible row.
        if len(usable_indices) == 1:
            only_index = usable_indices[0]
            if only_index + 1 < len(df):
                usable_indices.append(only_index + 1)
            elif only_index - 1 >= 0:
                usable_indices.insert(0, only_index - 1)

        selected_columns = cls._select_preview_columns(df, focus_columns)
        if not selected_columns:
            return ""

        separator = ["---"] * len(selected_columns)
        human_rows = [cls._excel_row_number(df, row_index) for row_index in usable_indices]
        issue_row_index = None
        if row_indices:
            last_requested = row_indices[-1]
            if 0 <= last_requested < len(df):
                issue_row_index = last_requested
        if len(human_rows) == 2:
            if issue_row_index is not None and issue_row_index in usable_indices:
                comparison_index = next(
                    (idx for idx in usable_indices if idx != issue_row_index),
                    issue_row_index,
                )
                row_context = (
                    f"Rows shown: comparison row = Excel row {cls._excel_row_number(df, comparison_index)}, "
                    f"issue row = Excel row {cls._excel_row_number(df, issue_row_index)}."
                )
            else:
                row_context = (
                    f"Rows shown: Excel row {human_rows[0]} and Excel row {human_rows[1]}."
                )
        elif len(human_rows) == 1:
            row_context = f"Row shown: Excel row {human_rows[0]}."
        else:
            row_context = "Rows shown: " + ", ".join(f"Excel row {row_number}" for row_number in human_rows) + "."
        lines = [
            "Context preview:",
            row_context,
            "| " + " | ".join(selected_columns) + " |",
            "| " + " | ".join(separator) + " |",
        ]
        for row_index in usable_indices:
            row = df.iloc[row_index]
            values = [cls._format_preview_value(row[col]) for col in selected_columns]
            lines.append("| " + " | ".join(values) + " |")
        return "\n".join(lines)

    @classmethod
    def _make_issue(
        cls,
        *,
        issue_type: str,
        description: str,
        question: str,
        details_markdown: str = "",
        preview_kind: str = "table",
        material_to_result: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return {
            "source": "router_evidence",
            "issue_type": issue_type,
            "description": description,
            "question": question,
            "details_markdown": details_markdown,
            "preview_kind": preview_kind,
            "material_to_result": material_to_result,
            "metadata": metadata or {},
        }

    @classmethod
    def _question_is_merge_like(cls, user_question: str) -> bool:
        q = (user_question or "").lower()
        markers = (
            "merge",
            "using another file",
            "using another csv",
            "join",
            "combine",
            "match",
            "rank the candidates",
            "fill missing",
            "dashboard",
            "screening",
        )
        return any(marker in q for marker in markers)

    @classmethod
    def _is_unique_key_like_header(cls, column_name: str) -> bool:
        normalized = cls._normalize_header_name(column_name)
        blocked_suffix_markers = (
            "opt in",
            "required",
            "status",
            "type",
            "level",
            "rate",
            "score",
            "price",
            "cost",
            "qty",
            "quantity",
            "date",
            "time",
        )
        if any(normalized.endswith(marker) for marker in blocked_suffix_markers):
            return False
        if normalized in {"id", "identifier", "email", "code", "tutorid"}:
            return True
        explicit_phrases = (
            "employee id",
            "customer id",
            "order id",
            "record id",
            "reading id",
            "booking id",
            "agent id",
            "product id",
            "student id",
            "patient id",
            "station id",
            "appt id",
        )
        if normalized in explicit_phrases:
            return True
        return normalized.endswith("id") or normalized.endswith("identifier") or normalized.endswith("code")

    @classmethod
    def _header_matches_candidate(cls, column_name: str, candidate: str) -> bool:
        column_norm = cls._normalize_header_name(column_name)
        candidate_norm = cls._normalize_header_name(candidate)
        if not column_norm or not candidate_norm:
            return False
        if column_norm == candidate_norm:
            return True
        column_tokens = set(column_norm.split())
        candidate_tokens = set(candidate_norm.split())
        if candidate_tokens and candidate_tokens.issubset(column_tokens):
            return True
        if candidate_norm in column_norm or column_norm in candidate_norm:
            return True
        return False

    @classmethod
    def _is_period_like_column(cls, series: pd.Series, column_name: str) -> bool:
        normalized = cls._normalize_header_name(column_name)
        if any(token in normalized for token in ("year", "date", "month", "week", "quarter")):
            return True
        sample = [cls._normalize_cell_text(value) for value in series.tolist()[:12] if cls._normalize_cell_text(value)]
        if not sample:
            return False
        if sum(1 for value in sample if re.fullmatch(r"(19|20)\d{2}", value)) >= max(2, len(sample) // 2):
            return True
        if sum(1 for value in sample if re.search(r"(19|20)\d{2}", value)) >= max(2, len(sample) // 2):
            return True
        return False

    @classmethod
    def _extract_requested_years(cls, user_question: str) -> List[int]:
        years = sorted({int(token) for token in re.findall(r"\b(19\d{2}|20\d{2})\b", user_question or "")})
        return years

    @classmethod
    def _extract_available_years(cls, df: pd.DataFrame) -> List[int]:
        years: set[int] = set()
        for column_name in map(str, getattr(df, "columns", [])):
            series = df[column_name]
            if not cls._is_period_like_column(series, column_name):
                continue
            for raw_value in series.tolist():
                text = cls._normalize_cell_text(raw_value)
                if not text:
                    continue
                match = re.search(r"\b(19\d{2}|20\d{2})\b", text)
                if match:
                    years.add(int(match.group(1)))
        return sorted(years)

    @classmethod
    def _is_time_or_unit_column(cls, column_name: str) -> bool:
        normalized = cls._normalize_header_name(column_name)
        return any(
            token in normalized
            for token in (
                "time", "duration", "hour", "hours", "minute", "minutes", "rate",
                "amount", "price", "cost", "spending", "weight", "unit",
                "pct", "percent", "percentage", "ctr", "cvr",
            )
        )

    @classmethod
    def _is_date_like_text(cls, text: str) -> bool:
        value = cls._normalize_cell_text(text)
        if not value:
            return False
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return True
        if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", value):
            return True
        return False

    @classmethod
    def _date_format_kind(cls, text: str) -> str:
        value = cls._normalize_cell_text(text)
        if not value:
            return ""
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return "iso_ymd"
        if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", value):
            return "slash_dmy"
        return ""

    @classmethod
    def _canonical_inconsistency_key(cls, column_name: str, value: Any) -> str:
        text = cls._normalize_cell_text(value)
        if not text:
            return ""
        normalized_column = cls._normalize_header_name(column_name)
        if "date" in normalized_column:
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
                return text
            if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", text):
                parsed = pd.to_datetime(text, errors="coerce", format="%d/%m/%Y")
            else:
                parsed = pd.to_datetime(text, errors="coerce")
            if not pd.isna(parsed):
                return parsed.strftime("%Y-%m-%d")
        canonical = text.lower()
        canonical = re.sub(r"\s+", " ", canonical)
        return canonical.strip()

    @classmethod
    def _is_label_like_column(cls, df: pd.DataFrame, column_name: str) -> bool:
        normalized = cls._normalize_header_name(column_name)
        if cls._is_entity_key_header(column_name):
            return False
        if any(token in normalized for token in ("date", "time", "email", "id", "identifier")):
            return False
        series = df[column_name]
        non_empty = [cls._normalize_cell_text(value) for value in series.tolist() if cls._normalize_cell_text(value)]
        if not non_empty:
            return False
        if sum(1 for value in non_empty if re.fullmatch(r"-?\d+(\.\d+)?", value)) >= max(2, len(non_empty) - 1):
            return False
        unique_count = len(set(value.lower() for value in non_empty))
        if unique_count <= min(12, max(3, len(non_empty) // 2)):
            return True
        label_markers = (
            "status", "priority", "severity", "level", "category", "sector",
            "type", "method", "crop", "grade", "class", "department", "region",
        )
        return any(marker in normalized for marker in label_markers)

    @classmethod
    def _missing_value_priority(cls, column_name: str) -> int:
        normalized = cls._normalize_header_name(column_name)
        score = 0
        primary_markers = (
            "revenue", "sales", "price", "hours worked", "closing price",
            "kwh consumed", "score", "grade", "depends on", "check out date",
            "return reason", "stock qty", "operating expenses",
        )
        derived_markers = (
            "net ", "avg", "average", "pct", "percent", "ratio", "change",
            "cost", "total", "monthly cost", "daily change", "net revenue",
        )
        if any(marker in normalized for marker in primary_markers):
            score += 4
        if any(marker in normalized for marker in ("id", "name", "date", "time")):
            score += 2
        if any(marker in normalized for marker in derived_markers):
            score -= 3
        if normalized.startswith("net "):
            score -= 2
        return score

    @classmethod
    def _coerce_numeric_series(cls, series: pd.Series) -> pd.Series:
        return pd.to_numeric(series, errors="coerce")

    @classmethod
    def _semantic_numeric_bounds(cls, column_name: str) -> tuple[float | None, float | None]:
        normalized = cls._normalize_header_name(column_name)
        lower = None
        upper = None
        if any(token in normalized for token in ("score", "grade", "pct", "percent", "percentage", "ratio", "ctr")):
            lower = 0.0
            upper = 100.0
        if re.search(r"(^| )rate($| )", normalized) and any(
            token in normalized for token in ("success", "pass", "completion", "utilisation", "utilization", "occupancy")
        ):
            lower = 0.0
            upper = 100.0
        if "age" in normalized:
            lower = 0.0
            upper = 120.0
        if "years experience" in normalized or "experience" in normalized:
            lower = 0.0
            upper = 80.0
        if "systolic" in normalized:
            lower = 50.0
            upper = 300.0
        if "diastolic" in normalized:
            lower = 30.0
            upper = 200.0
        if "temp" in normalized and "avg" in normalized:
            lower = -80.0
            upper = 80.0
        if any(token in normalized for token in ("yield", "consumed", "qty", "quantity", "price", "cost", "salary", "revenue", "sales", "stock")):
            lower = 0.0 if lower is None else max(lower, 0.0)
        return lower, upper

    @classmethod
    def _requires_non_negative_metric(cls, column_name: str) -> bool:
        normalized = cls._normalize_header_name(column_name)
        return any(
            token in normalized
            for token in (
                "yield",
                "consumed",
                "qty",
                "quantity",
                "price",
                "cost",
                "rate",
                "salary",
                "revenue",
                "sales",
                "stock",
                "score",
                "grade",
                "pct",
                "percent",
                "percentage",
                "ratio",
                "ctr",
                "cvr",
                "systolic",
                "diastolic",
                "experience",
                "age",
            )
        )

    @classmethod
    def _series_uniqueness_ratio(cls, series: pd.Series) -> float:
        cleaned = [cls._normalize_cell_text(value) for value in series.tolist() if cls._normalize_cell_text(value)]
        if not cleaned:
            return 0.0
        return len(set(cleaned)) / len(cleaned)

    @classmethod
    def _has_more_granular_unique_key(cls, df: pd.DataFrame, key_col: str) -> bool:
        current_ratio = cls._series_uniqueness_ratio(df[key_col])
        for column_name in map(str, getattr(df, "columns", [])):
            if column_name == key_col:
                continue
            if not cls._is_unique_key_like_header(column_name):
                continue
            other_ratio = cls._series_uniqueness_ratio(df[column_name])
            if other_ratio >= 0.95 and other_ratio > current_ratio + 0.1:
                return True
        return False

    @classmethod
    def _is_event_granularity_column(cls, df: pd.DataFrame, column_name: str) -> bool:
        normalized = cls._normalize_header_name(column_name)
        if cls._is_period_like_column(df[column_name], column_name):
            return True
        if any(
            token in normalized
            for token in (
                "order",
                "booking",
                "reading",
                "transaction",
                "event",
                "appointment",
                "appt",
                "invoice",
                "record",
                "timestamp",
                "datetime",
            )
        ):
            return True
        return cls._is_unique_key_like_header(column_name) and cls._series_uniqueness_ratio(df[column_name]) >= 0.95

    @classmethod
    def _is_metric_like_column(cls, column_name: str) -> bool:
        normalized = cls._normalize_header_name(column_name)
        if cls._is_entity_key_header(column_name) or "date" in normalized or "time" in normalized:
            return False
        metric_markers = (
            "score", "price", "cost", "revenue", "sales", "salary", "hours",
            "duration", "bp", "pressure", "temp", "yield", "kwh", "qty",
            "quantity", "rate", "count", "stock", "experience", "age",
        )
        return any(marker in normalized for marker in metric_markers)

    @classmethod
    def _is_measure_like_column(cls, df: pd.DataFrame, column_name: str) -> bool:
        if cls._is_metric_like_column(column_name):
            return True
        if column_name not in getattr(df, "columns", []):
            return False
        series = cls._coerce_numeric_series(df[column_name])
        valid = series.dropna()
        if len(valid) < max(2, len(series) // 3):
            return False
        return len(valid) >= max(2, int(len(series) * 0.6))

    @classmethod
    def _is_id_like_value(cls, text: str) -> bool:
        value = cls._normalize_cell_text(text)
        if not value:
            return False
        if re.fullmatch(r"[A-Za-z]{2,}\d{2,}", value):
            return True
        if re.fullmatch(r"[A-Za-z]{1,5}[-_ ]?\d{2,}", value):
            return True
        if re.fullmatch(r"\d{3,}", value):
            return True
        return False

    @classmethod
    def _id_like_ratio(cls, values: List[Any]) -> float:
        cleaned = [cls._normalize_cell_text(value) for value in values if cls._normalize_cell_text(value)]
        if not cleaned:
            return 0.0
        matches = sum(1 for value in cleaned if cls._is_id_like_value(value))
        return matches / len(cleaned)

    @classmethod
    def _value_pattern_kind(cls, text: str) -> str:
        value = cls._normalize_cell_text(text)
        if not value:
            return ""
        lowered = value.lower()
        if re.fullmatch(r"\d{1,2}:\d{2}(\s*-\s*\d{1,2}:\d{2})?", lowered):
            return "time_hhmm"
        if re.fullmatch(r"\d{1,2}\s*(am|pm)(\s*-\s*\d{1,2}\s*(am|pm))?", lowered):
            return "time_ampm"
        if re.fullmatch(r"-?\d+(\.\d+)?", lowered):
            return "plain_number"
        if re.fullmatch(r"-?\d+(\.\d+)?\s*[a-z%£$]+", lowered):
            return "number_with_unit"
        if re.fullmatch(r"[a-z]+\s*-?\d+(\.\d+)?", lowered):
            return "prefixed_unit"
        return "other"

    @classmethod
    def _build_schema_preview(cls, df: pd.DataFrame) -> str:
        headers = [str(col) for col in getattr(df, "columns", [])]
        if not headers:
            return "Context preview:\nNo visible headers were found."
        lines = [
            "Context preview:",
            "Headers: " + ", ".join(headers[:12]),
        ]
        preview = cls._build_markdown_preview(df, [0, 1], [])
        if preview:
            preview_lines = preview.splitlines()
            if preview_lines and preview_lines[0].strip() == "Context preview:":
                preview_lines = preview_lines[1:]
            lines.extend(preview_lines)
        return "\n".join(lines)

    @classmethod
    def _index_is_default_range(cls, df: pd.DataFrame) -> bool:
        index = getattr(df, "index", None)
        if isinstance(index, pd.RangeIndex):
            return True
        if index is None:
            return True
        try:
            return list(index) == list(range(len(df)))
        except Exception:
            return False

    @classmethod
    def _detect_row_alignment_issues(
        cls,
        sheet_key: str,
        df: pd.DataFrame,
        user_question: str,
    ) -> List[Dict[str, Any]]:
        if df is None or df.empty:
            return []
        if not cls._question_is_merge_like(user_question):
            return []
        overflow_excel_rows = list(getattr(df, "attrs", {}).get("overflow_excel_rows") or [])
        if not overflow_excel_rows:
            return []

        columns = [str(col) for col in getattr(df, "columns", [])]
        key_like_columns = [col for col in columns if cls._is_entity_key_header(col)]
        if not key_like_columns:
            return []

        suspicious_column = columns[-1] if columns else None
        for column_name in key_like_columns:
            visible_ratio = cls._id_like_ratio(df[column_name].tolist()[:10])
            if visible_ratio <= 0.2 and suspicious_column is None:
                suspicious_column = column_name
        suspicious_column = suspicious_column or key_like_columns[0]

        non_empty_row_indices: List[int] = []
        for row_index in range(len(df)):
            excel_row = cls._excel_row_number(df, row_index)
            if excel_row not in overflow_excel_rows:
                continue
            if cls._row_has_any_data(df.iloc[row_index]):
                non_empty_row_indices.append(row_index)
            if len(non_empty_row_indices) >= 2:
                break
        if not non_empty_row_indices:
            return []

        file_name, sheet_name = cls._extract_sheet_parts(sheet_key)
        description = (
            f"In sheet `{sheet_key}`, some rows appear to contain more populated cells than the header allows."
        )
        question = (
            f"I noticed that in `{file_name}` / `{sheet_name}`, some rows appear to contain more values than the header structure allows, "
            f"and the visible columns look shifted near `{suspicious_column}`. This suggests the CSV may have been split incorrectly during parsing. "
            "Should I reconstruct those shifted rows before matching them with the other files?"
        )
        preview = cls._build_markdown_preview(df, non_empty_row_indices, columns[: min(len(columns), 6)])
        preview = (
            "Context preview:\n"
            f"Rows with suspected overflow values include Excel row(s): {', '.join(str(value) for value in overflow_excel_rows[:4])}.\n"
            "The visible columns may be shifted because the raw CSV row contains more cells than the header.\n"
            + "\n".join(preview.splitlines()[1:])
        )
        return [
            cls._make_issue(
                issue_type="row_alignment",
                description=description,
                question=question,
                details_markdown=preview,
                preview_kind="row_pair",
                metadata={
                    "sheet_key": sheet_key,
                    "suspicious_column": suspicious_column,
                    "overflow_excel_rows": overflow_excel_rows,
                },
            )
        ]

    @classmethod
    def _detect_duplicate_header_issues(cls, sheet_key: str, df: pd.DataFrame) -> List[Dict[str, Any]]:
        if df is None or not hasattr(df, "columns"):
            return []
        raw_headers = [str(col) for col in df.columns]
        normalized_to_raw: Dict[str, List[str]] = {}
        for raw in raw_headers:
            normalized = cls._normalize_header_name(raw)
            normalized_to_raw.setdefault(normalized, [])
            if raw not in normalized_to_raw[normalized]:
                normalized_to_raw[normalized].append(raw)

        file_name, sheet_name = cls._extract_sheet_parts(sheet_key)
        issues: List[Dict[str, Any]] = []
        for normalized, raw_variants in normalized_to_raw.items():
            if normalized and len(raw_variants) > 1:
                joined = ", ".join(f"`{item}`" for item in raw_variants[:4])
                description = (
                    f"In sheet `{sheet_key}`, multiple headers normalize to the same meaning ({joined})."
                )
                question = (
                    f"I noticed that in `{file_name}` / `{sheet_name}`, the headers {joined} look like the same field after normalization. "
                    "Which header should I treat as the authoritative one for this task?"
                )
                details = "Context preview:\n- Headers: " + ", ".join(raw_headers[:8])
                issues.append(
                    cls._make_issue(
                        issue_type="duplicate_header",
                        description=description,
                        question=question,
                        details_markdown=details,
                        preview_kind="schema",
                        metadata={"sheet_key": sheet_key, "headers": raw_variants},
                    )
                )
        return issues

    @classmethod
    def _detect_missing_key_column_issues(
        cls,
        workbook_view: Dict[str, pd.DataFrame],
        user_question: str,
    ) -> List[Dict[str, Any]]:
        if not cls._question_is_merge_like(user_question):
            return []
        if len(workbook_view) < 2:
            return []

        all_normalized_headers: Dict[str, set[str]] = {}
        for sheet_key, df in workbook_view.items():
            for column_name in map(str, getattr(df, "columns", [])):
                normalized = cls._normalize_header_name(column_name)
                if not normalized:
                    continue
                all_normalized_headers.setdefault(normalized, set()).add(sheet_key)

        common_key_candidates = [
            normalized for normalized, sheets in all_normalized_headers.items()
            if len(sheets) >= 2 and (
                cls._is_entity_key_header(normalized)
                or cls._is_entity_descriptor_header(normalized)
            )
        ]
        if not common_key_candidates:
            return []

        issues: List[Dict[str, Any]] = []
        for sheet_key, df in workbook_view.items():
            raw_headers = [str(col) for col in getattr(df, "columns", [])]
            if any(
                cls._header_matches_candidate(column_name, candidate)
                for candidate in common_key_candidates
                for column_name in raw_headers
            ):
                continue
            file_name, sheet_name = cls._extract_sheet_parts(sheet_key)
            display_candidates = ", ".join(f"`{candidate}`" for candidate in common_key_candidates[:4])
            description = (
                f"In sheet `{sheet_key}`, no clear matching key column was found for the multi-file task."
            )
            question = (
                f"I could not find a clear matching key in `{file_name}` / `{sheet_name}` for this multi-file task. "
                f"The other file(s) appear to match on fields like {display_candidates}. Which column in this sheet should I use to match rows?"
            )
            issues.append(
                cls._make_issue(
                    issue_type="missing_key_column",
                    description=description,
                    question=question,
                    details_markdown=cls._build_schema_preview(df),
                    preview_kind="schema",
                    metadata={"sheet_key": sheet_key, "candidate_keys": common_key_candidates},
                )
            )
            if len(issues) >= 1:
                break
        return issues

    @classmethod
    def _is_entity_key_header(cls, column_name: str) -> bool:
        normalized = cls._normalize_header_name(column_name)
        relation_like = ("depends on", "node from", "node to", "source", "target")
        if any(token in normalized for token in relation_like):
            return False
        if normalized in {"id", "identifier", "code", "email", "room", "tutorid"}:
            return True
        if any(token in normalized for token in ("employee id", "customer id", "order id")):
            return True
        if re.search(r"(^| )id($| )", normalized):
            return True
        if re.search(r"(^| )identifier($| )", normalized):
            return True
        if re.search(r"(^| )email($| )", normalized):
            return True
        if re.search(r"(^| )code($| )", normalized):
            return True
        if normalized.startswith("room ") and any(token in normalized for token in ("number", "id", "identifier", "code", "no")):
            return True
        return False

    @classmethod
    def _is_entity_descriptor_header(cls, column_name: str) -> bool:
        normalized = cls._normalize_header_name(column_name)
        if normalized in {"name", "email", "room", "code", "identifier", "id"}:
            return True
        if any(token in normalized for token in ("employee id", "customer id", "order id")):
            return True
        if normalized.startswith("room ") and any(token in normalized for token in ("number", "id", "identifier", "code", "no")):
            return True
        return any(
            re.search(rf"(^| ){token}($| )", normalized)
            for token in ("name", "email", "code", "identifier", "id")
        )

    @classmethod
    def _detect_conflicting_key_mapping_issues(cls, sheet_key: str, df: pd.DataFrame) -> List[Dict[str, Any]]:
        if df is None or df.empty or not hasattr(df, "columns"):
            return []

        file_name, sheet_name = cls._extract_sheet_parts(sheet_key)
        issues: List[Dict[str, Any]] = []
        columns = [str(col) for col in df.columns]
        key_columns = [col for col in columns if cls._is_entity_key_header(col)]
        descriptor_columns = [col for col in columns if cls._is_entity_descriptor_header(col)]
        if not key_columns or len(descriptor_columns) < 2:
            return []

        for key_col in key_columns:
            for descriptor_col in [col for col in descriptor_columns if col != key_col]:
                working = df[[key_col, descriptor_col]].copy()
                row_index_column = "___router_row_index___"
                working[row_index_column] = list(range(len(df)))
                working[key_col] = working[key_col].map(cls._normalize_cell_text)
                working["__normalized_descriptor__"] = working[descriptor_col].map(cls._normalize_cell_text)
                working = working[(working[key_col] != "") & (working["__normalized_descriptor__"] != "")]
                if working.empty:
                    continue

                grouped = working.groupby(key_col)["__normalized_descriptor__"].nunique(dropna=True)
                conflict_keys = grouped[grouped > 1].index.tolist()
                if not conflict_keys:
                    continue

                example_key = conflict_keys[0]
                sample_rows = working[working[key_col] == example_key].head(2)
                raw_values = sorted({cls._normalize_cell_text(value) for value in sample_rows[descriptor_col].tolist() if cls._normalize_cell_text(value)})[:3]
                row_indices = [int(value) for value in sample_rows[row_index_column].tolist()]
                description = (
                    f"In sheet `{sheet_key}`, `{key_col}` value `{example_key}` maps to multiple `{descriptor_col}` values."
                )
                question = (
                    f"I noticed that in `{file_name}` / `{sheet_name}`, `{key_col}` value `{example_key}` is linked to different `{descriptor_col}` values "
                    f"({', '.join(raw_values)}). Which value should I use as correct?"
                )
                issues.append(
                    cls._make_issue(
                        issue_type="conflicting_mapping",
                        description=description,
                        question=question,
                        details_markdown=cls._build_markdown_preview(df, row_indices, [key_col, descriptor_col]),
                        preview_kind="row_pair",
                        metadata={
                            "sheet_key": sheet_key,
                            "key_column": key_col,
                            "descriptor_column": descriptor_col,
                            "entity_key": example_key,
                        },
                    )
                )
                if len(issues) >= 2:
                    return issues
        return issues

    @classmethod
    def _detect_missing_value_issues(
        cls,
        sheet_key: str,
        df: pd.DataFrame,
        user_question: str,
    ) -> List[Dict[str, Any]]:
        if df is None or df.empty:
            return []
        file_name, sheet_name = cls._extract_sheet_parts(sheet_key)
        issues: List[Dict[str, Any]] = []
        relevant_columns = cls._relevant_columns(df, user_question)
        if not relevant_columns:
            return []
        row_candidates: dict[int, list[str]] = {}
        for column_name in relevant_columns:
            series = df[column_name]
            for row_index, value in enumerate(series.tolist()):
                if not cls._is_missing_value(value):
                    continue
                row = df.iloc[row_index]
                if not cls._row_has_any_data(row):
                    continue
                row_candidates.setdefault(row_index, []).append(column_name)

        for row_index in sorted(row_candidates):
            candidate_columns = row_candidates[row_index]
            candidate_columns.sort(
                key=lambda col: (-cls._missing_value_priority(col), str(col).lower())
            )
            column_name = candidate_columns[0]
            normalized_column = cls._normalize_header_name(column_name)
            excel_row = cls._excel_row_number(df, row_index)
            context_label = cls._row_context_label(df, row_index, column_name)
            description = (
                f"In sheet `{sheet_key}`, column `{column_name}` is empty at Excel row {excel_row}."
            )
            question = (
                f"I noticed that in `{file_name}` / `{sheet_name}`, the value in column `{column_name}` is empty at Excel row {excel_row}"
            )
            if context_label:
                question += f" ({context_label})"
            if normalized_column == "depends on":
                question += (
                    ". Does this mean the task has no prerequisite and should be treated as a root task, "
                    "or should I treat it as missing data?"
                )
            else:
                question += ". How should I handle it for this task?"

            preview_rows = [row_index - 1, row_index] if row_index > 0 else [row_index]
            issues.append(
                cls._make_issue(
                    issue_type="missing_value",
                    description=description,
                    question=question,
                    details_markdown=cls._build_markdown_preview(df, preview_rows, [column_name]),
                    preview_kind="cell_issue",
                    metadata={
                        "sheet_key": sheet_key,
                        "column": column_name,
                        "row_index": row_index,
                        "excel_row": excel_row,
                    },
                )
            )
            if len(issues) >= 2:
                break
        return issues

    @classmethod
    def _detect_internal_blank_row_issues(
        cls,
        sheet_key: str,
        df: pd.DataFrame,
        user_question: str,
    ) -> List[Dict[str, Any]]:
        if df is None or df.empty:
            return []
        question_lower = (user_question or "").lower()
        if not any(token in question_lower for token in ("average", "total", "sum", "merge", "combine", "report", "analysis", "calculate")):
            return []

        row_has_data = [cls._row_has_any_data(df.iloc[idx]) for idx in range(len(df))]
        if not any(row_has_data):
            return []
        first_data = next((idx for idx, has_data in enumerate(row_has_data) if has_data), None)
        last_data = next((idx for idx in range(len(row_has_data) - 1, -1, -1) if row_has_data[idx]), None)
        if first_data is None or last_data is None or first_data >= last_data:
            return []

        file_name, sheet_name = cls._extract_sheet_parts(sheet_key)
        for row_index in range(first_data + 1, last_data):
            if row_has_data[row_index]:
                continue
            previous_index = row_index - 1
            if previous_index < 0 or not row_has_data[previous_index]:
                continue
            excel_row = cls._excel_row_number(df, row_index)
            description = f"In sheet `{sheet_key}`, Excel row {excel_row} is blank inside an active table."
            question = (
                f"I noticed that `{file_name}` / `{sheet_name}` has a blank row at Excel row {excel_row} in the middle of the table. "
                "Should I ignore this blank row and continue reading the surrounding rows as one table?"
            )
            return [
                cls._make_issue(
                    issue_type="blank_row",
                    description=description,
                    question=question,
                    details_markdown=cls._build_markdown_preview(df, [previous_index, row_index], []),
                    preview_kind="boundary",
                    metadata={"sheet_key": sheet_key, "row_index": row_index, "excel_row": excel_row},
                )
            ]
        return []

    @classmethod
    def _is_name_like_column(cls, column_name: str) -> bool:
        normalized = cls._normalize_header_name(column_name)
        return any(token in normalized for token in ("name", "student", "tutor", "teacher", "employee", "customer"))

    @classmethod
    def _has_actionable_format_variation(cls, raw_values: List[str]) -> bool:
        cleaned = [value for value in raw_values if value]
        if len(cleaned) < 2:
            return False
        if all(cls._is_date_like_text(value) for value in cleaned):
            return len({cls._date_format_kind(value) for value in cleaned if cls._date_format_kind(value)}) > 1
        lower_values = {value.lower() for value in cleaned}
        if len(lower_values) > 1:
            comma_variation = any("," in value for value in cleaned)
            whitespace_variation = any(value != value.strip() or "  " in value for value in cleaned)
            order_like_variation = any("," in value for value in cleaned) and any("," not in value for value in cleaned)
            return comma_variation or whitespace_variation or order_like_variation
        return any(value != cleaned[0] for value in cleaned[1:])

    @classmethod
    def _detect_format_inconsistency_issues(
        cls,
        sheet_key: str,
        df: pd.DataFrame,
        user_question: str,
    ) -> List[Dict[str, Any]]:
        if df is None or df.empty:
            return []
        file_name, sheet_name = cls._extract_sheet_parts(sheet_key)
        issues: List[Dict[str, Any]] = []
        candidate_columns = list(dict.fromkeys(
            [
                col for col in cls._relevant_columns(df, user_question)
                if cls._is_name_like_column(col) or cls._is_label_like_column(df, col) or "date" in cls._normalize_header_name(col)
            ] + [
                str(col) for col in getattr(df, "columns", [])
                if cls._is_name_like_column(str(col)) or cls._is_label_like_column(df, str(col)) or "date" in cls._normalize_header_name(str(col))
            ]
        ))

        for column_name in candidate_columns[:5]:
            normalized_column = cls._normalize_header_name(column_name)
            if "date" in normalized_column:
                format_examples: dict[str, int] = {}
                for row_index, value in enumerate(df[column_name].tolist()):
                    kind = cls._date_format_kind(value)
                    if kind and kind not in format_examples:
                        format_examples[kind] = row_index
                if len(format_examples) >= 2:
                    row_indices = list(format_examples.values())[:2]
                    example_values = [
                        cls._normalize_cell_text(df.iloc[row_index][column_name])
                        for row_index in row_indices
                    ]
                    description = (
                        f"In sheet `{sheet_key}`, column `{column_name}` mixes multiple date formats."
                    )
                    question = (
                        f"I noticed that in `{file_name}` / `{sheet_name}`, column `{column_name}` mixes date formats such as "
                        f"`{example_values[0]}` and `{example_values[1]}`. Should I normalize this whole column to one consistent date format before continuing?"
                    )
                    issues.append(
                        cls._make_issue(
                            issue_type="format_inconsistency",
                            description=description,
                            question=question,
                            details_markdown=cls._build_markdown_preview(df, row_indices, [column_name]),
                            preview_kind="row_pair",
                            metadata={
                                "sheet_key": sheet_key,
                                "column": column_name,
                                "format_kinds": list(format_examples.keys())[:2],
                            },
                        )
                    )
                    if len(issues) >= 1:
                        return issues
                    continue

            working = pd.DataFrame({
                "raw": df[column_name].tolist(),
                "canonical": [cls._canonical_inconsistency_key(column_name, value) for value in df[column_name].tolist()],
                "row_index": list(range(len(df))),
            })
            working = working[(working["canonical"] != "") & (working["raw"].map(lambda value: not cls._is_missing_value(value)))]
            if working.empty:
                continue

            for canonical_value, group in working.groupby("canonical"):
                raw_variants = []
                row_indices = []
                for _, record in group.iterrows():
                    raw_text = cls._normalize_cell_text(record["raw"])
                    if raw_text not in raw_variants:
                        raw_variants.append(raw_text)
                        row_indices.append(int(record["row_index"]))
                if len(raw_variants) < 2:
                    continue
                if not cls._has_actionable_format_variation(raw_variants):
                    continue

                display_variants = [cls._normalize_cell_text(value) or str(value) for value in raw_variants[:2]]
                description = (
                    f"In sheet `{sheet_key}`, column `{column_name}` uses inconsistent textual formats for the same logical value `{canonical_value}`."
                )
                question = (
                    f"I noticed that in `{file_name}` / `{sheet_name}`, column `{column_name}` uses both `{display_variants[0]}` and `{display_variants[1]}` for what looks like the same value. "
                    "Should I treat them as the same value and normalize them before matching?"
                )
                issues.append(
                    cls._make_issue(
                        issue_type="format_inconsistency",
                        description=description,
                        question=question,
                        details_markdown=cls._build_markdown_preview(df, row_indices[:2], [column_name]),
                        preview_kind="row_pair",
                        metadata={
                            "sheet_key": sheet_key,
                            "column": column_name,
                            "normalized_value": canonical_value,
                        },
                    )
                )
                if len(issues) >= 1:
                    return issues
        return issues

    @classmethod
    def _detect_unit_or_time_format_issues(
        cls,
        sheet_key: str,
        df: pd.DataFrame,
        user_question: str,
    ) -> List[Dict[str, Any]]:
        if df is None or df.empty:
            return []
        file_name, sheet_name = cls._extract_sheet_parts(sheet_key)
        issues: List[Dict[str, Any]] = []
        question_lower = (user_question or "").lower()
        candidate_columns = [
            column_name for column_name in cls._relevant_columns(df, user_question)
            if cls._is_time_or_unit_column(column_name)
        ]
        for column_name in candidate_columns:
            normalized_column = cls._normalize_header_name(column_name)
            if normalized_column not in question_lower and not any(
                marker in question_lower
                for marker in (
                    "calculate", "average", "total", "sum", "duration", "hours", "minutes",
                    "schedule", "scheduling", "rate", "percent", "percentage", "ctr", "cvr",
                    "report", "reporting", "benchmark", "analysis", "inconsistency",
                )
            ):
                continue
            if "preferred" in normalized_column:
                continue

            numeric_series = cls._coerce_numeric_series(df[column_name])
            numeric_valid = numeric_series.dropna()
            if (
                len(numeric_valid) >= 4
                and any(token in normalized_column for token in ("pct", "percent", "percentage", "ctr", "cvr", "rate"))
            ):
                fraction_rows = [
                    int(row_index)
                    for row_index, value in numeric_series.items()
                    if not pd.isna(value) and 0 < float(value) < 0.1
                ]
                percent_rows = [
                    int(row_index)
                    for row_index, value in numeric_series.items()
                    if not pd.isna(value) and float(value) >= 1
                ]
                if fraction_rows and len(percent_rows) >= 2:
                    issue_row = fraction_rows[0]
                    comparison_row = percent_rows[0] if percent_rows[0] != issue_row else percent_rows[1]
                    issue_value = cls._normalize_cell_text(df.iloc[issue_row][column_name])
                    comparison_value = cls._normalize_cell_text(df.iloc[comparison_row][column_name])
                    description = (
                        f"In sheet `{sheet_key}`, column `{column_name}` appears to mix raw fraction values with percentage-scale values."
                    )
                    question = (
                        f"I noticed that in `{file_name}` / `{sheet_name}`, column `{column_name}` mixes values like "
                        f"`{comparison_value}` and `{issue_value}`. This looks like some rows may use percentage scale while others use raw fractions. "
                        "Should I convert the fraction-style values to the same percentage scale before continuing?"
                    )
                    issues.append(
                        cls._make_issue(
                            issue_type="unit_or_time_format",
                            description=description,
                            question=question,
                            details_markdown=cls._build_markdown_preview(df, [comparison_row, issue_row], [column_name]),
                            preview_kind="cell_issue",
                            metadata={
                                "sheet_key": sheet_key,
                                "column": column_name,
                                "formats": ["percentage_scale", "raw_fraction"],
                            },
                        )
                    )
                    if len(issues) >= 1:
                        break

            values = []
            for row_index, raw_value in enumerate(df[column_name].tolist()):
                text = cls._normalize_cell_text(raw_value)
                if not text:
                    continue
                kind = cls._value_pattern_kind(text)
                values.append((row_index, text, kind))
            if len(values) < 2:
                continue

            kinds = {}
            for row_index, text, kind in values:
                kinds.setdefault(kind, []).append((row_index, text))
            kinds = {kind: rows for kind, rows in kinds.items() if kind}
            if len(kinds) < 2:
                continue

            kind_items = sorted(kinds.items(), key=lambda item: len(item[1]), reverse=True)
            primary_kind, primary_rows = kind_items[0]
            secondary_kind, secondary_rows = kind_items[1]
            preview_rows = [primary_rows[0][0], secondary_rows[0][0]]
            description = (
                f"In sheet `{sheet_key}`, column `{column_name}` mixes different time/unit formats."
            )
            question = (
                f"I noticed that in `{file_name}` / `{sheet_name}`, column `{column_name}` mixes different formats such as "
                f"`{primary_rows[0][1]}` and `{secondary_rows[0][1]}`. "
                "Should I normalize these values into one consistent format before using them in the calculation?"
            )
            issues.append(
                cls._make_issue(
                    issue_type="unit_or_time_format",
                    description=description,
                    question=question,
                    details_markdown=cls._build_markdown_preview(df, preview_rows, [column_name]),
                    preview_kind="cell_issue",
                    metadata={
                        "sheet_key": sheet_key,
                        "column": column_name,
                        "formats": [primary_kind, secondary_kind],
                    },
                )
            )
            if len(issues) >= 1:
                break
        return issues

    @classmethod
    def _detect_missing_period_endpoint_issues(
        cls,
        workbook_view: Dict[str, pd.DataFrame],
        user_question: str,
    ) -> List[Dict[str, Any]]:
        requested_years = cls._extract_requested_years(user_question)
        if not requested_years:
            return []

        issues: List[Dict[str, Any]] = []
        requested_set = set(requested_years)
        for sheet_key, df in workbook_view.items():
            available_years = cls._extract_available_years(df)
            if not available_years:
                continue
            available_set = set(available_years)
            missing_years = sorted(requested_set - available_set)
            if not missing_years:
                continue
            file_name, sheet_name = cls._extract_sheet_parts(sheet_key)
            latest_available = max(available_years)
            details_lines = [
                "Context preview:",
                f"Requested years: {', '.join(str(year) for year in requested_years)}",
                f"Available years: {', '.join(str(year) for year in available_years[:12])}",
            ]
            description = (
                f"In sheet `{sheet_key}`, requested period values {missing_years} are missing from the available data."
            )
            question = (
                f"I noticed that `{file_name}` / `{sheet_name}` does not contain the requested year(s) "
                f"{', '.join(str(year) for year in missing_years)}. "
                f"The latest available year is `{latest_available}`. Should I use the latest available year instead and state that assumption in the result?"
            )
            issues.append(
                cls._make_issue(
                    issue_type="missing_period_endpoint",
                    description=description,
                    question=question,
                    details_markdown="\n".join(details_lines),
                    preview_kind="period",
                    metadata={
                        "sheet_key": sheet_key,
                        "requested_years": requested_years,
                        "available_years": available_years,
                    },
                )
            )
            if len(issues) >= 1:
                break
        return issues

    @classmethod
    def _detect_duplicate_conflicting_row_issues(
        cls,
        sheet_key: str,
        df: pd.DataFrame,
        user_question: str,
    ) -> List[Dict[str, Any]]:
        if df is None or df.empty:
            return []
        file_name, sheet_name = cls._extract_sheet_parts(sheet_key)
        issues: List[Dict[str, Any]] = []
        key_columns = [str(col) for col in getattr(df, "columns", []) if cls._is_unique_key_like_header(str(col))]
        if not key_columns:
            return []

        for key_col in key_columns:
            if cls._has_more_granular_unique_key(df, key_col):
                continue
            working = df.copy()
            working["__key__"] = working[key_col].map(cls._normalize_cell_text)
            working["__row_index__"] = list(range(len(working)))
            working = working[working["__key__"] != ""]
            if working.empty:
                continue
            duplicate_keys = working["__key__"].value_counts()
            duplicate_keys = duplicate_keys[duplicate_keys > 1].index.tolist()
            for duplicate_key in duplicate_keys:
                sample = working[working["__key__"] == duplicate_key].head(2)
                compare_rows = []
                for _, record in sample.iterrows():
                    row_index = int(record["__row_index__"])
                    compare_rows.append({
                        "row_index": row_index,
                        "values": {
                            str(col): cls._normalize_cell_text(df.iloc[row_index][col])
                            for col in getattr(df, "columns", [])
                        },
                    })
                if len(compare_rows) < 2:
                    continue
                differing_columns = []
                for column_name in map(str, getattr(df, "columns", [])):
                    values = {row["values"].get(column_name, "") for row in compare_rows}
                    values = {value for value in values if value != ""}
                    if len(values) > 1:
                        differing_columns.append(column_name)
                if not differing_columns:
                    continue
                if len(differing_columns) == 1 and cls._is_entity_descriptor_header(differing_columns[0]):
                    continue
                event_columns = [
                    column_name for column_name in differing_columns
                    if cls._is_event_granularity_column(df, column_name)
                ]
                if event_columns:
                    non_event_differences = [
                        column_name for column_name in differing_columns
                        if column_name not in event_columns
                    ]
                    if not non_event_differences or all(
                        cls._is_measure_like_column(df, column_name) for column_name in non_event_differences
                    ):
                        continue
                if any(cls._is_period_like_column(df[column_name], column_name) for column_name in differing_columns):
                    non_period_differences = [
                        column_name for column_name in differing_columns
                        if not cls._is_period_like_column(df[column_name], column_name)
                    ]
                    if not non_period_differences or all(
                        cls._is_measure_like_column(df, column_name) for column_name in non_period_differences
                    ):
                        continue
                description = (
                    f"In sheet `{sheet_key}`, key `{key_col} = {duplicate_key}` appears in multiple rows with conflicting values."
                )
                question = (
                    f"I noticed that in `{file_name}` / `{sheet_name}`, `{key_col} = {duplicate_key}` appears more than once, "
                    f"and the rows differ in fields like `{differing_columns[0]}`. "
                    "Should I keep one row as authoritative, or treat both rows as valid records?"
                )
                issues.append(
                    cls._make_issue(
                        issue_type="duplicate_conflicting_rows",
                        description=description,
                        question=question,
                        details_markdown=cls._build_markdown_preview(
                            df,
                            [row["row_index"] for row in compare_rows],
                            [key_col] + differing_columns[:2],
                        ),
                        preview_kind="row_pair",
                        metadata={
                            "sheet_key": sheet_key,
                            "key_column": key_col,
                            "key_value": duplicate_key,
                            "differing_columns": differing_columns,
                        },
                    )
                )
                if len(issues) >= 1:
                    return issues
        return issues

    @classmethod
    def _detect_semantic_anomaly_issues(
        cls,
        sheet_key: str,
        df: pd.DataFrame,
        user_question: str,
    ) -> List[Dict[str, Any]]:
        if df is None or df.empty:
            return []

        file_name, sheet_name = cls._extract_sheet_parts(sheet_key)
        candidate_columns = list(dict.fromkeys(
            [
                col for col in cls._relevant_columns(df, user_question)
                if cls._is_metric_like_column(col)
            ] + [
                str(col) for col in getattr(df, "columns", [])
                if cls._is_metric_like_column(str(col))
            ]
        ))

        issues: List[Dict[str, Any]] = []
        for column_name in candidate_columns[:6]:
            series = cls._coerce_numeric_series(df[column_name])
            valid = series.dropna()
            if len(valid) < 4:
                continue

            lower_bound, upper_bound = cls._semantic_numeric_bounds(column_name)
            median = float(valid.median())
            positive = valid[valid > 0]
            positive_median = float(positive.median()) if not positive.empty else None
            requires_non_negative = cls._requires_non_negative_metric(column_name)
            suspicious_rows: list[int] = []

            for row_index, numeric_value in series.items():
                if pd.isna(numeric_value):
                    continue
                value = float(numeric_value)
                suspicious = False
                if lower_bound is not None and value < lower_bound:
                    suspicious = True
                if upper_bound is not None and value > upper_bound:
                    suspicious = True
                if not suspicious and positive_median is not None and positive_median > 0:
                    if value > positive_median * 5 and value > median * 3:
                        suspicious = True
                    if requires_non_negative and value < 0:
                        suspicious = True
                    if requires_non_negative and 0 < value < positive_median * 0.02 and positive_median >= 50:
                        suspicious = True
                if suspicious:
                    suspicious_rows.append(int(row_index))

            if not suspicious_rows:
                continue

            row_index = suspicious_rows[0]
            excel_row = cls._excel_row_number(df, row_index)
            context_label = cls._row_context_label(df, row_index, column_name)
            raw_value = cls._normalize_cell_text(df.iloc[row_index][column_name])
            description = (
                f"In sheet `{sheet_key}`, column `{column_name}` contains a value that looks implausible at Excel row {excel_row}."
            )
            question = (
                f"I noticed that in `{file_name}` / `{sheet_name}`, column `{column_name}` has value `{raw_value}` at Excel row {excel_row}"
            )
            if context_label:
                question += f" ({context_label})"
            question += (
                ". This value looks inconsistent with the rest of the table or outside a plausible domain range. "
                "Should I treat it as a data error and correct/normalize it before continuing?"
            )
            preview_rows = [row_index - 1, row_index] if row_index > 0 else [row_index]
            issues.append(
                cls._make_issue(
                    issue_type="semantic_anomaly",
                    description=description,
                    question=question,
                    details_markdown=cls._build_markdown_preview(df, preview_rows, [column_name]),
                    preview_kind="cell_issue",
                    metadata={
                        "sheet_key": sheet_key,
                        "column": column_name,
                        "row_index": row_index,
                        "excel_row": excel_row,
                        "value": raw_value,
                    },
                )
            )
            if len(issues) >= 1:
                return issues
        return issues

    @classmethod
    def _detect_blocking_data_issues(cls, workbook_view, user_question: str) -> List[Dict[str, Any]]:
        if cls._is_self_reporting_issue_task(user_question):
            return []
        if should_skip_diagnose(user_question):
            return []

        coerced = cls._coerce_workbook_view(workbook_view)
        if not coerced:
            return []

        issues: List[Dict[str, Any]] = []
        cross_sheet_detectors = (
            cls._detect_missing_key_column_issues,
            cls._detect_missing_period_endpoint_issues,
        )
        for detector in cross_sheet_detectors:
            found = detector(coerced, user_question)
            issues.extend(found)
            if len(issues) >= 4:
                return issues[:4]

        row_alignment_sheets: set[str] = set()
        for sheet_key, df in coerced.items():
            found = cls._detect_row_alignment_issues(sheet_key, df, user_question)
            if found:
                row_alignment_sheets.add(sheet_key)
                issues.extend(found)
                if len(issues) >= 4:
                    return issues[:4]

        detectors = (
            (cls._detect_missing_value_issues, True),
            (cls._detect_semantic_anomaly_issues, True),
            (cls._detect_unit_or_time_format_issues, True),
            (cls._detect_format_inconsistency_issues, True),
            (cls._detect_duplicate_conflicting_row_issues, True),
            (cls._detect_internal_blank_row_issues, True),
            (cls._detect_duplicate_header_issues, False),
            (cls._detect_conflicting_key_mapping_issues, False),
        )
        for sheet_key, df in coerced.items():
            if sheet_key in row_alignment_sheets:
                continue
            for detector, needs_question in detectors:
                if needs_question:
                    found = detector(sheet_key, df, user_question)  # type: ignore[misc]
                else:
                    found = detector(sheet_key, df)  # type: ignore[misc]
                issues.extend(found)
                if len(issues) >= 4:
                    return issues[:4]
        return issues[:4]

    def _ask_llm(self, prompt: str) -> Optional[bool]:
        messages = [{"role": "user", "content": prompt}]
        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=messages,
            )
            content = (response.choices[0].message.content or "").strip()
        except Exception as exc:
            logger.warning("Diagnose router LLM request failed: %s", exc)
            return None

        parsed = self._parse_yes_no(content)
        if parsed is None:
            logger.warning("Diagnose router invalid output: %r", content)
        return parsed

    @staticmethod
    def _parse_yes_no(text: str) -> Optional[bool]:
        upper = (text or "").strip().upper()
        if upper.startswith("YES"):
            return True
        if upper.startswith("NO"):
            return False
        return None
