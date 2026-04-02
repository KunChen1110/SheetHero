"""Shared LLM call helper with exponential-backoff retry for pipeline stages."""

from __future__ import annotations

import random
import re
import time
from typing import Any, Optional

from openai import RateLimitError

from ...log.logger_registry import LoggerRegistry

logger = LoggerRegistry.setup_logger(__name__)


def call_llm(
    client: Any,
    deployment: str,
    messages: list,
    max_retries: int = 5,
    base_delay: float = 1.0,
    **kwargs: Any,
) -> str:
    """
    Call the LLM with exponential-backoff retry for rate limits and transient errors.

    Args:
        client:      OpenAI-compatible client instance.
        deployment:  Model name / deployment string.
        messages:    List of message dicts for the chat completion.
        max_retries: Maximum number of attempts before raising.
        base_delay:  Base delay (seconds) for exponential backoff on generic errors.
        **kwargs:    Extra keyword arguments forwarded to client.chat.completions.create
                     (e.g. max_tokens=80).

    Returns:
        The content string from the first choice of the LLM response.

    Raises:
        The last exception if all retries are exhausted.
    """
    last_exception: Optional[Exception] = None

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=deployment,
                messages=messages,
                **kwargs,
            )
            return response.choices[0].message.content or ""

        except RateLimitError as e:
            last_exception = e
            logger.warning("Rate limit hit, attempt %d/%d: %s", attempt + 1, max_retries, e)
            wait_time = _extract_wait_seconds(str(e))
            if attempt < max_retries - 1:
                delay = (wait_time + random.uniform(1, 3)) if wait_time else 10.0
                logger.info("Waiting %.1f s (rate-limit back-off)", delay)
                time.sleep(delay)
            else:
                logger.error("All %d attempts failed due to rate limiting", max_retries)

        except Exception as e:
            last_exception = e
            logger.error("LLM API error, attempt %d/%d: %s", attempt + 1, max_retries, e)
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                logger.info("Waiting %.1f s before retry", delay)
                time.sleep(delay)
            else:
                logger.error("All %d attempts failed", max_retries)

    if last_exception:
        raise last_exception
    return ""  # unreachable; satisfies type checker


def _extract_wait_seconds(error_message: str) -> Optional[int]:
    """Parse the suggested retry delay from a rate-limit error message."""
    lower = error_message.lower()
    for pattern in (r"try again in (\d+) seconds?", r"retry after (\d+) seconds?"):
        m = re.search(pattern, lower)
        if m:
            return int(m.group(1))
    return None
