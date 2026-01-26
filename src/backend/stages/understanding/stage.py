"""Initial analysis and context generation stage for SheetHero."""

import re
import time
import random
from typing import Dict, Any, Optional
from openai import RateLimitError

from ...log.logger_registry import LoggerRegistry
from ..base.stage import Stage
from ...prompt.prompt_builder import PromptBuilder

logger = LoggerRegistry.setup_logger(__name__)


class UnderstandingStage(Stage):
    """
    Module responsible for generating initial analysis and understanding from Excel context and user questions.
    """

    def __init__(self, client, deployment: str, excel_context_understanding: str):
        """Initialize the UnderstandingStage."""

        self.client = client
        self.deployment = deployment
        self.excel_context_understanding = excel_context_understanding

    def run(self, user_question: str) -> str:
        """
        Generate comprehensive understanding of the user's question in context.

        Combines Excel data context with the user's question to create an analysis plan that guides the execution module.
        """
        logger.info("Starting understanding analysis")

        # Build prompt and get LLM response
        messages = self._create_multimodal_prompt(user_question, self.excel_context_understanding)
        understanding_output = self._get_llm_response(messages)

        logger.info("Understanding analysis completed")
        return understanding_output


    def _create_multimodal_prompt(self, user_question: str, excel_context_understanding: str) -> list:
        """Build prompt combining user question with Excel context."""
        prompt_text = PromptBuilder().build_understanding_prompt(
            user_question,
            excel_context_understanding
        )
        return [{"role": "user", "content": prompt_text}]

    def _get_llm_response(self, messages: list, max_retries: int = 5, base_delay: float = 1.0) -> str:
        """
        Get LLM response with exponential backoff retry for rate limits.
        Retries up to max_retries times, with increasing wait times between attempts.
        """
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

                # Extract wait time from error message if available
                wait_time = self._extract_wait_time_from_error(str(e))

                if attempt < max_retries - 1:
                    if wait_time:
                        delay = wait_time + random.uniform(1, 3)
                        logger.info(f"Waiting {delay:.1f} seconds as suggested by API")
                    else:
                        delay = 10
                        logger.info(f"Waiting {delay:.1f} seconds")

                    time.sleep(delay)
                else:
                    logger.error(f"All {max_retries} attempts failed due to rate limiting")
                    break

            except Exception as e:
                last_exception = e
                logger.error(f"API error, attempt {attempt + 1}/{max_retries}: {str(e)}")

                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    logger.info(f"Waiting {delay:.1f} seconds before retry")
                    time.sleep(delay)
                else:
                    logger.error(f"All {max_retries} attempts failed")
                    break

        if last_exception:
            raise last_exception

    def _extract_wait_time_from_error(self, error_message: str) -> Optional[int]:
        """
        Parse retry wait time from rate limit error messages.
        Looks for patterns like "Try again in X seconds" or "Retry after X seconds".
        """
        try:
            # Look for patterns like "Try again in X seconds"
            match = re.search(r'try again in (\d+) seconds?', error_message.lower())
            if match:
                return int(match.group(1))

            # Look for other patterns like "Retry after X seconds"
            match = re.search(r'retry after (\d+) seconds?', error_message.lower())
            if match:
                return int(match.group(1))

            return None
        except:
            return None
