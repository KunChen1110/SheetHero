"""LLM client wrapper for execution retries and rate limits."""

import concurrent.futures
import os
import random
import re
import time
from typing import Optional

from openai import RateLimitError

from ....log.logger_registry import LoggerRegistry
from ...base.llm_client import BaseLLMClient

logger = LoggerRegistry.setup_logger(__name__)

_DEFAULT_EXECUTION_TIMEOUT = 300


def _is_thinking_model(deployment: str) -> bool:
    """Return True for models with chain-of-thought thinking mode (e.g. qwen3)."""
    return (deployment or "").lower().startswith("qwen3")


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
    return _DEFAULT_EXECUTION_TIMEOUT


class ExecutionLLMClient(BaseLLMClient):
    """Handles LLM response retrieval with retry/backoff behavior."""

    def __init__(self, client, deployment: str):
        super().__init__(client, deployment)
        self._max_backoff_seconds = int(os.getenv("SHEETHERO_MAX_BACKOFF_SECONDS", "20"))
        self._wall_timeout = _resolve_wall_timeout(deployment)

    def get_response(self, messages: list, max_retries: int = 5,
                     base_delay: float = 1.0, max_tokens: Optional[int] = None):
        last_exception = None
        create_kwargs: dict = {
            "model": self.deployment,
            "messages": messages,
            "stream": False,
        }
        if max_tokens is not None:
            create_kwargs["max_tokens"] = max_tokens

        for attempt in range(max_retries):
            try:
                response = self._call_with_wall_timeout(create_kwargs)
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

            except TimeoutError as e:
                # Wall-clock timeout: the model is too slow. Do not retry —
                # retrying would just block for another full timeout window per attempt.
                last_exception = e
                logger.error(
                    f"Wall-clock timeout on attempt {attempt + 1}/{max_retries}: {str(e)}"
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

    def _call_with_wall_timeout(self, create_kwargs: dict):
        """Run the API call in a thread and enforce a wall-clock timeout.

        Using shutdown(wait=False) so the main thread is not blocked by the
        underlying HTTP thread if the timeout fires.
        """
        # qwen3 models benefit from their thinking mode for code generation —
        # do NOT disable it. The timeout controls how long we wait.

        client = self.client

        def _do_call():
            return client.chat.completions.create(**create_kwargs)

        if self._wall_timeout is None:
            return _do_call()

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(_do_call)
        try:
            result = future.result(timeout=self._wall_timeout)
            executor.shutdown(wait=False)
            return result
        except concurrent.futures.TimeoutError:
            executor.shutdown(wait=False)
            raise TimeoutError(
                f"LLM call exceeded wall-clock timeout of {self._wall_timeout}s "
                f"(model={self.deployment})"
            )

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
