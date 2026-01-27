"""LLM client wrapper for validation."""

import time

from ...log.logger_registry import LoggerRegistry
from ..base.llm_client import BaseLLMClient

logger = LoggerRegistry.setup_logger(__name__)


class ValidationLLMClient(BaseLLMClient):
    """Handles LLM calls for validation with retry logic."""

    def __init__(self, client, deployment: str):
        super().__init__(client, deployment)

    def get_response(self, messages: list, max_retries: int = 5) -> str:
        last_exception = None

        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.deployment,
                    messages=messages,
                )

                return response.choices[0].message.content

            except Exception as e:
                last_exception = e
                logger.error(
                    f"LLM Error (attempt {attempt + 1}/{max_retries}): {str(e)}"
                )

                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)

        raise last_exception
