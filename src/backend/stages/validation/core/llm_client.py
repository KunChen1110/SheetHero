"""LLM client wrapper for validation."""

import os
import time
import random

from ....log.logger_registry import LoggerRegistry
from ...base.llm_client import BaseLLMClient

logger = LoggerRegistry.setup_logger(__name__)


class ValidationLLMClient(BaseLLMClient):
    """Handles LLM calls for validation with retry logic."""

    def __init__(self, client, deployment: str):
        super().__init__(client, deployment)
        self._max_backoff_seconds = int(os.getenv("SHEETHERO_MAX_BACKOFF_SECONDS", "20"))

    def get_response(self, messages: list, max_retries: int = 5,
                     max_tokens: int | None = None) -> str:
        last_exception = None

        for attempt in range(max_retries):
            try:
                create_kwargs = {
                    "model": self.deployment,
                    "messages": messages,
                    "stream": False,
                }
                if max_tokens is not None:
                    create_kwargs["max_tokens"] = max_tokens
                response = self.client.chat.completions.create(**create_kwargs)
                if not getattr(response, "choices", None) or len(response.choices) == 0:
                    raise ValueError("LLM returned no choices (empty response)")
                msg = response.choices[0].message
                content = getattr(msg, "content", None)
                return content if content is not None else ""

            except Exception as e:
                last_exception = e
                logger.error(
                    f"LLM Error (attempt {attempt + 1}/{max_retries}): {str(e)}"
                )

                if attempt < max_retries - 1:
                    delay = min((2 ** attempt) + random.uniform(0, 0.5), self._max_backoff_seconds)
                    time.sleep(delay)

        raise last_exception
