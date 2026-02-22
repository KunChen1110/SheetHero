"""LLM client wrapper for execution retries and rate limits."""

import os
import random
import re
import time
from typing import Optional

from openai import RateLimitError

from ...log.logger_registry import LoggerRegistry
from ..base.llm_client import BaseLLMClient

logger = LoggerRegistry.setup_logger(__name__)


class ExecutionLLMClient(BaseLLMClient):
    """Handles LLM response retrieval with retry/backoff behavior."""

    def __init__(self, client, deployment: str):
        super().__init__(client, deployment)
        self._max_backoff_seconds = int(os.getenv("SHEETHERO_MAX_BACKOFF_SECONDS", "20"))

    def get_response(self, messages: list, max_retries: int = 5,
                     base_delay: float = 1.0, max_tokens: Optional[int] = None):
        last_exception = None
        create_kwargs = {
            "model": self.deployment,
            "messages": messages,
            "stream": False,
        }
        if max_tokens is not None:
            create_kwargs["max_tokens"] = max_tokens

        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(**create_kwargs)
                if not getattr(response, "choices", None) or len(response.choices) == 0:
                    raise ValueError("LLM returned no choices (empty response)")
                return response.choices[0].message

            except RateLimitError as e:
                last_exception = e
                logger.warning(
                    f"Rate limit hit, attempt {attempt + 1}/{max_retries}: {str(e)}"
                )

                wait_time = self._extract_wait_time_from_error(str(e))

                if attempt < max_retries - 1:
                    if wait_time:
                        delay = min(wait_time, self._max_backoff_seconds) + random.uniform(0.5, 1.5)
                        logger.info(f"Waiting {delay:.1f} seconds as suggested by API")
                    else:
                        delay = min(10, self._max_backoff_seconds)
                        logger.info(f"Waiting {delay:.1f} seconds (exponential backoff)")
                    time.sleep(delay)
                else:
                    logger.error(
                        f"All {max_retries} attempts failed due to rate limiting"
                    )
                    break

            except Exception as e:
                last_exception = e
                logger.error(
                    f"API error, attempt {attempt + 1}/{max_retries}: {str(e)}"
                )

                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    delay = min(delay, self._max_backoff_seconds)
                    logger.info(f"Waiting {delay:.1f} seconds before retry")
                    time.sleep(delay)
                else:
                    logger.error(f"All {max_retries} attempts failed")
                    break

        if last_exception:
            raise last_exception

        raise RuntimeError("Failed to retrieve LLM response")

    @staticmethod
    def _extract_wait_time_from_error(error_message: str) -> Optional[int]:
        try:
            match = re.search(r'try again in (\d+) seconds?', error_message.lower())
            if match:
                return int(match.group(1))

            match = re.search(r'retry after (\d+) seconds?', error_message.lower())
            if match:
                return int(match.group(1))

            return None
        except Exception:
            return None
