
"""Understanding module for initial analysis and context generation."""

import base64
import io
import re
import time
import random
from typing import Dict, Any, Optional

from openai import RateLimitError

from utils.logger import setup_logger

logger = setup_logger(__name__)


class UnderstandingModule:
    """
    Module responsible for initial analysis and context generation using multimodal capabilities.
    Processes both table data and table images to extract visual context.
    """

    def __init__(self, client, deployment: str, excel_context_understanding: str):
        """ Initialize the UnderstandingModule. """

        self.client = client
        self.deployment = deployment
        self.excel_context_understanding = excel_context_understanding

    def analyze(self, user_question: str) -> str:
        """ Analyze the user question and Excel workbook to generate comprehensive understanding. """

        messages = self._create_multimodal_prompt(user_question, self.excel_context_understanding)
        understanding_output = self._get_llm_response(messages)

        return understanding_output

    def _create_multimodal_prompt(self, user_question: str, excel_context_understanding: str) -> list:
        """Create a prompt for the LLM."""

        prompt_text = f"""You are an expert Excel data analyst. I need you to analyze the spreadsheet content to understand the context for answering a specific question.

**User Question:** {user_question}

**Excel Workbook Content:**
{excel_context_understanding}

**Your Task:**
Analyze the Excel content to provide an analysis in the following format EXACTLY. Do NOT provide the actual answer to the user's question - only provide the analysis framework:

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

        return messages

    def _get_llm_response(self, messages: list, max_retries: int = 5) -> str:
        """Get response from the LLM."""
        last_error = None
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.deployment,
                    messages=messages,
                )
                return response.choices[0].message.content

            except Exception as e:
                last_error = e
            if attempt < max_retries - 1:
                time.sleep(5)
        raise last_error


