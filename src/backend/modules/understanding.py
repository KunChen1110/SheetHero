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

logger = setup_logger(__name__)


class UnderstandingModule:
    """
    Module responsible for initial analysis and context generation using multimodal capabilities.
    Processes both table data and table images to extract visual context.
    """

    def __init__(self, client, deployment: str, excel_context_understanding: str, workbook=None):
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
        self.workbook = workbook
        self.excel_context_understanding = excel_context_understanding

    def analyze(self, user_question: str, table_image: Optional[Image.Image] = None) -> str:
        """
        Analyze the user question and Excel workbook to generate comprehensive understanding.

        Args:
            user_question: The user's query or task
            table_image: Screenshot of the relevant sheet area

        Returns:
            String containing analysis results
        """
        logger.info("Starting understanding analysis")

        messages = self._create_multimodal_prompt(user_question, self.excel_context_understanding, table_image)
        understanding_output = self._get_llm_response(messages)

        logger.info("Understanding analysis completed")
        return understanding_output

    def _create_multimodal_prompt(self, user_question: str, excel_context_understanding: str,
                                 table_image: Optional[Image.Image]) -> list:
        """Create a multimodal prompt for the LLM."""

        prompt_text = f"""You are an expert Excel data analyst. I need you to analyze the spreadsheet content and visual representation (if provided) to understand the context for answering a specific question.

**User Question:** {user_question}

**Excel Workbook Content:**
{excel_context_understanding}

**Your Task:**
Analyze the Excel content and visual representation (if provided) to provide analysis in the following format EXACTLY. Do NOT provide the actual answer to the user's question - only provide the analysis framework:

1. **Sheet Summary**:
Provide a comprehensive overview including:
- **Workbook Purpose & Domain**: Identify the business context, industry, and primary use case
- **File Organization**: **CRITICAL - Identify if there are MULTIPLE FILES**
  - **If multiple files are present**: Explicitly state "There are X separate Excel files" and list each file:
    * File 1: [filename] contains [description] in sheet [sheetname]
    * File 2: [filename] contains [description] in sheet [sheetname]
    * **IMPORTANT**: Calculations that span multiple files MUST read from each file separately using inspector_multi()
- **Sheet Organization**: Describe how sheets are logically organized and their relationships
  - **CRITICAL for Multi-Sheet Workbooks**: Explicitly list all sheet names and explain:
    * What data each sheet contains
    * How sheets relate to each other (e.g., "Sheet1 and Sheet2 contain data for Class1 and Class2 respectively")
    * Whether sheets have similar structures (same columns, different data)
    * Whether calculations need to combine data across sheets OR across files
- **Data Structure & Types**: Catalog numerical data, text, dates, calculated fields, and hierarchical relationships
  - For each sheet, identify key columns and data types
  - Note if multiple sheets share the same structure

2. **Problem Insights**:
- **Relevant Data Scope**: Identify which specific files, sheets, ranges, or data points are most relevant
  - **For Multi-File Questions**: **CRITICAL** - Explicitly identify which FILES need to be accessed
    * State: "This question requires data from File 1: [name] and File 2: [name]"
    * Specify: "Data must be read from each file separately using inspector_multi() function"
    * Indicate: "The calculation requires combining data from multiple files"
  - **For Multi-Sheet Questions**: Explicitly identify which sheets need to be accessed
  - Specify if the question requires combining data from multiple files OR multiple sheets
  - Indicate the relationship between files/sheets (e.g., "File 1 contains Class A grades, File 2 contains Class B grades, need to calculate overall average across both files")
- **Potential Challenges**: Identify data structure complexities that might affect analysis
  - Multi-sheet operations: Need to ensure consistent column names/structures across sheets
  - Data alignment: Verify that data from different sheets can be properly combined
- **Validation Strategy**: Recommend ways to verify the accuracy of results
  - For multi-sheet calculations: Verify that all relevant sheets were included
  - Check that data from different sheets was combined correctly
- **Hierarchical Data Considerations**: Note any parent-child relationships, subtotals, or nested categories

"""

        messages = [
            {
                "role": "user",
                "content": prompt_text
            }
        ]

        # Add image if provided
        if table_image:
            # Convert PIL Image to base64
            buffered = io.BytesIO()
            table_image.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode()

            # Modify the message to include image
            messages[0]["content"] = [
                {"type": "text", "text": prompt_text},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{img_str}"
                    }
                }
            ]

        return messages

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