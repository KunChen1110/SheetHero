"""LLM-driven data cleaning stage."""

import json
import re
from typing import Any, Dict, List, Optional

from ...log.logger_registry import LoggerRegistry
from ...prompt.prompt_builder import PromptBuilder
from ..understanding.context_builder import ExcelContextBuilder
from ..base.stage import Stage
from ..base.llm_utils import call_llm
from .policy_executor import apply_policy_plan

logger = LoggerRegistry.setup_logger(__name__)


_FILL_MISSING_ACTION_RE = re.compile(
    r"^Fill the missing value in `(?P<column>[^`]+)`"
    r"(?: at Excel row (?P<row>\d+))?"
    r" in `(?P<sheet_key>[^`]+)` with (?P<value>.+?)\.$"
)


class DataCleaningStage(Stage):
    """Cleaning stage driven by action list (LLM-produced)."""

    def __init__(self, client, deployment: str, token_budget: int = 6000,
                 progress_logger=None, prompt_profile: str = "online_rich"):
        self.client = client
        self.deployment = deployment
        self.token_budget = token_budget
        self.progress_logger = progress_logger
        self._schema_changed = False
        self._is_offline = prompt_profile == "offline_strict"

    def apply_policy_plans(self, sandbox, policy_plans: List[dict]) -> Dict[str, Any]:
        workbooks = getattr(sandbox, "workbooks", {}) or {}
        report = {"applied_actions": [], "skipped_actions": [], "notes": []}
        for policy_plan in policy_plans or []:
            report_key, message = apply_policy_plan(workbooks, policy_plan)
            if message:
                report[report_key].append(message)
        return report

    def apply(
        self,
        sandbox,
        actions: List[str],
        policy_plans: Optional[List[dict]] = None,
    ) -> Dict[str, Any]:
        actions = actions or []
        policy_plans = policy_plans or []
        workbooks = getattr(sandbox, "workbooks", {}) or {}
        report = {"applied_actions": [], "skipped_actions": [], "notes": []}

        self._log_progress(
            f"[CLEANING] start actions={len(actions)}"
        )
        self._log_progress(
            f"[CLEANING] actions={self._truncate(actions)}"
        )
        if policy_plans:
            self._log_progress(
                f"[CLEANING] policy_plans={self._truncate(policy_plans)}"
            )
            policy_report = self.apply_policy_plans(sandbox, policy_plans)
            report["applied_actions"].extend(policy_report.get("applied_actions", []))
            report["skipped_actions"].extend(policy_report.get("skipped_actions", []))
            report["notes"].extend(policy_report.get("notes", []))

        if not actions:
            self._schema_changed = bool(report["applied_actions"])
            self._log_progress("[CLEANING] no actions, skipping.")
            self._log_cleaning_report(report)
            return report

        deterministic_report, remaining_actions = self._apply_deterministic_actions(
            workbooks=workbooks,
            actions=actions,
        )
        report["applied_actions"].extend(deterministic_report.get("applied_actions", []))
        report["skipped_actions"].extend(deterministic_report.get("skipped_actions", []))
        report["notes"].extend(deterministic_report.get("notes", []))
        if not remaining_actions:
            self._schema_changed = bool(report["applied_actions"])
            self._log_progress(
                f"[CLEANING] completed actions={len(report.get('applied_actions', []))}"
            )
            self._log_cleaning_report(report)
            return report

        schema_summary = ExcelContextBuilder(
            excel_paths=list(workbooks.keys()),
            workbooks=workbooks
        ).build(total_token_budget=self.token_budget)

        prompt_text = PromptBuilder().build_cleaning_code_prompt(
            schema_summary=schema_summary,
            actions=remaining_actions
        )
        if self.progress_logger:
            self.progress_logger.log_raw("### [CLEANING PROMPT]\n" + prompt_text)

        self._log_progress("[CLEANING] generating cleaning code")
        llm_kwargs = {}
        if self._is_offline:
            llm_kwargs["max_tokens"] = 1024
        try:
            code = call_llm(self.client, self.deployment, [{"role": "user", "content": prompt_text}], **llm_kwargs)
        except Exception as exc:
            report["notes"].append(f"Cleaning code generation failed: {exc}")
            return report
        code = self._extract_code(code)

        if self.progress_logger:
            self.progress_logger.log_raw("### [CLEANING CODE]\n" + code)

        try:
            result = sandbox.run(code)
            stdout = (result or {}).get("stdout", "")
            stderr = (result or {}).get("stderr", "")

            if stderr:
                report["notes"].append(stderr.strip())

            parsed = self._parse_report(stdout)
            if parsed:
                report.update(parsed)
            elif stdout:
                report["notes"].append(stdout.strip())
        except Exception as exc:
            report["notes"].append(f"Cleaning code execution failed: {exc}")

        self._schema_changed = True
        self._log_progress(
            f"[CLEANING] completed actions={len(report.get('applied_actions', []))}"
        )
        self._log_cleaning_report(report)
        return report

    def _apply_deterministic_actions(
        self,
        workbooks: Dict[str, Any],
        actions: List[str],
    ) -> tuple[Dict[str, Any], List[str]]:
        report = {"applied_actions": [], "skipped_actions": [], "notes": []}
        remaining: list[str] = []
        for action in actions:
            applied = self._apply_single_deterministic_action(workbooks, action)
            if applied is None:
                remaining.append(action)
                continue
            report_key, message = applied
            if message:
                report[report_key].append(message)
        if report["applied_actions"]:
            self._log_progress(
                f"[CLEANING] deterministic actions applied={len(report['applied_actions'])}"
            )
        return report, remaining

    def _apply_single_deterministic_action(
        self,
        workbooks: Dict[str, Any],
        action: str,
    ) -> Optional[tuple[str, str]]:
        text = str(action or "").strip()
        match = _FILL_MISSING_ACTION_RE.match(text)
        if not match:
            return None

        column_name = match.group("column").strip()
        row_text = match.group("row")
        sheet_key = match.group("sheet_key").strip()
        value_text = match.group("value").strip()
        excel_row = int(row_text) if row_text else None

        workbook, worksheet = self._resolve_sheet(workbooks, sheet_key)
        if workbook is None or worksheet is None:
            return "skipped_actions", f"Could not resolve sheet `{sheet_key}` for action: {text}"
        if excel_row is None:
            return "skipped_actions", f"Missing Excel row reference for action: {text}"

        column_index = self._find_column_index(worksheet, column_name)
        if column_index is None:
            return "skipped_actions", f"Could not resolve column `{column_name}` in `{sheet_key}`."

        parsed_value = self._parse_action_value(value_text)
        cell = worksheet.cell(row=excel_row, column=column_index)
        if cell.value not in (None, ""):
            return "skipped_actions", (
                f"Skipped deterministic fill for `{column_name}` at Excel row {excel_row} in `{sheet_key}` because the cell already has a value."
            )
        cell.value = parsed_value
        return "applied_actions", text

    @staticmethod
    def _resolve_sheet(workbooks: Dict[str, Any], sheet_key: str):
        file_part = sheet_key
        sheet_name = ""
        if "::" in sheet_key:
            file_part, sheet_name = sheet_key.split("::", 1)
        file_part = file_part.strip()
        sheet_name = (sheet_name or "").strip()

        for path, workbook in workbooks.items():
            if path == file_part or path.endswith(file_part):
                if not sheet_name:
                    active = workbook.active
                    return workbook, active
                if sheet_name in workbook.sheetnames:
                    return workbook, workbook[sheet_name]
        return None, None

    @staticmethod
    def _normalize_header(value: Any) -> str:
        return re.sub(r"\s+", " ", str(value or "").strip()).lower()

    def _find_column_index(self, worksheet, column_name: str) -> Optional[int]:
        normalized_target = self._normalize_header(column_name)
        for row_idx in range(1, min(worksheet.max_row, 20) + 1):
            for col_idx in range(1, worksheet.max_column + 1):
                cell_value = worksheet.cell(row=row_idx, column=col_idx).value
                if self._normalize_header(cell_value) == normalized_target:
                    return col_idx
        return None

    @staticmethod
    def _parse_action_value(value_text: str):
        cleaned = str(value_text or "").strip()
        if cleaned.startswith(("£", "$", "€")):
            cleaned = cleaned[1:].strip()
        cleaned = cleaned.replace(",", "")
        if re.fullmatch(r"[-+]?\d+", cleaned):
            return int(cleaned)
        if re.fullmatch(r"[-+]?\d+(?:\.\d+)?", cleaned):
            return float(cleaned)
        if cleaned.lower() in {"blank", "empty", "null", "none"}:
            return ""
        return cleaned

    @staticmethod
    def _extract_code(raw: str) -> str:
        """Extract executable Python from LLM output that may contain markdown."""
        raw = (raw or "").strip()
        # Try to extract from ```python ... ``` fences first
        blocks = re.findall(r"```python\s*(.*?)```", raw, re.DOTALL | re.IGNORECASE)
        if blocks:
            # Use the longest code block (skip short summary blocks)
            return max(blocks, key=len).strip()
        # Try generic ``` fences
        blocks = re.findall(r"```\s*(.*?)```", raw, re.DOTALL)
        if blocks:
            return max(blocks, key=len).strip()
        # No fences — assume the whole response is code, strip markdown artifacts
        lines = []
        for line in raw.splitlines():
            stripped = line.strip()
            # Skip markdown headers, horizontal rules, emoji lines, blank prose
            if stripped.startswith("#") or stripped.startswith("---"):
                continue
            if stripped.startswith("- ") and not stripped.startswith("- "):
                continue
            lines.append(line)
        return "\n".join(lines).strip()

    def last_run_affects_schema(self) -> bool:
        return self._schema_changed

    @staticmethod
    def _truncate(value: Any, limit: int = 300) -> str:
        text = str(value)
        if len(text) <= limit:
            return text
        return text[:limit] + "..."

    def _log_progress(self, message: str) -> None:
        if self.progress_logger is None:
            logger.info(message)
            return
        self.progress_logger.log(message, to_terminal=False)

    def _log_cleaning_report(self, report: Dict[str, Any]) -> None:
        if self.progress_logger is None:
            return

        lines = ["### [CLEANING REPORT]"]
        lines.append(f"Applied actions: {report.get('applied_actions', [])}")
        lines.append(f"Skipped actions: {report.get('skipped_actions', [])}")
        if report.get("notes"):
            lines.append("Notes:")
            lines.extend([f"- {note}" for note in report.get("notes", [])])
        self.progress_logger.log_raw("\n".join(lines))

    @staticmethod
    def _parse_report(stdout: str) -> Optional[Dict[str, Any]]:
        stdout = (stdout or "").strip()
        if not stdout:
            return None
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        return {
            "applied_actions": payload.get("applied_actions", []),
            "skipped_actions": payload.get("skipped_actions", []),
            "notes": payload.get("notes", []),
        }
