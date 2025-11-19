# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Execution module for multi-turn reasoning and code execution."""

import io
import re
import sys
import time
import random
import traceback
from typing import Dict, Any, Optional, Tuple

from openai import RateLimitError

from utils.logger import setup_logger

logger = setup_logger(__name__)


class ExecutionModule:
    """
    Module responsible for multi-turn reasoning and code execution based on understanding context.
    Handles its own conversation flow internally and returns the final result.
    """

    def __init__(self, client, deployment: str, code_globals: dict, code_locals: dict,
                 excel_context_execution: str):
        """
        Initialize the ExecutionModule.

        Args:
            client: OpenAI client instance
            deployment: Model deployment name
            code_globals: Global variables for code execution
            code_locals: Local variables for code execution
            excel_context_execution: Excel context for execution
        """
        self.client = client
        self.deployment = deployment
        self.code_globals = code_globals
        self.code_locals = code_locals
        self.excel_context_execution = excel_context_execution
        self.conversation_history = []

    def _get_system_prompt(self) -> dict:
        """Create the system prompt for the conversation."""

        system_content = """You are an expert Excel data analyst with access to a comprehensive Python environment for Excel analysis.

**CODE EXECUTION ENVIRONMENT:**
You have access to a Python environment with the following pre-loaded:
- openpyxl library for Excel operations
- **Pandas (pd)** for data operations including:
  * DataFrames for structured data manipulation
  * `pd.merge()` for JOIN operations between tables
  * `pd.concat()` for combining similar tables
  * Advanced filtering with boolean conditions
  * GroupBy operations for aggregations
- Helper functions for common Excel operations
- The workbook(s) are already loaded:
  * `workbooks`: Dictionary mapping file paths to workbooks (for multi-file access)
  * `excel_paths`: List of all file paths

Available Excel Helper Functions:

**Basic Sheet Operations:**
- `list_sheets()`: List all sheet names in the workbook
  - **Usage:** `sheets = list_sheets()`
  - **Output:** List of sheet names: `['Sheet1', 'Sheet2', 'Sheet3']`
  - **Important:** Use this first to see what sheets are available!

- `get_sheet(sheet_name=None)`: Get worksheet by name or active sheet
  - **Usage:** `sheet = get_sheet("Sheet1")` or `sheet = get_sheet()` for active sheet
  - **Output:** Returns openpyxl worksheet object for further operations

- `get_sheet_info(sheet_name=None)`: Get information about a sheet
  - **Usage:** `info = get_sheet_info("Sheet1")`
  - **Output:** Dict with name, dimensions: `{'name': 'Sheet1', 'max_row': 100, 'max_column': 5, 'dimensions': '100 rows × 5 columns'}`

- `get_all_sheets_info()`: Get information about all sheets
  - **Usage:** `all_info = get_all_sheets_info()`
  - **Output:** Dict mapping sheet names to their info: `{'Sheet1': {...}, 'Sheet2': {...}}`

**Reading Data:**
- `inspector(range_ref, sheet_name=None)`: Read cell values from specified range
  - **Usage:** `data = inspector("A1:C3", "Sheet1")` or `value = inspector("B5")`
  - **Output:** List of lists format: `[['A1', 'B1', 'C1'], ['A2', 'B2', 'C2']]` or `[['single_value']]`
  - **Multi-sheet:** Always specify `sheet_name` when working with multiple sheets!

- `read_multiple_sheets(sheet_names, range_ref=None)`: Read data from multiple sheets at once
  - **Usage:** `data = read_multiple_sheets(["Sheet1", "Sheet2"], "A1:C10")`
  - **Output:** Dict mapping sheet names to data: `{'Sheet1': [[...]], 'Sheet2': [[...]]}`

- `inspector_attribute(range_ref, attributes, sheet_name=None)`: Extract cell formatting and properties
  - **Usage:** `attrs = inspector_attribute("A1:B2", ["color", "font"], "Sheet1")`
  - **Attributes:** `["color", "font", "formula"]` - specify which properties to extract
  - **Output:** Dict with structure: `{"range": "A1:B2", "sheet": "Sheet1", "attributes": {"color": {"A1": "#FF0000"}, "font": {"B2": "name:Arial; size:12; bold:True"}}}`

- `search(value, sheet_name=None, case_sensitive=False, search_type='partial')`: Find cells containing specific values
  - **Usage:** `matches = search("Total", case_sensitive=True, search_type="whole")`
  - **Search types:** `"partial"` (default), `"whole"`, `"strip"`
  - **Output:** List of dicts: `[{"coordinate": "A5", "value": "Total Sales", "row": 5, "column": 1}]`

- `apply_formatting(sheet_name, range_ref, format_dict)`: Apply cell formatting (colors, fonts, borders)
  - **Usage:** `result = apply_formatting("Sheet1", "A1:C5", {"fill_color": "#FF0000", "bold": True})`
  - **Format Options:**
    - `fill_color`: Background color (hex: '#FF0000' or name: 'red')
    - `font_color`: Font color (hex: '#FF0000' or name: 'red')
    - `font_size`: Font size (int)
    - `font_name`: Font name (str)
    - `bold`: Bold text (bool)
    - `italic`: Italic text (bool)
    - `underline`: Underline text (bool)
    - `border`: Border style ('thin', 'medium', 'thick')
    - `alignment`: Text alignment ('left', 'center', 'right')
  - **Output:** String message confirming formatting applied to specified range

- `save_plot_to_excel(sheet_name, cell_position='A1', figsize=(10,6), dpi=100)`: Save current matplotlib plot to Excel sheet
  - **Usage:** `result = save_plot_to_excel("Charts", "D5", figsize=(8,6))`
  - **Prerequisites:** Create matplotlib plot first with `plt.plot()` or similar
  - **Output:** String message: `"Chart saved to Charts!D5"` or `"No plot to save"`

- `save_workbook()`: Save workbook to file with '_output' postfix
  - **Usage:** `filename = save_workbook()`
  - **Output:** Returns saved filename string: `"/path/to/original_output.xlsx"` and prints confirmation message

**RESPONSE FORMATS - MANDATORY COMPLIANCE:**

SYSTEM CONSTRAINT: Your response must contain EXACTLY one of these formats and NOTHING ELSE:

FORMAT A - Thinking + Code execution:
**Thought:** [Your reasoning and analysis here]

```python
# Your Python code here
```

FORMAT B - Thinking + Final answer:
**Thought:** [Your reasoning and analysis here]

Final Answer: [Your conclusive answer]

CRITICAL REQUIREMENTS:
- ALWAYS start with **Thought:** to explain your reasoning
- Follow with EITHER code execution OR final answer
- NO additional text, explanation, or commentary outside these formats
- NO preamble, postamble, or "how it works" sections
- VIOLATION WILL RESULT IN TASK FAILURE

**CRITICAL DECISION FRAMEWORK - When to use Code vs. Direct Analysis:**

** USE DIRECT ANALYSIS (Give Final Answer immediately) when:**
- The Sheet Content preview shows ALL necessary data for the question
- Simple calculations can be performed mentally from visible data
- The question asks for values that are directly visible in the preview
- Table structure is clear and hierarchical relationships are evident
- No complex aggregations, transformations, or editing operations are needed
- Data relationships (parent-child, subtotals) are obvious from the preview

** USE CODE when:**
- Data extends beyond what's shown in the preview
- Complex calculations, aggregations, or statistical analysis is required
- Data transformation, filtering, or manipulation is needed
- **JOIN/MERGE operations** are needed (combining tables with common keys)
- **Multi-condition filtering** is required (e.g., score >= 60 AND major == '计算机')
- Need to edit/modify the Excel file
- Need to search across large datasets
- Verification of calculations through code is specifically requested

**IMPORTANT GUIDELINES:**
- **NO REDUNDANT CODE**: Don't write code to print data that's already visible in the Sheet Content
- Print intermediate results to show your thought process
- Use the helper functions for common operations
- **Identify hierarchical relationships** (e.g., "of which", "including", indented items)
- Use `save_workbook()` to save changes
- **ALWAYS call `save_workbook()` after making ANY changes to the Excel file**
- **VERIFICATION FOR MULTI-FILE CALCULATIONS**: When working with multiple files, ALWAYS:
  * Print the number of rows read from each file
  * Print the combined total number of rows
  * Verify that data from ALL files is included before calculating the final result
  * Example verification code:
    ```python
    print(f"Class A rows: {len(df_class_a)}")
    print(f"Class B rows: {len(df_class_b)}")
    print(f"Combined rows: {len(combined_data)}")
    print(f"Expected total: {len(df_class_a) + len(df_class_b)}")
    ```

### Multi-File Operations – CRITICAL INSTRUCTIONS
When working with multiple Excel files:

**⚠️ CRITICAL: If the Sheet Content shows multiple files, you MUST read from each file separately!**

**🚨 MANDATORY CHECKLIST for Multi-File Questions:**
1. ✅ Call `list_all_workbooks()` to confirm all files are loaded
2. ✅ Read data from File 1 using `inspector_multi(file1_path, range, sheet_name)`
3. ✅ Read data from File 2 using `inspector_multi(file2_path, range, sheet_name)`
4. ✅ Verify both DataFrames have data (print their lengths)
5. ✅ Combine both DataFrames using `pd.concat()`
6. ✅ Verify combined DataFrame has data from BOTH files (print total length)
7. ✅ Calculate result on COMBINED data, not individual files

**❌ COMMON MISTAKES TO AVOID:**
- DO NOT use `inspector()` for multi-file scenarios (it only reads from first file)
- DO NOT calculate average on only one file's data
- DO NOT skip reading from the second file
- DO NOT assume both files have the same structure without checking

1. **List All Workbooks First**
   - Start by calling `list_all_workbooks()` to see all loaded file paths
   - Use `workbooks` dictionary to access specific workbooks by file path
   - Example: `all_files = list_all_workbooks()` returns `['/path/to/file1.xlsx', '/path/to/file2.xlsx']`
   - **VERIFY**: Print the list to confirm you have all files

2. **Access Data from Specific Files - MANDATORY for Multi-File Scenarios**
   - **DO NOT use `inspector()` for multi-file scenarios** - it only reads from the first workbook in workbooks!
   - **MUST use `inspector_multi(file_path, range_ref, sheet_name)` to read from each file separately**
   - Use `get_workbook(file_path)` to get a specific workbook
   - Use `get_sheet_from_workbook(file_path, sheet_name)` to get a sheet from a specific file
   - Example for two files:
     ```python
     # Get file paths
     all_files = list_all_workbooks()
     file1_path = all_files[0]  # or excel_paths[0]
     file2_path = all_files[1]  # or excel_paths[1]
     
     # Read from each file separately
     file1_data = inspector_multi(file1_path, "A1:D20", "Sheet1")
     file2_data = inspector_multi(file2_path, "A1:D20", "Sheet1")
     
     # Then combine the data
     df1 = pd.DataFrame(file1_data[1:], columns=file1_data[0])
     df2 = pd.DataFrame(file2_data[1:], columns=file2_data[0])
     combined = pd.concat([df1, df2])
     ```

3. **Cross-File Calculations - MANDATORY STEPS**
   - When the question involves multiple files (e.g., "average across two classes in different files"), you MUST:
     a. **FIRST**: Call `list_all_workbooks()` to get all file paths
     b. **SECOND**: Read data from EACH file separately using `inspector_multi(file_path, range_ref, sheet_name)`
     c. **THIRD**: Combine the data appropriately (using pandas if needed)
     d. **FOURTH**: Perform calculations on the combined dataset
   - **CRITICAL**: Never use `inspector()` alone for multi-file scenarios - it will only read from the first file!
   - Example for "average across two classes in different files":
     ```python
     # Step 1: Get all file paths
     all_files = list_all_workbooks()
     file1_path = all_files[0]  # First file (e.g., example_table.xlsx)
     file2_path = all_files[1]  # Second file (e.g., example2.xlsx)
     
     # Step 2: Read from each file using inspector_multi (NOT inspector!)
     # IMPORTANT: Include header row in range (e.g., A2:C7 includes row 2 as header)
     # Check the Sheet Content preview to determine correct ranges
     class1_data = inspector_multi(file1_path, "A2:C7", "PELAGIC")  # Read including header row
     class2_data = inspector_multi(file2_path, "A2:C7", "Sheet1")   # Read including header row
     
     # Step 3: Convert to DataFrames
     # First row of data is usually the header, rest are data rows
     df1 = pd.DataFrame(class1_data[1:], columns=class1_data[0])  # Skip first row if it's header
     df2 = pd.DataFrame(class2_data[1:], columns=class2_data[0])  # Skip first row if it's header
     
     # Step 4: Combine the dataframes
     combined = pd.concat([df1, df2], ignore_index=True)
     
     # Step 5: Calculate average on combined data
     combined['GRP Grades'] = pd.to_numeric(combined['GRP Grades'], errors='coerce')
     combined = combined.dropna(subset=['GRP Grades'])  # Remove any NaN values
     
     # CRITICAL: Verify data from both files is included
     print(f"Class A students: {len(df1)}")
     print(f"Class B students: {len(df2)}")
     print(f"Total students in combined data: {len(combined)}")
     if len(combined) != len(df1) + len(df2):
         print(f"WARNING: Expected {len(df1) + len(df2)} students, but got {len(combined)}")
     
     average = combined['GRP Grades'].mean()
     print(f"Overall average: {average}")
     print(f"Class A average: {df1['GRP Grades'].mean():.2f}")
     print(f"Class B average: {df2['GRP Grades'].mean():.2f}")
     ```

4. **File Relationships and JOIN Operations**
   - Identify if files contain related data (e.g., different classes, different time periods, different departments)
   - **For JOIN/MERGE operations**: When tables have a common key (e.g., student ID, employee ID), use `pd.merge()` to join them
   - **JOIN Types**: Use `how='inner'` (default) for matching records only, `how='left'` to keep all from left table, `how='outer'` for all records
   - **Example for JOIN with filtering**:
     ```python
     # Read two tables with common key
     table1_data = inspector_multi(file1_path, "A1:C10", "Sheet1")  # ID, Name, Score
     table2_data = inspector_multi(file2_path, "A1:B10", "Sheet1")  # ID, Major
     
     # Convert to DataFrames
     df1 = pd.DataFrame(table1_data[1:], columns=table1_data[0])
     df2 = pd.DataFrame(table2_data[1:], columns=table2_data[0])
     
     # JOIN on common key (e.g., student ID)
     merged = pd.merge(df1, df2, on='学生ID', how='inner')
     
     # Apply filters (e.g., score >= 60 AND major == '计算机')
     result = merged[(merged['均分'] >= 60) & (merged['专业'] == '计算机')]
     
     print(f"符合条件的学生数: {len(result)}")
     print(result)
     ```
   - Pay attention to file names in the Sheet Content preview to identify which file contains which data

### Multi-Sheet Operations – CRITICAL INSTRUCTIONS
When working with multiple sheets in a workbook:

1. **Always List Sheets First**
   - Start by calling `list_sheets()` to see all available sheets in the first workbook (from workbooks dictionary)
   - Use `get_all_sheets_info()` to understand the structure of all sheets
   - For multi-file scenarios, check each workbook separately using `get_workbook(file_path)`

2. **Explicitly Specify Sheet Names**
   - ALWAYS provide `sheet_name` parameter when calling `inspector()`, `get_sheet()`, etc.
   - Example: `data1 = inspector("A1:C10", "Sheet1")` and `data2 = inspector("A1:C10", "Sheet2")`
   - Never rely on default/active sheet when multiple sheets exist

3. **Cross-Sheet Calculations (within same file)**
   - When the question involves multiple sheets in the same workbook:
     a. Read data from each relevant sheet separately
     b. Combine the data appropriately (using pandas if needed)
     c. Perform calculations on the combined dataset
   - Example for "average across two sheets in same file":
     ```python
     # Get data from both sheets
     class1_data = inspector("A1:D20", "Class1")
     class2_data = inspector("A1:D20", "Class2")
     # Convert to DataFrames and combine
     df1 = pd.DataFrame(class1_data[1:], columns=class1_data[0])
     df2 = pd.DataFrame(class2_data[1:], columns=class2_data[0])
     combined = pd.concat([df1, df2])
     # Calculate average
     average = combined['GRP'].mean()
     ```

4. **Sheet Relationships**
   - Identify if sheets contain related data (e.g., different classes, different time periods)
   - Understand how to combine them (concatenate, merge, or calculate separately then aggregate)

### Multi-Table in One Sheet – Instructions
1. **Detect Multiple Tables**
   Recognize that a single sheet may contain several distinct tables separated by blank rows/columns or different header areas.
2. **Identify Boundaries**
   Clearly define the start and end range of each table to avoid mixing data.
3. **Check Relationships**
   Analyze whether tables are logically connected (e.g., raw data vs. summary, detail vs. KPIs).
4. **Follow Query Focus**
   If the query mentions multiple tables, address each one explicitly and compare where relevant.

### Complex Table – Instructions
1. **Identify Hierarchies**
   Detect multi-row column headers (top headers) and multi-level row headers (left headers) as hierarchical structures.
2. **Preserve Header Levels**
   Keep parent–child relationships intact when analyzing (e.g., Region → Product → Sales).
3. **Handle Subtotals**
   Recognize subtotal and total rows/columns, and clarify "of which" or aggregation relationships.
4. **Explain Hierarchy in Results**
   Clearly state how each level contributes to subtotals/totals in your explanation.

Start by exploring the data structure to understand what you're working with."""

        return {"role": "system", "content": system_content}

    def _create_initial_user_prompt(self, understanding_output: str, user_question: str) -> dict:
        """Create the initial user prompt for the conversation."""

        user_content = f"""**Sheet Content:**
{self.excel_context_execution}

**Understanding Context:**
{understanding_output}

**USER QUESTION:**
{user_question}

Please start by exploring the data structure and then work toward answering the question step by step.
"""

        return {"role": "user", "content": user_content}

    def run(self, understanding_output: str, user_question: str, max_turns: int = 20) -> Dict[str, Any]:
        """
        Run the execution module with understanding context and user question.

        Args:
            understanding_output: Output from UnderstandingModule
            user_question: Original user question
            max_turns: Maximum number of conversation turns

        Returns:
            Dictionary containing execution results and conversation history
        """
        logger.info(f"Starting multi-turn analysis for: '{user_question}'")

        # Initialize conversation with system prompt and initial user prompt
        self.conversation_history = [self._get_system_prompt()]
        initial_prompt = self._create_initial_user_prompt(understanding_output, user_question)
        self.conversation_history.append(initial_prompt)

        execution_steps = []  # Track key execution steps

        for turn in range(max_turns):
            logger.info(f"Execution turn {turn + 1}")

            try:
                response_message = self._get_llm_response()
                self.conversation_history.append(response_message)

                # Parse response for code action or final answer
                thought, code_action = self._parse_llm_response(response_message.content)

                if code_action is None:
                    # No code to execute, check if it's a final answer
                    if thought and "Final Answer:" in thought:
                        # Extract the final answer from the content
                        final_answer_match = re.search(r"Final Answer:\s*(.*?)$", thought, re.DOTALL)
                        if final_answer_match:
                            final_answer = final_answer_match.group(1).strip()
                        else:
                            final_answer = thought.replace("Final Answer:", "").strip()

                        logger.info(f"Final answer found: {final_answer}")

                        return {
                            "success": True,
                            "answer": final_answer,
                            "total_turns": turn + 1,
                            "conversation_history": self._format_conversation_history(),
                            "execution_summary": self._generate_execution_summary(execution_steps, final_answer)
                        }
                    else:
                        # No valid action found, ask for clarification
                        logger.warning("No valid action found, asking for clarification")
                        reminder = (
                            "CRITICAL FORMAT VIOLATION: You must respond in EXACTLY one of these formats:\n\n"
                            "FORMAT A - Thinking + Code:\n"
                            "**Thought:** [Your reasoning here]\n\n"
                            "```python\n# Your code here\n```\n\n"
                            "FORMAT B - Thinking + Final Answer:\n"
                            "**Thought:** [Your reasoning here]\n\n"
                            "Final Answer: Your answer here\n\n"
                            "NO other text is allowed. Start with **Thought:** ALWAYS."
                        )
                        self.conversation_history.append({"role": "user", "content": reminder})
                        continue

                # Execute code action
                logger.info(f"Executing Python code:\n{code_action}")

                try:
                    execution_result = self._execute_code(code_action)
                    observation = f"Code execution result:\n{execution_result}"
                    logger.info(f"Execution result:\n{execution_result}")

                    # Track this execution step
                    execution_steps.append({
                        "turn": turn + 1,
                        "code": code_action,
                        "result": execution_result,
                        "success": True
                    })

                    self.conversation_history.append({"role": "user", "content": observation})

                except Exception as e:
                    error_message = f"Code execution error: {str(e)}"
                    logger.error(f"Execution error: {error_message}")

                    # Track this failed execution step
                    execution_steps.append({
                        "turn": turn + 1,
                        "code": code_action,
                        "result": error_message,
                        "success": False
                    })

                    self.conversation_history.append({"role": "user", "content": error_message})

            except Exception as e:
                logger.error(f"LLM Error: {str(e)}")
                return {
                    "success": False,
                    "answer": f"LLM communication error: {str(e)}",
                    "total_turns": turn + 1,
                    "conversation_history": self._format_conversation_history(),
                    "execution_summary": self._generate_execution_summary(execution_steps, None)
                }

        # Reached maximum turns without final answer
        logger.warning("Reached maximum turns without finding final answer")
        return {
            "success": False,
            "answer": "Unable to find a complete answer within the maximum number of turns.",
            "total_turns": max_turns,
            "conversation_history": self._format_conversation_history(),
            "execution_summary": self._generate_execution_summary(execution_steps, None)
        }

    def _execute_code(self, code: str) -> str:
        """Execute Python code in the Excel environment."""
        old_stdout = sys.stdout
        old_stderr = sys.stderr

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        result = ""

        try:
            sys.stdout = stdout_capture
            sys.stderr = stderr_capture

            # Merge locals into globals for better variable access in nested scopes
            combined_namespace = {**self.code_globals, **self.code_locals}

            # Execute the code with combined namespace
            exec(code, combined_namespace)

            # Update both globals and locals with any new variables
            self.code_globals.update({k: v for k, v in combined_namespace.items()
                                    if k not in self.code_globals or k in self.code_locals})
            self.code_locals.update(combined_namespace)

            stdout_output = stdout_capture.getvalue()
            stderr_output = stderr_capture.getvalue()

            if stdout_output:
                result += f"Output:\n{stdout_output}\n"

            if stderr_output:
                result += f"Errors/Warnings:\n{stderr_output}\n"

            # Check for result variable
            if 'result' in combined_namespace:
                result += f"Result variable: {combined_namespace['result']}\n"

            # Try to evaluate last expression if no output
            if not result.strip():
                lines = code.strip().split('\n')
                if lines:
                    last_line = lines[-1].strip()
                    if last_line and not any(last_line.startswith(kw) for kw in
                                           ['import ', 'from ', 'def ', 'class ', 'if ', 'for ', 'while ', 'try ', 'with ', 'print(']):
                        try:
                            last_result = eval(last_line, combined_namespace)
                            if last_result is not None:
                                result = f"Expression result: {last_result}"
                        except:
                            pass

            if not result.strip():
                result = "Code executed successfully (no output)"

        except Exception as e:
            result = f"Execution error: {str(e)}\nTraceback:\n{traceback.format_exc()}"

        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

        if len(result) <= 10000:
            return result
        else:
            return result[:10000] + "\n⚠️ **[OUTPUT TRUNCATED]** ⚠️\n"

    def _get_llm_response(self, max_retries: int = 5, base_delay: float = 1.0):
        """Get response from OpenAI with retry logic."""
        last_exception = None

        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.deployment,
                    messages=self.conversation_history,
                )

                # Extract message
                choice = response.choices[0]
                message = choice.message

                print("="*50)
                print("EXECUTION MODULE LLM RESPONSE:")
                print("="*50)
                print(message.content)
                print("="*50)
                return message

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
                        logger.info(f"Waiting {delay:.1f} seconds (exponential backoff)")

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

    def _parse_llm_response(self, content: str) -> Tuple[Optional[str], Optional[str]]:
        """Parse LLM response for Final Answer or Code Action"""

        # Check for Final Answer (with or without Thought prefix)
        if "Final Answer:" in content:
            return content.strip(), None

        # Check for Code Action
        code_match = re.search(r"```python\s*(.*?)\s*```", content, re.DOTALL)
        if code_match:
            code = code_match.group(1).strip()
            return None, code

        # No valid format found
        return content.strip(), None

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

    def _format_conversation_history(self) -> list:
        """Format conversation history for output."""
        formatted_history = []
        for msg in self.conversation_history:
            if hasattr(msg, 'dict'):
                formatted_history.append(msg.dict())
            elif isinstance(msg, dict):
                formatted_history.append(msg)
            else:
                # Convert other message types to dict format
                formatted_history.append({
                    "role": getattr(msg, 'role', 'unknown'),
                    "content": getattr(msg, 'content', str(msg))
                })
        return formatted_history

    def _generate_execution_summary(self, execution_steps: list, final_answer: Optional[str]) -> dict:
        """Generate a summary of the execution process."""
        successful_steps = [step for step in execution_steps if step["success"]]
        failed_steps = [step for step in execution_steps if not step["success"]]

        summary = {
            "total_code_executions": len(execution_steps),
            "successful_executions": len(successful_steps),
            "failed_executions": len(failed_steps),
            "execution_steps": execution_steps,
            "has_final_answer": final_answer is not None,
            "final_answer": final_answer
        }

        if execution_steps:
            summary["first_execution_turn"] = execution_steps[0]["turn"]
            summary["last_execution_turn"] = execution_steps[-1]["turn"]

        return summary