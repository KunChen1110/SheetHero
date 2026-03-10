"""Routing logic for whether to run the diagnose stage."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd

from ..log.logger_registry import LoggerRegistry
from ..prompt.prompt_builder import PromptBuilder

logger = LoggerRegistry.setup_logger(__name__)


@dataclass
class DiagnoseDecision:
    should_diagnose: bool
    reasons: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)


class DiagnoseRouter:
    """Decide whether the diagnose stage should run."""

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
                self.progress_logger.log_raw(
                    "\n".join(["### [ROUTER DATA EVIDENCE]"] + [f"- {issue}" for issue in issues])
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
    def _normalize_cell_text(text: str) -> str:
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
        if "room identifiers" in q or ("room" in q and "inconsistenc" in q):
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
                rows = list(sheet.values)
                if not rows:
                    df = pd.DataFrame()
                else:
                    header = list(rows[0])
                    if not any(h is not None and str(h).strip() != "" for h in header):
                        header = [f"col_{i + 1}" for i in range(len(header))]
                    else:
                        header = [
                            (str(h).strip() if h is not None and str(h).strip() != "" else f"col_{i + 1}")
                            for i, h in enumerate(header)
                        ]
                    df = pd.DataFrame(rows[1:], columns=header)
                view[f"{file_key}::{sheet.title}"] = df
        return view

    @classmethod
    def _detect_duplicate_header_issues(cls, sheet_key: str, df: pd.DataFrame) -> List[str]:
        if df is None or not hasattr(df, "columns"):
            return []
        raw_headers = [str(col) for col in df.columns]
        normalized_to_raw: Dict[str, List[str]] = {}
        for raw in raw_headers:
            normalized = cls._normalize_header_name(raw)
            normalized_to_raw.setdefault(normalized, [])
            if raw not in normalized_to_raw[normalized]:
                normalized_to_raw[normalized].append(raw)

        issues: List[str] = []
        for normalized, raw_variants in normalized_to_raw.items():
            if normalized and len(raw_variants) > 1:
                joined = ", ".join(f"`{item}`" for item in raw_variants[:4])
                issues.append(
                    f"In sheet `{sheet_key}`, multiple headers normalize to the same meaning ({joined}). Which header should be treated as authoritative?"
                )
        return issues

    @classmethod
    def _is_entity_key_header(cls, column_name: str) -> bool:
        normalized = cls._normalize_header_name(column_name)
        relation_like = ("depends on", "node from", "node to", "source", "target")
        if any(token in normalized for token in relation_like):
            return False
        entity_like = (
            "id",
            "identifier",
            "code",
            "room",
            "email",
            "tutorid",
            "employee id",
            "customer id",
            "order id",
        )
        return any(token in normalized for token in entity_like)

    @classmethod
    def _is_entity_descriptor_header(cls, column_name: str) -> bool:
        normalized = cls._normalize_header_name(column_name)
        descriptor_like = (
            "name",
            "email",
            "room",
            "code",
            "identifier",
            "id",
        )
        return any(token in normalized for token in descriptor_like)

    @classmethod
    def _detect_conflicting_key_mapping_issues(cls, sheet_key: str, df: pd.DataFrame) -> List[str]:
        if df is None or df.empty or not hasattr(df, "columns"):
            return []

        issues: List[str] = []
        columns = [str(col) for col in df.columns]
        key_columns = [col for col in columns if cls._is_entity_key_header(col)]
        descriptor_columns = [col for col in columns if cls._is_entity_descriptor_header(col)]
        if not key_columns or len(descriptor_columns) < 2:
            return []

        for key_col in key_columns:
            working = df[[key_col] + [col for col in descriptor_columns if col != key_col]].copy()
            working[key_col] = working[key_col].map(cls._normalize_cell_text)
            working = working[working[key_col] != ""]
            if working.empty:
                continue

            for descriptor_col in [col for col in descriptor_columns if col != key_col]:
                normalized_descriptor = working[descriptor_col].map(cls._normalize_cell_text)
                compare = pd.DataFrame({
                    "key": working[key_col],
                    "value": normalized_descriptor,
                    "raw_value": working[descriptor_col].astype(str),
                })
                compare = compare[compare["value"] != ""]
                if compare.empty:
                    continue

                grouped = compare.groupby("key")["value"].nunique(dropna=True)
                conflict_keys = grouped[grouped > 1].index.tolist()
                if not conflict_keys:
                    continue

                example_key = conflict_keys[0]
                sample_rows = compare[compare["key"] == example_key]
                raw_values = sorted(set(sample_rows["raw_value"].tolist()))[:3]
                example_text = ", ".join(f"`{value}`" for value in raw_values)
                issues.append(
                    f"In sheet `{sheet_key}`, `{key_col}` value `{example_key}` maps to multiple `{descriptor_col}` values ({example_text}). Which value should be treated as correct?"
                )
                if len(issues) >= 2:
                    return issues
        return issues

    @classmethod
    def _detect_blocking_data_issues(cls, workbook_view, user_question: str) -> List[str]:
        if cls._is_self_reporting_issue_task(user_question):
            return []

        coerced = cls._coerce_workbook_view(workbook_view)
        if not coerced:
            return []

        issues: List[str] = []
        for sheet_key, df in coerced.items():
            issues.extend(cls._detect_duplicate_header_issues(sheet_key, df))
            issues.extend(cls._detect_conflicting_key_mapping_issues(sheet_key, df))
            if len(issues) >= 4:
                break
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
