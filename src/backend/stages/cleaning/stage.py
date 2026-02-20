"""LLM-driven data cleaning stage."""

import json
from typing import Any, Dict, List, Optional

from ...log.logger_registry import LoggerRegistry
from ...prompt.prompt_builder import PromptBuilder
from ..understanding.context_builder import ExcelContextBuilder

logger = LoggerRegistry.setup_logger(__name__)


class DataCleaningStage:
    """Cleaning stage driven by action list (LLM-produced)."""

    def __init__(self, client, deployment: str, token_budget: int = 6000, progress_logger=None):
        self.client = client
        self.deployment = deployment
        self.token_budget = token_budget
        self.progress_logger = progress_logger
        self._schema_changed = False

    def apply(self, sandbox, actions: List[str]) -> Dict[str, Any]:
        actions = actions or []
        workbooks = getattr(sandbox, "workbooks", {}) or {}
        report = {"applied_actions": [], "skipped_actions": [], "notes": []}

        self._log_progress(
            f"[CLEANING] start actions={len(actions)}"
        )
        self._log_progress(
            f"[CLEANING] actions={self._truncate(actions)}"
        )

        if not actions:
            self._log_progress("[CLEANING] no actions, skipping.")
            return report

        schema_summary = ExcelContextBuilder(
            excel_paths=list(workbooks.keys()),
            workbooks=workbooks
        ).build(total_token_budget=self.token_budget)

        prompt_text = PromptBuilder().build_cleaning_code_prompt(
            schema_summary=schema_summary,
            actions=actions
        )

        self._log_progress("[CLEANING] generating cleaning code")
        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=[{"role": "user", "content": prompt_text}],
        )
        code = (response.choices[0].message.content or "").strip()

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
