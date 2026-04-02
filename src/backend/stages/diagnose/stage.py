"""Read-only diagnose stage for question list generation."""

import os
from typing import List, Optional

from ...log.logger_registry import LoggerRegistry
from ...prompt.prompt_builder import PromptBuilder
from .cropper import sample_workbook_view
from .reporting import build_diagnose_report
from ..base.stage import Stage
from ..base.llm_utils import call_llm

logger = LoggerRegistry.setup_logger(__name__)


class DiagnoseStage(Stage):
    """Generate a question list from read-only workbooks."""

    def __init__(self, client, deployment: str, excel_paths, sandbox=None,
                 token_budget: int = 50000, progress_logger=None,
                 prompt_profile: str = "online_rich"):
        self.client = client
        self.deployment = deployment
        self.excel_paths = excel_paths
        self.sandbox = sandbox
        self.token_budget = token_budget
        self.progress_logger = progress_logger
        self.prompt_builder = PromptBuilder(profile=prompt_profile)

    def run_readonly(self, workbooks, user_task: str = "") -> List[str]:
        workbook_source = workbooks or {}
        geom_debug_enabled = os.getenv("DIAGNOSE_GEOM_DEBUG") == "1"
        debug_lines: List[str] = []
        def _debug_hook(message: str) -> None:
            debug_lines.append(message)
        sampled = sample_workbook_view(
            workbook_source,
            token_budget=self.token_budget,
            debug_hook=_debug_hook if self.progress_logger else None,
        )
        scan_report = build_diagnose_report(sampled)
        prompt_text = self.prompt_builder.build_diagnose_prompt(user_task, scan_report)
        messages = [{"role": "user", "content": prompt_text}]

        if self.progress_logger:
            self.progress_logger.log("[DIAGNOSE] Generating diagnostic issues", to_terminal=False)
            debug_sections: List[str] = []
            if geom_debug_enabled:
                debug_sections.append(
                    "\n".join(["### [DIAGNOSE SAMPLED TABLES]", scan_report or "No scan results."])
                )
            if debug_lines:
                debug_sections.append(
                    "\n".join(["### [DIAGNOSE GEOM DEBUG]"] + debug_lines)
                )
            if debug_sections:
                self.progress_logger.log_raw("\n\n".join(debug_sections))

        try:
            content = call_llm(self.client, self.deployment, messages)
        except Exception:
            if self.progress_logger:
                self.progress_logger.log_raw("### [DIAGNOSE ERROR]\nLLM request failed.")
            return []


        content = self._strip_code_fences(content)
        self._last_diagnose_code = content
        questions = self._parse_json_list(content) or []

        
        prioritized = self._prioritize_questions(user_task, questions)
        if self.progress_logger and prioritized is not None:
            self.progress_logger.log_raw(
                "\n".join(["### [DIAGNOSE PRIORITIZE OUTPUT]",
                           f"Count: {len(prioritized)}"] + [f"- {q}" for q in prioritized])
            )
        else:
            logger.info(f"Question list generated with {len(questions)} item(s).")
        return prioritized if prioritized is not None else questions

    def _prioritize_questions(self, user_task: str, questions: List[str]) -> Optional[List[str]]:
        if not questions:
            return []
        prompt_text = self.prompt_builder.build_diagnose_prioritize_prompt(user_task, questions)
        messages = [{"role": "user", "content": prompt_text}]
        try:
            content = call_llm(self.client, self.deployment, messages)
        except Exception:
            if self.progress_logger:
                self.progress_logger.log_raw("### [DIAGNOSE PRIORITIZE ERROR]\nLLM request failed.")
            return None
        

        content = self._strip_code_fences(content)
        prioritized = self._parse_json_list(content)
        if prioritized is None:
            if self.progress_logger:
                self.progress_logger.log_raw("### [DIAGNOSE PRIORITIZE ERROR]\nInvalid JSON output")
            return None
        return prioritized

    @staticmethod
    def _strip_code_fences(content: str) -> str:
        import re
        match = re.search(r"```(?:json|python)?\s*(.*?)```", content, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return content.strip()

    @staticmethod
    def _parse_json_list(output: str) -> Optional[List[str]]:
        import json
        try:
            data = json.loads(output.strip())
        except Exception:
            return None
        if not isinstance(data, list):
            return None
        return [str(item) for item in data]

    @staticmethod
    def _parse_questions(content: str) -> List[str]:
        questions = []
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line.startswith("- "):
                continue
            text = line[2:].strip()
            if text:
                questions.append(text)
        return questions
