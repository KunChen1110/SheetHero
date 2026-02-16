"""Interact stage for non-spreadsheet queries."""

import random
import time
from typing import Optional

from openai import RateLimitError

from ...log.logger_registry import LoggerRegistry
from ...prompt.prompt_builder import PromptBuilder
from ..base.stage import Stage

logger = LoggerRegistry.setup_logger(__name__)


class InteractStage(Stage):
    """Lightweight LLM pass-through for text-only interactions."""

    def __init__(self, client, deployment: str, progress_logger=None):
        self.client = client
        self.deployment = deployment
        self.progress_logger = progress_logger

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
        response = self._get_llm_response(messages)
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

    def summarize_context(self, user_message: str) -> str:
        prompt_text = PromptBuilder().build_interact_context_summary_prompt(
            user_message=user_message
        )
        messages = [{"role": "user", "content": prompt_text}]
        if self.progress_logger:
            self.progress_logger.log_raw(
                "\n".join(["### [INTERACT CONTEXT PROMPT]", prompt_text])
            )
        response = self._get_llm_response(messages)
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
        response = self._get_llm_response(messages)
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

    def _get_llm_response(self, messages: list, max_retries: int = 5, base_delay: float = 1.0) -> str:
        last_exception = None
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.deployment,
                    messages=messages,
                )
                return response.choices[0].message.content
            except RateLimitError as e:
                last_exception = e
                logger.warning(f"Rate limit hit, attempt {attempt + 1}/{max_retries}: {str(e)}")
                wait_time = self._extract_wait_time_from_error(str(e))
                if attempt < max_retries - 1:
                    if wait_time:
                        delay = wait_time + random.uniform(1, 3)
                    else:
                        delay = 10
                    time.sleep(delay)
                else:
                    logger.error("All attempts failed due to rate limiting")
                    break
            except Exception as e:
                last_exception = e
                logger.error(f"API error, attempt {attempt + 1}/{max_retries}: {str(e)}")
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    time.sleep(delay)
                else:
                    logger.error("All attempts failed")
                    break
        if last_exception:
            raise last_exception

    def _extract_wait_time_from_error(self, error_message: str) -> Optional[int]:
        try:
            import re
            match = re.search(r'try again in (\d+) seconds?', error_message.lower())
            if match:
                return int(match.group(1))
            match = re.search(r'retry after (\d+) seconds?', error_message.lower())
            if match:
                return int(match.group(1))
            return None
        except Exception:
            return None
