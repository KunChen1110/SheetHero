"""Shared LLM call helper with exponential-backoff retry for pipeline stages."""

from __future__ import annotations

import concurrent.futures
import os
import random
import re
import time
from typing import Any, Optional

from openai import RateLimitError

from ...log.logger_registry import LoggerRegistry

logger = LoggerRegistry.setup_logger(__name__)

_DEFAULT_LLM_TIMEOUT = 300


def _is_thinking_model(deployment: str) -> bool:
    """Return True for models that have chain-of-thought thinking mode (e.g. qwen3)."""
    name = (deployment or "").lower()
    return name.startswith("qwen3")


def _resolve_wall_timeout(deployment: str) -> Optional[int]:
    raw_timeout = os.getenv("SHEETHERO_LLM_TIMEOUT_SECONDS")
    if raw_timeout is not None and raw_timeout.strip():
        try:
            parsed_timeout = int(raw_timeout)
            return None if parsed_timeout <= 0 else parsed_timeout
        except ValueError:
            pass
    if _is_thinking_model(deployment):
        return None
    return _DEFAULT_LLM_TIMEOUT


def call_llm(
    client: Any,
    deployment: str,
    messages: list,
    max_retries: int = 5,
    base_delay: float = 1.0,
    timeout: Optional[int] = None,
    **kwargs: Any,
) -> str:
    """
    Call the LLM with exponential-backoff retry for rate limits and transient errors.

    A wall-clock timeout is enforced via a thread so that slow local models
    (e.g. Ollama qwen3:8b) cannot block the pipeline indefinitely.

    Args:
        client:      OpenAI-compatible client instance.
        deployment:  Model name / deployment string.
        messages:    List of message dicts for the chat completion.
        max_retries: Maximum number of attempts before raising.
        base_delay:  Base delay (seconds) for exponential backoff on generic errors.
        timeout:     Wall-clock seconds before the call is abandoned.  Defaults to
                     the SHEETHERO_LLM_TIMEOUT_SECONDS env-var (120 s).
        **kwargs:    Extra keyword arguments forwarded to client.chat.completions.create
                     (e.g. max_tokens=80).

    Returns:
        The content string from the first choice of the LLM response.

    Raises:
        The last exception if all retries are exhausted.
    """
    last_exception: Optional[Exception] = None
    wall_timeout = (
        None if timeout is not None and timeout <= 0
        else (timeout if timeout is not None else _resolve_wall_timeout(deployment))
    )

    for attempt in range(max_retries):
        try:
            response = _call_with_wall_timeout(
                client, deployment, messages, wall_timeout, **kwargs
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

        except TimeoutError as e:
            # Wall-clock timeout: the model is too slow. Do not retry —
            # retrying would just block for another full timeout window per attempt.
            last_exception = e
            logger.error("Wall-clock timeout on attempt %d/%d: %s", attempt + 1, max_retries, e)
            break

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


def _call_with_wall_timeout(client: Any, deployment: str, messages: list,
                             wall_timeout: Optional[int], **kwargs: Any):
    """Run client.chat.completions.create in a thread and enforce a wall-clock timeout.

    Using shutdown(wait=False) so the main thread is not blocked by the
    underlying HTTP thread if the timeout fires.
    """
    # Note: thinking mode is NOT disabled here for general LLM calls (understanding,
    # validation, QA). qwen3 needs thinking to generate complex structured outputs.
    # Thinking is disabled only in ExecutionLLMClient for code generation speed.

    def _do_call():
        return client.chat.completions.create(
            model=deployment,
            messages=messages,
            **kwargs,
        )

    if wall_timeout is None:
        return _do_call()

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(_do_call)
    try:
        result = future.result(timeout=wall_timeout)
        executor.shutdown(wait=False)
        return result
    except concurrent.futures.TimeoutError:
        executor.shutdown(wait=False)
        raise TimeoutError(
            f"LLM call exceeded wall-clock timeout of {wall_timeout}s "
            f"(model={deployment})"
        )


def _extract_wait_seconds(error_message: str) -> Optional[int]:
    """Parse the suggested retry delay from a rate-limit error message."""
    lower = error_message.lower()
    for pattern in (r"try again in (\d+) seconds?", r"retry after (\d+) seconds?"):
        m = re.search(pattern, lower)
        if m:
            return int(m.group(1))
    return None
