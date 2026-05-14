"""Interact stage for non-spreadsheet queries."""

from typing import Optional

from ...log.logger_registry import LoggerRegistry
from ...prompt.prompt_builder import PromptBuilder
from ..base.stage import Stage
from ..base.llm_utils import call_llm

logger = LoggerRegistry.setup_logger(__name__)


class InteractStage(Stage):
    """Lightweight LLM pass-through for text-only interactions."""

    def __init__(self, client, deployment: str, progress_logger=None,
                 prompt_profile: str = "online_rich"):
        self.client = client
        self.deployment = deployment
        self.progress_logger = progress_logger
        self._is_offline = prompt_profile == "offline_strict"

    def run(self, user_message: str) -> str:
        prompt_text = (
            "You are a spreadsheet processing agent. The user message is not "
            "spreadsheet-related or no spreadsheet was provided. Answer the user's "
            "request directly and concisely.\n\n"
            f"User: {user_message}"
        )
        messages = [{"role": "user", "content": prompt_text}]
        if self.progress_logger:
            self.progress_logger.log_raw(
                "\n".join(["### [INTERACT PROMPT]", prompt_text])
            )
        llm_kwargs = {}
        if self._is_offline:
            llm_kwargs["max_tokens"] = 256
        response = call_llm(self.client, self.deployment, messages, **llm_kwargs)
        if self.progress_logger:
            self.progress_logger.log_raw(
                "\n".join(["### [INTERACT OUTPUT]", response or ""])
            )
        return response

    def needs_spreadsheet(self, user_message: str) -> bool:
        prompt_text = PromptBuilder().build_interact_needs_spreadsheet_prompt(
            user_message=user_message
        )
        decision = self._ask_yes_no(prompt_text, default=False)
        if self.progress_logger:
            self.progress_logger.log(
                f"[INTERACT] needs_spreadsheet={decision}",
                to_terminal=False
            )
        return decision

    def context_matches(self, user_message: str, context_understanding: str) -> bool:
        prompt_text = PromptBuilder().build_interact_context_match_prompt(
            user_message=user_message,
            context_understanding=context_understanding or ""
        )
        decision = self._ask_yes_no(prompt_text, default=False)
        if self.progress_logger:
            self.progress_logger.log(
                f"[INTERACT] context_matches={decision} context=\"{(context_understanding or '').strip()}\"",
                to_terminal=False
            )
        return decision

    def workbook_matches_request(self, user_message: str, workbook_summary: str) -> bool:
        prompt_text = (
            "You are checking whether the uploaded spreadsheet files match the user's requested task.\n"
            "Do not solve the task. Do not infer missing files.\n\n"
            "Return YES if at least some of the uploaded files contain entities, columns, or data relevant to the task.\n"
            "Not all files need to be directly relevant — a multi-file task may include supporting or reference tables.\n"
            "Return NO only if ALL uploaded files are clearly from a completely unrelated domain (e.g. the task asks about sales but files contain medical records).\n"
            "Cleaning problems inside otherwise relevant files should still be YES.\n\n"
            "Output only YES or NO.\n\n"
            f"User request:\n{user_message}\n\n"
            f"Uploaded workbook summary:\n{workbook_summary or '(empty)'}"
        )
        decision = self._ask_yes_no(prompt_text, default=True)
        if self.progress_logger:
            self.progress_logger.log(
                f"[INTERACT] workbook_matches_request={decision}",
                to_terminal=False,
            )
        return decision

    def summarize_context(self, user_message: str) -> str:
        prompt_text = PromptBuilder().build_interact_context_summary_prompt(
            user_message=user_message
        )
        messages = [{"role": "user", "content": prompt_text}]
        if self.progress_logger:
            self.progress_logger.log_raw(
                "\n".join(["### [INTERACT CONTEXT PROMPT]", prompt_text])
            )
        llm_kwargs = {}
        if self._is_offline:
            llm_kwargs["max_tokens"] = 256
        response = call_llm(self.client, self.deployment, messages, **llm_kwargs)
        summary = (response or "").strip()
        if self.progress_logger:
            self.progress_logger.log_raw(
                "\n".join(["### [INTERACT CONTEXT OUTPUT]", summary])
            )
            self.progress_logger.log(
                f"[INTERACT] context_summary=\"{summary}\"",
                to_terminal=False
            )
        return summary

    def _ask_yes_no(self, prompt_text: str, default: bool = False) -> bool:
        messages = [{"role": "user", "content": prompt_text}]
        if self.progress_logger:
            self.progress_logger.log_raw(
                "\n".join(["### [INTERACT ROUTER PROMPT]", prompt_text])
            )
        llm_kwargs = {}
        if self._is_offline:
            llm_kwargs["max_tokens"] = 64
        response = call_llm(self.client, self.deployment, messages, **llm_kwargs)
        parsed = self._parse_yes_no(response or "")
        if parsed is None:
            return default
        return parsed

    @staticmethod
    def _parse_yes_no(text: str) -> Optional[bool]:
        upper = (text or "").strip().upper()
        if upper.startswith("YES"):
            return True
        if upper.startswith("NO"):
            return False
        return None
