# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Understanding module for initial analysis and context generation."""

import base64
import io
import re
import time
import random
from typing import Dict, Any, Optional

from PIL import Image
from openai import RateLimitError

from utils.logger import setup_logger
from modules.prompts import build_understanding_prompt

logger = setup_logger(__name__)


class UnderstandingModule:
    """
    Module responsible for initial analysis and context generation using multimodal capabilities.
    Processes both table data and table images to extract visual context.
    """

    def __init__(self, client, deployment: str, excel_context_understanding: str):
        """
        Initialize the UnderstandingModule.

        Args:
            client: OpenAI client instance
            deployment: Model deployment name
            excel_context_understanding: Excel context for understanding
            workbook: Excel workbook instance (optional)
        """
        self.client = client
        self.deployment = deployment
        self.excel_context_understanding = excel_context_understanding

    def analyze(self, user_question: str) -> str:
        """
        Analyze the user question and Excel workbook to generate comprehensive understanding.

        Args:
            user_question: The user's query or task
            table_image: Screenshot of the relevant sheet area

        Returns:
            String containing analysis results
        """
        logger.info("Starting understanding analysis")

        messages = self._create_multimodal_prompt(user_question, self.excel_context_understanding)
        understanding_output = self._get_llm_response(messages)

        logger.info("Understanding analysis completed")
        return understanding_output

    def _create_multimodal_prompt(self, user_question: str, excel_context_understanding: str) -> list:
        """Create a multimodal prompt for the LLM."""
        prompt_text = build_understanding_prompt(user_question, excel_context_understanding)
        return [{"role": "user", "content": prompt_text}]

    def _get_llm_response(self, messages: list, max_retries: int = 5, base_delay: float = 1.0) -> str:
        """Get response from the multimodal LLM with retry logic."""
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
        """Extract wait time from rate limit error message."""
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