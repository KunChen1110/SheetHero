import os
import time
import csv
from typing import Dict, Any, Optional, Union, List
from openai import OpenAI
from openpyxl import load_workbook, Workbook
from openpyxl.utils import get_column_letter

from backend.config.settings import Config
from backend.modules.understanding import UnderstandingModule
from backend.modules.execution import ExecutionModule
from backend.modules.validation import ValidationModule
from backend.utils.excel_toolkit import ExcelToolkit, calculate_token_cost_line
from backend.utils.logger import setup_logger

logger = setup_logger(__name__)


def build_output_preferences(mode: str = "text",
                             file_path: Optional[str] = None) -> Dict[str, Optional[str]]:
    """
    Normalize user preferences for how results should be delivered.

    Args:
        mode: "text" for inline markdown answers, "file" to save results.
        file_path: Optional explicit path for file output.

    Returns:
        Dict with validated mode and file_path.
    """
    normalized_mode = (mode or "text").strip().lower()
    if normalized_mode not in {"text", "file"}:
        raise ValueError("output mode must be 'text' or 'file'")

    if normalized_mode == "file":
        normalized_path = file_path or os.path.join(
            os.getcwd(), "sheetbrain_output.xlsx"
        )
    else:
        normalized_path = None

    return {"mode": normalized_mode, "file_path": os.path.abspath(normalized_path) if normalized_path else None}


def output_mode(mode: str = "text", file_path: Optional[str] = None) -> Dict[str, Optional[str]]:
    return build_output_preferences(mode, file_path)


"""                                                                                                                                                                                                 
config (Config)
output_preferences (dict)
output_instruction (str)

excel_paths (list)

excel_conntext_understanding (str)
excel_conntext_execution (str)

self.client (OpenAI)
code_globals (dict)
code_locals (dict)
workbooks

understanding_module
execution_module
validation_module
"""
class SheetBrain:
    def __init__(self, excel_paths: Union[str, List[str]],
                 config: Config,
                 load_excel: bool = True):
        # === Load Config ===
        self.config = config
        self.output_preferences = build_output_preferences(
            mode=self.config.output_mode,
            file_path=self.config.output_file
        )
        self.output_instruction = self._build_output_instruction()
        self.excel_paths = excel_paths if isinstance(excel_paths, list) else [excel_paths]

        # === OpenAI Client Setup ===
        if not self.config.api_key:
            raise ValueError("OpenAI API key is missing in Config")
        client_kwargs = {"api_key": self.config.api_key}
        if self.config.base_url:
            client_kwargs["base_url"] = self.config.base_url
        self.client = OpenAI(**client_kwargs)

        # === Code Execution Environment Setup ===
        self.code_globals = {
            'math': __import__('math'),      # Mathematical functions (sin, cos, sqrt, etc.)
            'json': __import__('json'),      # JSON parsing/formatting
            're': __import__('re'),          # Regular expressions for text processing
            'os': __import__('os'),          # Operating system interface
            'sys': __import__('sys'),        # System-specific parameters
            'excel_paths': self.excel_paths, # List of all file paths
            'output_preferences': self.output_preferences,  # Output requirements
        }
        self.code_locals = {}  # Empty dict for code execution (stores variables created by AI code)

        # === Excel File Loading and Context Generation ===
        if load_excel:
            # Load the Excel file(s) and libraries (openpyxl, pandas, etc.)
            self._setup_excel_libraries()
            self.workbooks = self.code_globals.get('workbooks', {})

            # Generate markdown summary of Excel contents for AI context
            self.excel_context_understanding = self._generate_sheets_markdown_summary(self.config.total_token_budget * 2)
            self.excel_context_execution = self._generate_sheets_markdown_summary(self.config.total_token_budget)
        else:
            # Headless mode: don't load Excel, work with provided context only
            self.workbooks = {}
            self.excel_context_understanding = "Excel file not loaded. Working with provided context only."
            self.excel_context_execution = "Excel file not loaded. Working with provided context only."

        # === Module Initialization ===
        self.understanding_module = UnderstandingModule(
            self.client,
            self.config.deployment,
            self.excel_context_understanding
        )
        self.execution_module = ExecutionModule(
            self.client,
            self.config.deployment,
            self.code_globals,
            self.code_locals,
            self.excel_context_execution,
            self.output_instruction
        )
        self.validation_module = ValidationModule(
            self.client,
            self.config.deployment,
            self.excel_context_understanding
        )

    def run(self, user_question: str) -> Dict[str, Any]:
        # Use config defaults if parameters not provided (allows CLI overrides)
        max_turns = self.config.max_turns

        # Log and print that we're starting analysis
        logger.info("Starting iterative three-stage analysis")
        print("🚀 [SheetBrain] Starting iterative three-stage analysis...")
        print("="*80)

        # === Timing and Tracking Variables ===
        overall_start_time = time.time()
        all_execution_results = []    # Store results from each execution stage
        all_validation_results = []   # Store results from each validation stage

        try:
            # ===== STAGE 1: UNDERSTANDING (Optional but Recommended) =====
            logger.info("Running understanding module")
            print("📖 [STAGE 1] UNDERSTANDING MODULE")
            print("-" * 40)

            understanding_start_time = time.time()
            # Call the UnderstandingModule to analyze the question + Excel context
            understanding_output = self.understanding_module.analyze(user_question)
            understanding_duration = time.time() - understanding_start_time

            print(f"✅ [STAGE 1] Understanding completed in {understanding_duration:.2f}s")
            print(f"📝 [STAGE 1] Analysis preview: {understanding_output}...")

            # ===== ITERATIVE EXECUTE-VALIDATE LOOP =====
            for iteration in range(max_turns):
                logger.info(f"Starting iteration {iteration + 1}/{max_turns}")
                print(f"\n🔄 [ITERATION {iteration + 1}/{max_turns}] EXECUTE-VALIDATE CYCLE")
                print("="*60)

                # ===== STAGE 2: EXECUTION =====
                print(f"💻 [ITERATION {iteration + 1}] EXECUTION MODULE")
                print("-" * 40)
                execution_start_time = time.time()

                # If this isn't the first iteration, add validation feedback from previous attempt
                if iteration > 0 and all_validation_results:
                    last_validation = all_validation_results[-1]
                    if last_validation.get('improvement_feedback'):
                        # Build enhanced prompt with previous feedback
                        enhanced_understanding = f"""{understanding_output}

**IMPROVEMENT FEEDBACK FROM PREVIOUS ITERATION:**
{last_validation['improvement_feedback']}

**ISSUES TO ADDRESS:**
{'; '.join(last_validation.get('issues_found', []))}

Please address these specific points in your new analysis approach."""
                    else:
                        enhanced_understanding = understanding_output
                else:
                    enhanced_understanding = understanding_output

                # Run the ExecutionModule to generate and execute analysis code
                execution_result = self.execution_module.run(enhanced_understanding, user_question)
                execution_duration = time.time() - execution_start_time
                all_execution_results.append(execution_result)

                # Print execution metrics
                status_emoji = "✅" if execution_result["success"] else "❌"
                print(f"{status_emoji} [ITERATION {iteration + 1}] Execution completed in {execution_duration:.2f}s")
                print(f"🔄 [ITERATION {iteration + 1}] Total turns: {execution_result['total_turns']}")
                print(f"📊 [ITERATION {iteration + 1}] Code executions: {execution_result.get('execution_summary', {}).get('total_code_executions', 0)}")

                # ===== STAGE 3: VALIDATION (if enabled) =====
                logger.info(f"Running validation module for iteration {iteration + 1}")
                print(f"\n🔍 [ITERATION {iteration + 1}] VALIDATION MODULE")
                print("-" * 40)
                validation_start_time = time.time()

                # Run the ValidationModule to check if the answer is correct
                validation_result = self.validation_module.reflect(execution_result, user_question, understanding_output)
                validation_duration = time.time() - validation_start_time
                all_validation_results.append(validation_result)

                # Print validation results
                validation_emoji = "✅" if validation_result["validation_passed"] else "⚠️"
                print(f"{validation_emoji} [ITERATION {iteration + 1}] Validation completed in {validation_duration:.2f}s")
                print(f"🎯 [ITERATION {iteration + 1}] Confidence: {validation_result['confidence_score']:.2f}")
                print(f"📋 [ITERATION {iteration + 1}] Validation: {'PASSED' if validation_result['validation_passed'] else 'FAILED'}")

                # === Loop Termination Logic ===
                # Decide whether to stop iterating or try again
                if validation_result['validation_passed']:
                    # Success! Answer is good enough
                    logger.info(f"Validation passed on iteration {iteration + 1}")
                    print(f"🎉 [SUCCESS] Validation passed on iteration {iteration + 1}!")
                    final_answer = validation_result.get('verified_answer', execution_result['answer'])
                    overall_success = True
                    confidence_score = validation_result['confidence_score']
                    validation_passed = True
                    break  # Exit the loop

                elif not validation_result.get('requires_reexecution', True):
                    # Validation says no point in trying again
                    logger.warning("Validation indicates no further improvement possible")
                    print(f"🛑 [STOPPING] Validation indicates no further improvement possible")
                    final_answer = execution_result['answer']
                    overall_success = False
                    confidence_score = validation_result['confidence_score']
                    validation_passed = False
                    break  # Exit the loop

                else:
                    # Validation found issues - prepare for next iteration
                    logger.info(f"Issues found, preparing for iteration {iteration + 2}")
                    print(f"🔄 [CONTINUE] Issues found, preparing for iteration {iteration + 2}")

                    # Check if we're out of iterations
                    if iteration == max_turns - 1:
                        logger.warning("Reached maximum iterations without validation")
                        print(f"⚠️ [MAX ITERATIONS] Reached maximum iterations without validation")
                        final_answer = execution_result['answer']
                        overall_success = False
                        confidence_score = validation_result['confidence_score']
                        validation_passed = False

            # === Final Report Generation ===
            # Collect issues and feedback from the last validation (if any)
            if all_validation_results:
                final_validation = all_validation_results[-1]
                issues_found = final_validation.get('issues_found', [])
                improvement_feedback = final_validation.get('improvement_feedback', '')
            else:
                issues_found = []
                improvement_feedback = ''

            # Collect conversation histories for debugging
            all_conversation_histories = []
            for exec_result in all_execution_results:
                conv_history = exec_result.get('conversation_history', [])
                if conv_history:
                    all_conversation_histories.append({
                        'iteration': all_execution_results.index(exec_result) + 1,
                        'conversation_history': conv_history
                    })

            # ===== FINAL SUMMARY =====
            total_duration = time.time() - overall_start_time
            total_iterations = len(all_execution_results)

            logger.info(f"Analysis completed. Success: {overall_success}, Iterations: {total_iterations}")
            print("\n" + "="*80)
            print("🎯 [FINAL SUMMARY]")
            print("="*80)
            print(f"Overall Success: {'✅ YES' if overall_success else '❌ NO'}")
            print(f"Total Iterations: {total_iterations}")
            print(f"Final Answer: {final_answer}")
            print(f"Confidence Score: {confidence_score:.2f}/1.0")
            print(f"Validation Passed: {'✅ YES' if validation_passed else '❌ NO'}")
            print(f"Total Duration: {total_duration:.2f}s")
            print("="*80)

            # Return comprehensive results dictionary
            return {
                "success": overall_success,
                "answer": final_answer,
                "confidence_score": confidence_score,
                "validation_passed": validation_passed,
                "total_iterations": total_iterations,
                "all_execution_results": all_execution_results,      # Full history
                "all_validation_results": all_validation_results,    # Full history
                "conversation_history": all_conversation_histories,  # For debugging
                "issues_found": issues_found,
                "improvement_feedback": improvement_feedback,
                "total_duration": total_duration,
                "user_question": user_question,
                "understanding_output": understanding_output
            }

        except Exception as e:
            # === Error Handling ===
            # If anything goes wrong, log it and return error info
            error_duration = time.time() - overall_start_time
            logger.error(f"Critical error: {str(e)}")
            print(f"❌ [SheetBrain] Critical error: {str(e)}")
            print(f"⏱️ [SheetBrain] Failed after {error_duration:.2f}s")

            # Collect what conversation history we have
            all_conversation_histories = []
            for exec_result in all_execution_results:
                conv_history = exec_result.get('conversation_history', [])
                if conv_history:
                    all_conversation_histories.append({
                        'iteration': all_execution_results.index(exec_result) + 1,
                        'conversation_history': conv_history
                    })

            # Return error results (success=False, answer=error message)
            return {
                "success": False,
                "answer": f"Analysis failed due to error: {str(e)}",
                "confidence_score": 0.0,
                "validation_passed": False,
                "total_iterations": len(all_execution_results),
                "all_execution_results": all_execution_results,
                "all_validation_results": all_validation_results,
                "conversation_history": all_conversation_histories,
                "issues_found": [f"Critical error: {str(e)}"],
                "improvement_feedback": "Review the error and try again",
                "total_duration": error_duration,
                "user_question": user_question
            }

    def _generate_sheets_markdown_summary(self, total_token_budget: int = 50000) -> str:
        """
         * Generate a markdown summary of all sheets in the Excel workbook(s).
         *
         * This method creates a readable text description of the Excel file(s) that
         * can be sent to the AI. It includes:
         * - File names and sheet counts
         * - Sheet names and dimensions (rows × columns)
         * - Data previews in markdown table format
         * - Cell references (A1 notation) for clarity
         * - Token budget management (truncates if too large)
         *
         * Token Budgeting Strategy:
         * =========================
         * - Divide total budget equally among all files
         * - For each file, divide its budget equally among all sheets
         * - For each sheet, show as many rows as fit in the sheet's budget
         * - Always show at least 5 rows minimum per sheet
         * - Mark clearly when data is truncated
         *
         * This prevents:
         * - Exceeding AI model's context length limits
         * - Wasting money on unnecessary tokens
         * - Overwhelming the AI with too much data
         *
         * @param total_token_budget: Maximum tokens for the entire summary (default: 50K)
         * @return: Markdown string describing the Excel file(s)
        """
        try:
            # Get all workbooks from code_globals (set up in _setup_excel_libraries)
            if hasattr(self, 'code_globals') and 'workbooks' in self.code_globals:
                workbooks = self.code_globals['workbooks']
            else:
                # Fallback: use self.workbooks if available
                workbooks = self.workbooks if hasattr(self, 'workbooks') else {}
            
            overview_parts = []
            
            # Overall header
            if len(workbooks) > 1:
                overview_parts.append(f"📊 **Multiple Excel Files Overview ({len(workbooks)} files)**\n")
            else:
                first_path = self.excel_paths[0] if self.excel_paths else "unknown"
                overview_parts.append(f"📊 **Excel File Overview: {os.path.basename(first_path)}**\n")
            
            # Calculate token budget per file
            available_tokens = total_token_budget
            tokens_per_file = available_tokens // len(workbooks) if workbooks else 0
            
            # Process each workbook
            for excel_path, workbook in workbooks.items():
                file_parts = []
                
                # File header
                file_parts.append(f"\n{'='*60}")
                file_parts.append(f"📁 **File: {os.path.basename(excel_path)}**")
                file_parts.append(f"**Full Path:** {excel_path}")
                file_parts.append(f"**Total Sheets:** {len(workbook.sheetnames)}\n")
                
                # Calculate token budget per sheet for this file
                tokens_per_sheet = tokens_per_file // len(workbook.sheetnames) if workbook.sheetnames else 0
                
                # Process each sheet in this workbook
                for sheet_name in workbook.sheetnames:
                    sheet = workbook[sheet_name]
                    sheet_parts = []
                    
                    # Sheet header
                    sheet_parts.append(f"\n**📄 Sheet: '{sheet_name}'** (in {os.path.basename(excel_path)})")
                    sheet_parts.append(f"- Dimensions: {sheet.max_row} rows × {sheet.max_column} columns")
                    
                    if tokens_per_sheet > 0:
                        # Generate data preview within token budget
                        preview_result = self._get_sheet_preview_with_token_limit(
                            sheet,
                            tokens_per_sheet,
                            max_rows=min(sheet.max_row, 10000),  # Safety cap for performance
                            max_cols=min(sheet.max_column, 1000)   # Safety cap for performance
                        )
                        
                        sheet_parts.append(f"- Data Preview ({preview_result['rows_shown']} of {sheet.max_row} rows, "
                                           f"{preview_result['cols_shown']} of {sheet.max_column} columns):")
                        
                        # Warn if data was truncated
                        if preview_result['is_truncated']:
                            sheet_parts.append("  ⚠️ Preview truncated to fit token budget")
                        
                        # Add actual data in markdown table format
                        sheet_parts.append("  Data:")
                        markdown_rows = []
                        for row_data in preview_result['formatted_data']:
                            # Join cells with "|" and add borders for markdown table format
                            markdown_rows.append(f"| {' | '.join(row_data)} |")
                        
                        # Join all rows with newlines (using \n for compactness)
                        if markdown_rows:
                            sheet_parts.append("  " + "\\n".join(markdown_rows))
                        
                        # Add summary stats if not all rows shown
                        if preview_result['rows_shown'] < sheet.max_row:
                            sheet_parts.append(f"\n  📊 Sheet Summary:")
                            sheet_parts.append(f"  - Total rows: {sheet.max_row}")
                            sheet_parts.append(f"  - Total columns: {sheet.max_column}")
                            sheet_parts.append(f"  - Rows shown in preview: {preview_result['rows_shown']}")
                    
                    file_parts.extend(sheet_parts)
                
                overview_parts.extend(file_parts)
            
            # Join all parts into single string
            final_overview = "\n".join(overview_parts)
            return final_overview

        except Exception as e:
            # If context generation fails, return error but don't crash whole analysis
            logger.error(f"Error generating Excel overview: {str(e)}")
            return f"❌ Error generating Excel overview: {str(e)}"

    def _build_output_instruction(self) -> str:
        """
        Create natural-language guidance for the execution module about output expectations.
        """
        mode = self.output_preferences.get("mode", "text")
        if mode == "file":
            target_path = self.output_preferences.get("file_path")
            return (
                "Final results must be saved to a spreadsheet file. "
                f"Write the consolidated output to '{target_path}' (e.g., via pandas.to_excel "
                "or save_workbook). After saving, mention the file path in the final answer."
            )

        return (
            "Final results must be presented directly in the final answer as a clean markdown "
            "table or list. Do not save any files unless the user explicitly asks."
        )

    def _load_workbook_from_path(self, excel_path: str):
        """
        Load a spreadsheet file (Excel or CSV) and return an openpyxl Workbook.

        Args:
            excel_path: Path to the spreadsheet file.

        Returns:
            openpyxl Workbook instance.
        """
        _, ext = os.path.splitext(excel_path)
        ext = ext.lower()
        excel_extensions = {".xlsx", ".xlsm", ".xltx", ".xltm"}

        if ext in excel_extensions:
            return load_workbook(excel_path, data_only=True)
        if ext == ".csv":
            return self._create_workbook_from_csv(excel_path)

        raise ValueError(
            f"Unsupported file extension '{ext}' for {excel_path}. "
            "Supported formats: .xlsx, .xlsm, .xltx, .xltm, .csv"
        )

    def _create_workbook_from_csv(self, csv_path: str) -> Workbook:
        """
        Convert a CSV file into an openpyxl Workbook for unified processing.

        Args:
            csv_path: Path to the CSV file.

        Returns:
            Workbook populated with CSV content in a single sheet.
        """
        workbook = Workbook()
        sheet = workbook.active

        # Sheet titles in Excel are limited to 31 characters
        sheet_name = os.path.splitext(os.path.basename(csv_path))[0][:31] or "Sheet1"
        sheet.title = sheet_name

        with open(csv_path, newline="", encoding="utf-8-sig") as csv_file:
            reader = csv.reader(csv_file)
            for row in reader:
                processed_row = [self._infer_cell_value(value) for value in row]
                sheet.append(processed_row)

        return workbook

    @staticmethod
    def _infer_cell_value(value: str):
        """
        Try to convert a CSV string value to int/float when possible.
        Keeps original string if conversion fails.
        """
        if value is None:
            return value

        stripped = value.strip()
        if stripped == "":
            return ""

        try:
            if '.' not in stripped:
                return int(stripped)
            return float(stripped)
        except ValueError:
            return value

    def _get_sheet_preview_with_token_limit(self, sheet, token_budget: int,
                                            max_rows: int = 10000, max_cols: int = 1000) -> Dict[str, Any]:
        """
         * Generate a data preview that fits within a token budget.
         *
         * This method iterates through rows of an Excel sheet, building a preview
         * until it runs out of token budget. It's careful to:
         * - Count tokens accurately (using calculate_token_cost_line)
         * - Always include at least 5 rows (even if over budget)
         * - Escape special characters that break markdown formatting
         * - Track exactly how much data was shown vs. available
         *
         * Token Estimation:
         * =================
         * Each row is converted to a string like "A1:value | B1:value | C1:value"
         * We count tokens in this string and stop when budget is exceeded.
         * This is approximate but good enough for budget management.
         *
         * Data Format:
         * ============
         * Returns a dictionary with:
         * - data: Raw cell values (2D list)
         * - formatted_data: Cell values with A1 references (2D list)
         * - rows_shown: Number of rows included
         * - cols_shown: Number of columns included
         * - is_truncated: Boolean - was data cut off?
         * - tokens_used: Actual tokens consumed
         *
         * @param sheet: The openpyxl sheet object to preview
         * @param token_budget: Maximum tokens allowed for this preview
         * @param max_rows: Safety limit on rows (default: 10,000)
         * @param max_cols: Safety limit on columns (default: 1,000)
         * @return: Dictionary with preview data and metadata
        """
        preview_data = []          # Raw cell values (for modules to use)
        formatted_data = []        # Formatted strings with cell references (for AI context)
        tokens_used = 0
        rows_shown = 0

        start_row = 1  # Start from first row (adjust if you want to skip headers)

        # Calculate actual limits (respect sheet boundaries and safety caps)
        max_data_rows = min(max_rows, sheet.max_row)
        max_data_cols = min(max_cols, sheet.max_column)

        # Iterate through rows until we hit token budget or row limit
        for row_idx in range(start_row, max_data_rows + 1):
            row_cells = []           # Raw values for this row
            formatted_row_cells = []  # Formatted strings for this row

            # Process each cell in the row
            for col_idx in range(1, max_data_cols + 1):
                # Create cell reference like "A1", "B1", etc.
                cell_ref = f"{get_column_letter(col_idx)}{row_idx}"
                cell = sheet[cell_ref]
                cell_value = cell.value

                # Convert value to string for display (handle None/empty cells)
                display_value = str(cell_value) if cell_value is not None else ""

                # Escape characters that break markdown tables
                # | is the column separator in markdown
                # \n and \r would create new lines
                display_value = display_value.replace("|", "\\|").replace("\n", " ").replace("\r", " ")

                # Create formatted version: "A1:value"
                formatted_cell = f"{cell_ref}:{display_value}"

                row_cells.append(cell_value)          # Store raw value
                formatted_row_cells.append(formatted_cell)  # Store formatted string

            # Estimate tokens for this row
            row_str = " | ".join(formatted_row_cells)
            row_tokens = calculate_token_cost_line(row_str)

            # Check if adding this row would exceed budget
            if tokens_used + row_tokens > token_budget:
                # Always include at least 5 rows for minimal useful data
                if rows_shown < 5:
                    preview_data.append(row_cells)
                    formatted_data.append(formatted_row_cells)
                    rows_shown += 1
                    tokens_used += row_tokens
                # Stop after hitting budget
                break

            # Add the row to our preview
            preview_data.append(row_cells)
            formatted_data.append(formatted_row_cells)
            rows_shown += 1
            tokens_used += row_tokens

        return {
            'data': preview_data,
            'formatted_data': formatted_data,
            'rows_shown': rows_shown,
            'cols_shown': max_data_cols,
            'start_row': start_row,
            'is_truncated': rows_shown < max_data_rows,  # True if we didn't show all rows
            'tokens_used': tokens_used
        }

    def _setup_excel_libraries(self):
        """
         * Load Excel-processing libraries and setup the code execution environment.
         *
         * This method:
         * 1. Imports required libraries (openpyxl, pandas, numpy, matplotlib)
         * 2. Loads the Excel workbook(s) into memory
         * 3. Creates helper functions for common Excel operations
         * 4. Adds everything to code_globals so AI-generated code can use them
         *
         * Libraries Added to Sandbox:
         * ============================
         * - openpyxl: Direct Excel file manipulation
         * - pandas: Data analysis and DataFrames
         * - numpy: Numerical computing
         * - matplotlib: Plotting (with non-GUI backend)
         * - ExcelToolkit: Custom helper functions for the AI
         *
         * @throws: ImportError if libraries aren't installed
         * @throws: Exception if Excel file is corrupted or can't be loaded
        """
        try:
            # Import required libraries
            import openpyxl
            from openpyxl.utils import range_boundaries, get_column_letter, column_index_from_string
            import pandas as pd
            import numpy as np
            import matplotlib
            matplotlib.use('Agg')  # Use non-interactive backend (no GUI needed)

            # Load all Excel files
            start_time = time.time()
            workbooks = {}  # Dictionary mapping file paths to workbooks
            all_sheet_names = []  # List of all sheet names across all files
            
            for excel_path in self.excel_paths:
                logger.info(f"Loading spreadsheet file: {excel_path}")
                workbook = self._load_workbook_from_path(excel_path)
                workbooks[excel_path] = workbook
                all_sheet_names.extend([(excel_path, sheet_name) for sheet_name in workbook.sheetnames])
            
            load_time = time.time() - start_time
            logger.info(f"All spreadsheet files loaded in {load_time:.2f}s")
            print(f"📊 [Excel] Loaded {len(self.excel_paths)} file(s) in {load_time:.2f}s")
            
            # Use the first workbook as the primary one for ExcelToolkit
            primary_workbook = workbooks[self.excel_paths[0]]
            primary_path = self.excel_paths[0]
            
            # Add libraries to the code execution environment
            self.code_globals.update({
                'openpyxl': openpyxl,                    # Excel library
                'workbooks': workbooks,                  # Dictionary of all workbooks
                'sheet_names': primary_workbook.sheetnames,  # List of sheet names from primary workbook
                'range_boundaries': range_boundaries,    # Convert "A1:B2" to coordinates
                'get_column_letter': get_column_letter,  # Convert 1 -> "A"
                'column_index_from_string': column_index_from_string,  # Convert "A" -> 1
                'pandas': pd,                            # Data analysis library
                'pd': pd,                                # Short alias
                'numpy': np,                             # Numerical computing library
                'np': np,                                # Short alias
            })

            # Create ExcelToolkit with helper functions for common operations
            # For multi-file support, we'll use the primary workbook but provide access to all
            self.mcp_toolkit = ExcelToolkit(primary_workbook, primary_path)
            excel_helpers = self.mcp_toolkit.get_helper_functions_dict()
            
            # Add multi-workbook helper functions
            def get_workbook(file_path: str):
                """Get a workbook by file path."""
                if file_path in workbooks:
                    return workbooks[file_path]
                # Try to find by filename
                for path, wb in workbooks.items():
                    if os.path.basename(path) == os.path.basename(file_path):
                        return wb
                raise ValueError(f"Workbook not found: {file_path}. Available: {list(workbooks.keys())}")
            
            def list_all_workbooks():
                """List all loaded workbook file paths."""
                return list(workbooks.keys())
            
            def get_sheet_from_workbook(file_path: str, sheet_name: str):
                """Get a sheet from a specific workbook."""
                wb = get_workbook(file_path)
                if sheet_name in wb.sheetnames:
                    return wb[sheet_name]
                raise ValueError(f"Sheet '{sheet_name}' not found in {file_path}. Available: {wb.sheetnames}")
            
            def inspector_multi(file_path: str, range_ref: str, sheet_name: Optional[str] = None):
                """
                Read a range from a specific workbook by file path.
                
                Args:
                    file_path: Full path to the Excel file OR just the filename
                    range_ref: Excel range reference (e.g., "A1:C10")
                    sheet_name: Name of the sheet (required if workbook has multiple sheets)
                
                Returns:
                    List of lists containing cell values
                """
                wb = get_workbook(file_path)
                if sheet_name is None:
                    sheet = wb.active
                else:
                    if sheet_name not in wb.sheetnames:
                        raise ValueError(f"Sheet '{sheet_name}' not found in {os.path.basename(file_path)}. Available sheets: {wb.sheetnames}")
                    sheet = wb[sheet_name]
                cell_range = sheet[range_ref]
                if hasattr(cell_range, 'value'):
                    return [[cell_range.value]]
                result = []
                for row in cell_range:
                    row_values = [cell.value for cell in row]
                    result.append(row_values)
                return result
            
            # Add multi-workbook helpers to the execution environment
            excel_helpers.update({
                'get_workbook': get_workbook,
                'list_all_workbooks': list_all_workbooks,
                'get_sheet_from_workbook': get_sheet_from_workbook,
                'inspector_multi': inspector_multi,
            })
            
            self.code_globals.update(excel_helpers)  # Add helpers to sandbox

            logger.info("Excel libraries loaded successfully")
            logger.info(f"Loaded {len(workbooks)} workbook(s)")
            for path, wb in workbooks.items():
                logger.info(f"  - {os.path.basename(path)}: {len(wb.sheetnames)} sheet(s) - {wb.sheetnames}")
            print("📦 [SheetBrain] Excel libraries loaded successfully")
            print(f"📊 [SheetBrain] Loaded {len(workbooks)} workbook(s):")
            for path, wb in workbooks.items():
                print(f"  📄 {os.path.basename(path)}: {len(wb.sheetnames)} sheet(s) - {wb.sheetnames}")

        except ImportError as e:
            # Missing library (e.g., openpyxl not installed)
            logger.error(f"Failed to import required libraries: {e}")
            print(f"❌ [SheetBrain] Failed to import required libraries: {e}")
            raise  # Re-raise to stop execution

        except Exception as e:
            # Problem loading the Excel file (corrupted, wrong format, etc.)
            logger.error(f"Failed to load Excel file: {e}")
            print(f"❌ [SheetBrain] Failed to load Excel file: {e}")
            raise  # Re-raise to stop execution