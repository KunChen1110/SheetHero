# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
 * Excel utility library and toolkit for SheetBrain.
 *
 * This module provides the ExcelToolkit class - a comprehensive wrapper around
 * openpyxl that gives the AI agent the ability to:
 *
 * 1. **Read Excel Data**: Extract cell values, ranges, and attributes
 * 2. **Search & Analyze**: Find specific values, convert to pandas DataFrames
 * 3. **Visualize**: Create and save matplotlib charts directly into Excel
 * 4. **Edit & Modify**: Insert/delete rows/columns, set cell values, copy ranges
 * 5. **Format & Style**: Apply colors, fonts, borders, alignment
 * 6. **Chart Creation**: Add bar, line, pie, scatter, and area charts
 * 7. **Formula Management**: Add Excel formulas to cells
 *
 * Design Philosophy:
 * ==================
 * This toolkit acts as a "translator" between the AI's natural language
 * instructions and Excel's technical API. Each method is designed to be:
 * - **Safe**: Validates inputs and provides clear error messages
 * - **Verbose**: Prints what it's doing (helps debug AI-generated code)
 * - **Convenient**: Handles common patterns in single function calls
 * - **Sandbox-Ready**: Can be exposed to AI-generated code safely
 *
 * Token Calculation:
 * ==================
 * The calculate_token_cost_line() function helps manage AI context limits
 * by accurately counting tokens using tiktoken (OpenAI's tokenizer).
 * This prevents sending too much data to the AI model.
 *
 * @author: Microsoft Corporation
 * @license: MIT License
"""

# Import standard library modules
import os              # File path operations and cleanup
import re              # Regular expressions for cell reference validation
import tempfile        # Create temporary files for images
import io              # In-memory byte buffers for image handling
from typing import List, Optional, Dict, Union, Any  # Type hints

# Import third-party libraries
import matplotlib.pyplot as plt  # Plotting library
from openpyxl.utils import get_column_letter, column_index_from_string  # Excel coordinate conversion
from openpyxl.utils.cell import coordinate_to_tuple  # Convert "A1" to (1, 1)
from openpyxl.styles import PatternFill, Font, Border, Side, Alignment  # Excel formatting
from openpyxl.chart import BarChart, LineChart, PieChart, ScatterChart, AreaChart  # Excel charts
from openpyxl.chart.reference import Reference  # Chart data references
from openpyxl.drawing.image import Image  # Excel image handling
from PIL import Image as PILImage  # Python Imaging Library (for image manipulation)
import tiktoken  # OpenAI's token counting library


def calculate_token_cost_line(text: str, model: str = "gpt-4") -> int:
    """
     * Calculate the exact token cost of a text string using OpenAI's tokenizer.
     *
     * Token counting is critical for managing AI context windows and costs.
     * Different AI models use different tokenization schemes - this function
     * maps model names to the correct tokenizer.
     *
     * Why This Matters:
     * =================
     * - **Budget Management**: Prevents exceeding token limits (e.g., 128K for GPT-4)
     * - **Cost Control**: You pay per token, so accurate counting saves money
     * - **Context Optimization**: Helps decide how much Excel data to send to AI
     *
     * Token Estimation Rule of Thumb:
     * ================================
     * ~1 token ≈ 0.75 words ≈ 4 characters (for English text)
     * Excel data with many numbers/symbols may use more tokens.
     *
     * @param text: The string to count tokens for
     * @param model: AI model name (e.g., "gpt-4", "gpt-4o", "gpt-3.5-turbo")
     *
     * @return: Exact token count as integer
     *
     * @example:
     * ```python
     * # Count tokens for a simple string
     * tokens = calculate_token_cost_line("Hello, world!")
     * print(tokens)  # Output: ~4
     *
     * # Count tokens for a row of Excel data
     * row_data = "A1:Name | B1:Age | C1:Salary"
     * tokens = calculate_token_cost_line(row_data)
     * ```
    """
    try:
        # Map model names to tiktoken encoding schemes
        # Different models were trained with different tokenizers
        model_encodings = {
            "gpt-4": "cl100k_base",           # GPT-4 and GPT-3.5 Turbo
            "gpt-4-turbo": "cl100k_base",
            "gpt-4o": "o200k_base",           # GPT-4o uses newer tokenizer
            "gpt-3.5-turbo": "cl100k_base",
            "gpt-5-nano-2025-08-07": "o200k_base",
            "text-embedding-ada-002": "cl100k_base",
        }

        # Get the appropriate tokenizer encoding
        encoding_name = model_encodings.get(model, "cl100k_base")  # Default fallback
        encoding = tiktoken.get_encoding(encoding_name)

        # Encode the text and count tokens
        tokens = encoding.encode(text)
        return len(tokens)

    except Exception:
        # Fallback: rough estimate if tiktoken fails
        # Assumes ~3.5 characters per token (conservative estimate)
        char_count = len(text)
        token_count = max(1, int(char_count / 3.5))
        return token_count


class ExcelToolkit:
    """
     * Comprehensive Excel manipulation toolkit for AI-generated code.
     *
     * This class wraps openpyxl to provide a simpler, safer API that the AI
     * can use to read, analyze, modify, and visualize Excel data. It handles
     * common patterns in a single method call and provides clear feedback.
     *
     * Key Features:
     * =============
     * - **Reading**: Extract cell values, ranges, attributes (color, font, formulas)
     * - **Searching**: Find values across entire workbook
     * - **DataFrames**: Convert sheets to pandas DataFrames for analysis
     * - **Visualization**: Save matplotlib plots directly into Excel cells
     * - **Editing**: Insert/delete rows/columns, set values, copy ranges
     * - **Formatting**: Apply colors, fonts, borders, alignment
     * - **Charts**: Create bar, line, pie, scatter, area charts
     * - **Formulas**: Add Excel formulas programmatically
     *
     * Temporary File Management:
     * ==========================
     * The toolkit saves matplotlib charts as temporary image files before
     * inserting them into Excel. The `_temp_files` list tracks these files
     * so they can be cleaned up when `save_workbook()` is called.
     *
     * @param workbook: An openpyxl Workbook object (already loaded Excel file)
     * @param excel_path: Path to the original Excel file (for saving)
    """

    def __init__(self, workbook, excel_path: str):
        """
         * Initialize the Excel toolkit.
         *
         * @param workbook: An openpyxl workbook instance (from load_workbook())
         * @param excel_path: Path to the Excel file (used when saving changes)
         *
         * @example:
         * ```python
         * # Load an Excel file first
         * from openpyxl import load_workbook
         * workbook = load_workbook("sales.xlsx")
         *
         * # Create toolkit
         * toolkit = ExcelToolkit(workbook, "sales.xlsx")
         * ```
        """
        self.workbook = workbook
        self.excel_path = excel_path
        self._temp_files = []  # Track temporary image files for cleanup

    def get_sheet(self, sheet_name: Optional[str] = None):
        """
         * Get a worksheet by name, or return the active sheet if no name provided.
         *
         * Excel always has an "active" sheet (the one displayed when file opens).
         * This method provides flexibility: specify a sheet or get the default.
         *
         * @param sheet_name: Name of sheet to get (e.g., "Sheet1"). If None, gets active sheet.
         *
         * @return: openpyxl Worksheet object
         *
         * @throws: ValueError if specified sheet doesn't exist
         *
         * @example:
         * ```python
         * # Get active sheet
         * sheet = toolkit.get_sheet()
         *
         * # Get specific sheet
         * sheet = toolkit.get_sheet("SalesData")
         * ```
        """
        if sheet_name is None:
            return self.workbook.active
        if sheet_name in self.workbook.sheetnames:
            return self.workbook[sheet_name]
        else:
            raise ValueError(f"Sheet '{sheet_name}' not found. Available: {self.workbook.sheetnames}")

    def inspector(self, range_ref: str, sheet_name: Optional[str] = None) -> List[List]:
        """
         * Read a range of cells and return their values as a 2D list.
         *
         * This is the primary method for reading Excel data. It handles ranges
         * like "A1", "A1:B5", or entire columns like "A:A".
         *
         * @param range_ref: Excel range reference in A1 notation (e.g., "A1:B5")
         * @param sheet_name: Optional sheet name (uses active sheet if None)
         *
         * @return: 2D list of cell values (list of rows, each row is a list of values)
         *
         * @example:
         * ```python
         * # Read single cell
         * value = toolkit.inspector("A1")
         * # Returns: [[42]]
         *
         * # Read range
         * data = toolkit.inspector("A1:C3")
         * # Returns: [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
         *
         * # Read with sheet name
         * data = toolkit.inspector("B2:D10", "SalesData")
         * ```
        """
        sheet = self.get_sheet(sheet_name)
        cell_range = sheet[range_ref]

        # Handle single cell case (not a range)
        if hasattr(cell_range, 'value'):
            return [[cell_range.value]]

        # Handle multi-cell range
        result = []
        for row in cell_range:
            row_values = [cell.value for cell in row]
            result.append(row_values)
        return result

    def inspector_attribute(self, range_ref: str, attributes: List[str],
                            sheet_name: Optional[str] = None) -> Dict:
        """
         * Read formatting attributes from a range of cells.
         *
         * This method extracts visual properties like cell color, font style,
         * or formulas. Useful when analysis depends on formatting (e.g.,
         * "sum all red cells" or "check if cell contains a formula").
         *
         * @param range_ref: Excel range in A1 notation (e.g., "A1:B5")
         * @param attributes: List of attributes to read: ["color", "font", "formula"]
         * @param sheet_name: Optional sheet name
         *
         * @return: Dictionary with attribute values for each cell coordinate
         *
         * @throws: ValueError if invalid attributes specified
         *
         * @example:
         * ```python
         * # Check cell colors and formulas
         * attrs = toolkit.inspector_attribute("A1:B5", ["color", "formula"])
         * # Returns: {
         * #     "range": "A1:B5",
         * #     "sheet": "Sheet1",
         * #     "attributes": {
         * #         "color": {"A1": "#FF0000", "B2": "#00FF00"},
         * #         "formula": {"A2": "=SUM(B1:B5)"}
         * #     },
         * #     "total_cells_processed": 10
         * # }
         * ```
        """
        print(f"🔎 [read_range_attribute] Reading attributes {attributes} for range {range_ref} in sheet '{sheet_name}'")

        # Validate attributes
        if not attributes:
            return {"error": "No attributes specified"}

        valid_attributes = ["color", "font", "formula"]
        invalid_attrs = [attr for attr in attributes if attr not in valid_attributes]
        if invalid_attrs:
            return {"error": f"Invalid attributes: {invalid_attrs}. Valid options: {valid_attributes}"}

        try:
            sheet = self.get_sheet(sheet_name)
            cell_range = sheet[range_ref]
        except (ValueError, KeyError) as e:
            return {"error": str(e)}

        # Normalize to list of cells (handles both single cell and range)
        if hasattr(cell_range, 'coordinate'):
            cells_to_process = [cell_range]
        else:
            cells_to_process = []
            for row in cell_range:
                if hasattr(row, '__iter__'):
                    cells_to_process.extend(row)
                else:
                    cells_to_process.append(row)

        result_attributes = {}

        # Extract each requested attribute
        for attr in attributes:
            result_attributes[attr] = {}

            for cell in cells_to_process:
                cell_coord = cell.coordinate
                attr_value = None

                if attr == "color":
                    # Get background fill color (if any)
                    if cell.fill and cell.fill.fgColor and cell.fill.fgColor.rgb != '00000000':
                        attr_value = f"#{cell.fill.fgColor.rgb}"

                elif attr == "font":
                    # Compile font properties into a string
                    font_details = []
                    if cell.font:
                        if cell.font.color and cell.font.color.rgb != '00000000':
                            font_details.append(f"color:#{cell.font.color.rgb}")
                        if cell.font.name:
                            font_details.append(f"name:{cell.font.name}")
                        if cell.font.size:
                            font_details.append(f"size:{cell.font.size}")
                        if cell.font.bold:
                            font_details.append("bold:True")
                        if cell.font.italic:
                            font_details.append("italic:True")
                        if cell.font.underline and cell.font.underline != 'none':
                            font_details.append(f"underline:{cell.font.underline}")

                    attr_value = "; ".join(font_details) if font_details else None

                elif attr == "formula":
                    # Get formula if cell contains one
                    if cell.data_type == 'f' and cell.value:
                        attr_value = str(cell.value)

                if attr_value is not None:
                    result_attributes[attr][cell_coord] = attr_value

        return {
            "range": range_ref,
            "sheet": sheet_name or sheet.title,
            "attributes": result_attributes,
            "total_cells_processed": len(cells_to_process)
        }

    def search(self, value: Any, sheet_name: Optional[str] = None,
               case_sensitive: bool = False, search_type: str = "partial") -> List[Dict]:
        """
         * Search for cells containing a specific value across the entire sheet.
         *
         * This method scans every cell in the sheet to find matches.
         * Supports partial matches (contains), whole matches (exact), or
         * stripped matches (ignores whitespace).
         *
         * @param value: The value to search for (string, number, etc.)
         * @param sheet_name: Optional sheet name (searches active sheet if None)
         * @param case_sensitive: Whether to match case exactly (default: False)
         * @param search_type: "partial", "whole", or "strip" (default: "partial")
         *
         * @return: List of dictionaries with cell coordinates and values
         *
         * @throws: ValueError if invalid search_type specified
         *
         * @example:
         * ```python
         * # Find all cells containing "apple"
         * results = toolkit.search("apple")
         * # Returns: [
         * #     {'coordinate': 'A3', 'value': 'pineapple', 'row': 3, 'column': 1},
         * #     {'coordinate': 'C5', 'value': 'apple pie', 'row': 5, 'column': 3}
         * # ]
         *
         * # Case-sensitive exact match
         * results = toolkit.search("Total", case_sensitive=True, search_type="whole")
         * ```
        """
        sheet = self.get_sheet(sheet_name)
        matches = []

        # Validate search type
        valid_search_types = ["partial", "whole", "strip"]
        if search_type not in valid_search_types:
            raise ValueError(f"Invalid search_type '{search_type}'. Valid options: {valid_search_types}")

        # Prepare search value
        search_value = str(value) if case_sensitive else str(value).lower()

        # Scan all cells in the sheet
        for row in sheet.iter_rows():
            for cell in row:
                if cell.value is not None:
                    cell_str = str(cell.value)

                    if not case_sensitive:
                        cell_str = cell_str.lower()

                    is_match = False

                    # Determine match type
                    if search_type == "partial":
                        is_match = search_value in cell_str
                    elif search_type == "whole":
                        is_match = search_value == cell_str
                    elif search_type == "strip":
                        stripped_cell_str = cell_str.strip()
                        is_match = search_value == stripped_cell_str

                    if is_match:
                        matches.append({
                            'coordinate': cell.coordinate,
                            'value': cell.value,
                            'row': cell.row,
                            'column': cell.column
                        })

        return matches

    def get_sheet_as_dataframe(self, sheet_name: Optional[str] = None,
                               header_row: int = 1, max_rows: Optional[int] = None):
        """
         * Convert an Excel sheet to a pandas DataFrame for data analysis.
         *
         * This method transforms Excel data into pandas DataFrame format,
         * enabling powerful analysis operations (filtering, grouping, statistics).
         * The first row is used as column headers by default.
         *
         * @param sheet_name: Optional sheet name (uses active sheet if None)
         * @param header_row: Which row to use as column headers (1-indexed, default: 1)
         * @param max_rows: Maximum rows to read (default: None = all rows)
         *
         * @return: pandas DataFrame with the sheet data
         *
         * @throws: ImportError if pandas is not installed
         *
         * @example:
         * ```python
         * # Convert sheet to DataFrame
         * df = toolkit.get_sheet_as_dataframe("SalesData")
         *
         * # Analyze with pandas
         * total_sales = df['Revenue'].sum()
         * average_age = df['Age'].mean()
         * filtered = df[df['Region'] == 'North']
         * ```
        """
        import pandas as pd  # Local import (only when needed)
        sheet = self.get_sheet(sheet_name)

        # Extract all cell values
        data = []
        for i, row in enumerate(sheet.iter_rows(values_only=True), 1):
            if max_rows and i > max_rows:
                break
            data.append(row)

        if not data:
            return pd.DataFrame()  # Return empty DataFrame for empty sheet

        # Use specified header row for column names
        if header_row > 0 and len(data) >= header_row:
            headers = data[header_row - 1]
            data_rows = data[header_row:]
            df = pd.DataFrame(data_rows, columns=headers)
        else:
            df = pd.DataFrame(data)

        return df

    def save_plot_to_excel(self, sheet_name: str, cell_position: str = "A1",
                           figsize: tuple = (10, 6), dpi: int = 100) -> str:
        """
         * Save the current matplotlib plot as an image in an Excel sheet.
         *
         * This method:
         * 1. Gets the current matplotlib figure
         * 2. Saves it to a temporary PNG file
         * 3. Inserts the image into the specified Excel cell
         * 4. Tracks the temp file for cleanup later
         *
         * @param sheet_name: Target sheet name (created if doesn't exist)
         * @param cell_position: Top-left cell for the image (e.g., "A1")
         * @param figsize: Figure size in inches: (width, height)
         * @param dpi: Image resolution (dots per inch)
         *
         * @return: Success message string
         *
         * @example:
         * ```python
         * # Create a plot
         * import matplotlib.pyplot as plt
         * plt.plot([1, 2, 3], [4, 5, 6])
         * plt.title("Sales Trend")
         *
         * # Save to Excel
         * toolkit.save_plot_to_excel("Charts", "B2")
         * ```
        """
        # Create sheet if it doesn't exist
        if sheet_name not in self.workbook.sheetnames:
            self.workbook.create_sheet(sheet_name)
        sheet = self.workbook[sheet_name]

        # Get current figure
        fig = plt.gcf()
        if fig.get_axes():  # Check if figure has content
            fig.set_size_inches(figsize)
            plt.tight_layout()  # Adjust spacing

            # Save to memory buffer first
            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format='png', dpi=dpi, bbox_inches='tight')
            img_buffer.seek(0)

            # Convert to PIL Image
            pil_img = PILImage.open(img_buffer)

            # Save to temporary file (Excel needs a file path, not just bytes)
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                pil_img.save(tmp_file.name, 'PNG')
                tmp_filename = tmp_file.name

            # Add to Excel
            img = Image(tmp_filename)
            sheet.add_image(img, cell_position)

            # Track temp file for cleanup later
            self._temp_files.append(tmp_filename)

            print(f"✅ Chart saved to sheet '{sheet_name}' at position {cell_position}")
            plt.close(fig)  # Close plot to free memory
            return f"Chart saved to {sheet_name}!{cell_position}"
        else:
            print("⚠️ No plot found to save. Create a plot first.")
            return "No plot to save"

    def save_workbook(self) -> str:
        """
         * Save the workbook to a new file and cleanup temporary files.
         *
         * This method:
         * 1. Generates output filename by appending "_output" to original name
         * 2. Saves the workbook
         * 3. Deletes all temporary image files created by save_plot_to_excel()
         * 4. Clears the _temp_files tracking list
         *
         * **Important**: Always call this after using save_plot_to_excel() to
         * prevent temporary files from accumulating on your system.
         *
         * @return: Path to the saved file
         *
         * @example:
         * ```python
         * # After making changes and saving plots
         * new_file = toolkit.save_workbook()
         * # Returns: "sales_data_output.xlsx"
         * ```
        """
        # Generate output filename
        dir_path = os.path.dirname(self.excel_path)
        base_name = os.path.splitext(os.path.basename(self.excel_path))[0]
        filename = os.path.join(dir_path, f"{base_name}_output.xlsx")

        # Save the workbook
        self.workbook.save(filename)

        # Clean up temporary image files
        for temp_file in self._temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)  # Delete file
            except Exception as e:
                print(f"⚠️ Warning: Could not delete temporary file {temp_file}: {e}")

        # Clear tracking list
        self._temp_files = []

        print(f"💾 Workbook saved to: {filename}")
        return filename

    # ==================== Excel Editing Functions ====================
    # These methods modify the Excel file structure and content

    def insert_rows(self, sheet_name: str, row_index: int, count: int = 1) -> str:
        """
         * Insert empty rows at a specific position in the sheet.
         *
         * Existing rows at and below the insertion point are shifted down.
         *
         * @param sheet_name: Target sheet name
         * @param row_index: Row number where insertion starts (1-indexed)
         * @param count: Number of rows to insert (default: 1)
         *
         * @return: Success message string
         *
         * @throws: ValueError if row_index or count is invalid
         *
         * @example:
         * ```python
         * # Insert 3 rows starting at row 5
         * toolkit.insert_rows("SalesData", 5, 3)
         * ```
        """
        try:
            sheet = self.get_sheet(sheet_name)

            # Validate inputs
            if row_index < 1 or count < 1:
                raise ValueError("Row index and count must be >= 1")

            # Perform insertion
            sheet.insert_rows(row_index, count)

            message = f"✅ Inserted {count} row(s) at row {row_index} in sheet '{sheet_name}'"
            print(message)
            return message

        except Exception as e:
            error_msg = f"❌ Error inserting rows: {str(e)}"
            print(error_msg)
            raise Exception(error_msg)

    def insert_columns(self, sheet_name: str, col_index: Union[int, str], count: int = 1) -> str:
        """
         * Insert empty columns at a specific position.
         *
         * Accepts column index as either letter ("B") or number (2).
         * Existing columns at and to the right are shifted right.
         *
         * @param sheet_name: Target sheet name
         * @param col_index: Column letter or number (1-indexed)
         * @param count: Number of columns to insert (default: 1)
         *
         * @return: Success message string
         *
         * @throws: ValueError if column index or count is invalid
         *
         * @example:
         * ```python
         * # Insert 2 columns at column B
         * toolkit.insert_columns("SalesData", "B", 2)
         *
         * # Or using column number
         * toolkit.insert_columns("SalesData", 2, 2)
         * ```
        """
        try:
            sheet = self.get_sheet(sheet_name)

            # Convert column letter to number if needed (e.g., "B" -> 2)
            if isinstance(col_index, str):
                col_index = column_index_from_string(col_index)

            # Validate inputs
            if col_index < 1 or count < 1:
                raise ValueError("Column index and count must be >= 1")

            # Perform insertion
            sheet.insert_cols(col_index, count)

            col_letter = get_column_letter(col_index)
            message = f"✅ Inserted {count} column(s) at column {col_letter} in sheet '{sheet_name}'"
            print(message)
            return message

        except Exception as e:
            error_msg = f"❌ Error inserting columns: {str(e)}"
            print(error_msg)
            raise Exception(error_msg)

    def delete_rows(self, sheet_name: str, start_row: int, count: int = 1) -> str:
        """
         * Delete rows from the sheet.
         *
         * Rows below the deleted section are shifted up.
         *
         * @param sheet_name: Target sheet name
         * @param start_row: First row to delete (1-indexed)
         * @param count: Number of rows to delete (default: 1)
         *
         * @return: Success message string
         *
         * @throws: ValueError if start_row or count is invalid, or if start_row is beyond sheet bounds
         *
         * @example:
         * ```python
         * # Delete 5 rows starting at row 10
         * toolkit.delete_rows("SalesData", 10, 5)
         * ```
        """
        try:
            sheet = self.get_sheet(sheet_name)

            # Validate inputs
            if start_row < 1 or count < 1:
                raise ValueError("Start row and count must be >= 1")
            if start_row > sheet.max_row:
                raise ValueError(f"Start row {start_row} exceeds sheet max row {sheet.max_row}")

            # Perform deletion
            sheet.delete_rows(start_row, count)

            message = f"✅ Deleted {count} row(s) starting from row {start_row} in sheet '{sheet_name}'"
            print(message)
            return message

        except Exception as e:
            error_msg = f"❌ Error deleting rows: {str(e)}"
            print(error_msg)
            raise Exception(error_msg)

    def delete_columns(self, sheet_name: str, start_col: Union[int, str], count: int = 1) -> str:
        """
         * Delete columns from the sheet.
         *
         * Columns to the right of the deleted section are shifted left.
         *
         * @param sheet_name: Target sheet name
         * @param start_col: Column letter or number to start deleting from
         * @param count: Number of columns to delete (default: 1)
         *
         * @return: Success message string
         *
         * @throws: ValueError if start_col or count is invalid
         *
         * @example:
         * ```python
         * # Delete columns C and D
         * toolkit.delete_columns("SalesData", "C", 2)
         * ```
        """
        try:
            sheet = self.get_sheet(sheet_name)

            # Convert column letter to number if needed
            if isinstance(start_col, str):
                start_col = column_index_from_string(start_col)

            # Validate inputs
            if start_col < 1 or count < 1:
                raise ValueError("Start column and count must be >= 1")
            if start_col > sheet.max_column:
                raise ValueError(f"Start column {start_col} exceeds sheet max column {sheet.max_column}")

            # Perform deletion
            sheet.delete_cols(start_col, count)

            col_letter = get_column_letter(start_col)
            message = f"✅ Deleted {count} column(s) starting from column {col_letter} in sheet '{sheet_name}'"
            print(message)
            return message

        except Exception as e:
            error_msg = f"❌ Error deleting columns: {str(e)}"
            print(error_msg)
            raise Exception(error_msg)

    def set_cell_value(self, sheet_name: str, cell_ref: str, value: Any) -> str:
        """
         * Set the value of a single cell.
         *
         * @param sheet_name: Target sheet name
         * @param cell_ref: Cell reference in A1 notation (e.g., "A1", "B5")
         * @param value: Value to set (string, number, date, etc.)
         *
         * @return: Success message string
         *
         * @throws: ValueError if cell reference format is invalid
         *
         * @example:
         * ```python
         * # Set cell A1 to "Total Sales"
         * toolkit.set_cell_value("SalesData", "A1", "Total Sales")
         *
         * # Set cell B1 to a number
         * toolkit.set_cell_value("SalesData", "B1", 12345.67)
         * ```
        """
        try:
            sheet = self.get_sheet(sheet_name)

            # Validate cell reference format (must be like "A1", "B5", "AA100")
            if not re.match(r'^[A-Z]+[0-9]+$', cell_ref.upper()):
                raise ValueError(f"Invalid cell reference: {cell_ref}")

            # Set the value
            sheet[cell_ref] = value

            message = f"✅ Set cell {cell_ref} to '{value}' in sheet '{sheet_name}'"
            print(message)
            return message

        except Exception as e:
            error_msg = f"❌ Error setting cell value: {str(e)}"
            print(error_msg)
            raise Exception(error_msg)

    def set_range_values(self, sheet_name: str, start_cell: str,
                         values_2d_array: List[List[Any]]) -> str:
        """
         * Set values for a range of cells using a 2D array.
         *
         * This method writes an entire block of data starting at a specific cell.
         * The 2D array should be a list of rows, where each row is a list of values.
         *
         * @param sheet_name: Target sheet name
         * @param start_cell: Top-left cell where writing begins (e.g., "A1")
         * @param values_2d_array: 2D list of values (list of rows)
         *
         * @return: Success message string showing the range that was written
         *
         * @throws: ValueError if cell reference format is invalid or array is malformed
         *
         * @example:
         * ```python
         * # Write a 3x3 block of data starting at A1
         * data = [
         *     ["Name", "Age", "Score"],
         *     ["Alice", 25, 95],
         *     ["Bob", 30, 87]
         * ]
         * toolkit.set_range_values("Sheet1", "A1", data)
         * ```
        """
        try:
            sheet = self.get_sheet(sheet_name)

            # Validate inputs
            if not re.match(r'^[A-Z]+[0-9]+$', start_cell.upper()):
                raise ValueError(f"Invalid cell reference: {start_cell}")

            if not values_2d_array or not isinstance(values_2d_array, list):
                raise ValueError("values_2d_array must be a non-empty list")

            # Convert start cell to row/column numbers
            start_row, start_col = coordinate_to_tuple(start_cell)

            # Write the 2D array to the sheet
            for row_idx, row_values in enumerate(values_2d_array):
                if not isinstance(row_values, list):
                    raise ValueError(f"Row {row_idx} must be a list")

                for col_idx, value in enumerate(row_values):
                    current_row = start_row + row_idx
                    current_col = start_col + col_idx
                    sheet.cell(row=current_row, column=current_col, value=value)

            # Calculate the written range for the success message
            rows_count = len(values_2d_array)
            cols_count = max(len(row) for row in values_2d_array) if values_2d_array else 0
            end_cell = sheet.cell(row=start_row + rows_count - 1,
                                  column=start_col + cols_count - 1).coordinate

            message = f"✅ Set range {start_cell}:{end_cell} ({rows_count}x{cols_count}) in sheet '{sheet_name}'"
            print(message)
            return message

        except Exception as e:
            error_msg = f"❌ Error setting range values: {str(e)}"
            print(error_msg)
            raise Exception(error_msg)

    def copy_range(self, src_sheet: str, src_range: str, dest_sheet: str, dest_cell: str) -> str:
        """
         * Copy data from one range to another (possibly across sheets).
         *
         * This method reads values from a source range and writes them to a
         * destination starting cell. Can copy within same sheet or between sheets.
         *
         * @param src_sheet: Source sheet name
         * @param src_range: Source range in A1 notation (e.g., "A1:B5")
         * @param dest_sheet: Destination sheet name
         * @param dest_cell: Top-left cell of destination (e.g., "A10")
         *
         * @return: Success message string showing the destination range
         *
         * @throws: ValueError if source range format is invalid
         *
         * @example:
         * ```python
         * # Copy A1:B5 from Sheet1 to A10 in Sheet2
         * toolkit.copy_range("Sheet1", "A1:B5", "Sheet2", "A10")
         * ```
        """
        try:
            # Get source and destination sheets
            src_ws = self.get_sheet(src_sheet)
            dest_ws = self.get_sheet(dest_sheet)

            # Validate source range format
            if ':' not in src_range:
                raise ValueError("Source range must be in format 'A1:B2'")

            # Read source data
            source_data = []
            for row in src_ws[src_range]:
                row_data = [cell.value for cell in row]
                source_data.append(row_data)

            # Write to destination if data exists
            if source_data:
                dest_start_row, dest_start_col = coordinate_to_tuple(dest_cell)

                for row_idx, row_values in enumerate(source_data):
                    for col_idx, value in enumerate(row_values):
                        dest_row = dest_start_row + row_idx
                        dest_col = dest_start_col + col_idx
                        dest_ws.cell(row=dest_row, column=dest_col, value=value)

                rows_count = len(source_data)
                cols_count = len(source_data[0]) if source_data else 0
                dest_end_cell = dest_ws.cell(row=dest_start_row + rows_count - 1,
                                             column=dest_start_col + cols_count - 1).coordinate

                message = f"✅ Copied {src_sheet}!{src_range} to {dest_sheet}!{dest_cell}:{dest_end_cell}"
                print(message)
                return message
            else:
                message = "⚠️ No data found in source range"
                print(message)
                return message

        except Exception as e:
            error_msg = f"❌ Error copying range: {str(e)}"
            print(error_msg)
            raise Exception(error_msg)

    def apply_formatting(self, sheet_name: str, range_ref: str, format_dict: Dict[str, Any]) -> str:
        """
         * Apply visual formatting to a range of cells.
         *
         * This method can set background color, font properties, borders,
         * and alignment. Useful for making reports more readable.
         *
         * @param sheet_name: Target sheet name
         * @param range_ref: Range to format (e.g., "A1:B5" or single cell "A1")
         * @param format_dict: Dictionary of formatting properties
         *
         * Supported Format Properties:
         * ----------------------------
         * - fill_color: Background color (name or hex: "red" or "#FF0000")
         * - font_color: Text color (name or hex)
         * - font_size: Text size (number)
         * - font_name: Font family (e.g., "Arial", "Calibri")
         * - bold: True/False
         * - italic: True/False
         * - underline: True/False
         * - border: Border style ("thin", "medium", "thick")
         * - alignment: Horizontal alignment ("left", "center", "right")
         *
         * @return: Success message string
         *
         * @example:
         * ```python
         * # Format header row
         * toolkit.apply_formatting("Sheet1", "A1:C1", {
         *     "fill_color": "blue",
         *     "font_color": "white",
         *     "bold": True,
         *     "alignment": "center"
         * })
         * ```
        """
        try:
            sheet = self.get_sheet(sheet_name)

            # Handle both single cell and range
            if ':' in range_ref:
                cell_range = sheet[range_ref]
                cells = []
                for row in cell_range:
                    if hasattr(row, '__iter__'):
                        cells.extend(row)
                    else:
                        cells.append(row)
            else:
                cells = [sheet[range_ref]]

            # Apply each formatting property
            for cell in cells:
                # Background fill color
                if 'fill_color' in format_dict:
                    color = self._parse_color(format_dict['fill_color'])
                    cell.fill = PatternFill(start_color=color, end_color=color, fill_type='solid')

                # Font properties
                font_kwargs = {}
                if 'font_color' in format_dict:
                    font_kwargs['color'] = self._parse_color(format_dict['font_color'])
                if 'font_size' in format_dict:
                    font_kwargs['size'] = format_dict['font_size']
                if 'font_name' in format_dict:
                    font_kwargs['name'] = format_dict['font_name']
                if 'bold' in format_dict:
                    font_kwargs['bold'] = format_dict['bold']
                if 'italic' in format_dict:
                    font_kwargs['italic'] = format_dict['italic']
                if 'underline' in format_dict:
                    font_kwargs['underline'] = 'single' if format_dict['underline'] else None

                if font_kwargs:
                    cell.font = Font(**font_kwargs)

                # Border
                if 'border' in format_dict:
                    border_style = format_dict['border']
                    side = Side(style=border_style)
                    cell.border = Border(left=side, right=side, top=side, bottom=side)

                # Alignment
                if 'alignment' in format_dict:
                    horizontal = format_dict['alignment']
                    cell.alignment = Alignment(horizontal=horizontal)

            message = f"✅ Applied formatting to {range_ref} in sheet '{sheet_name}'"
            print(message)
            return message

        except Exception as e:
            error_msg = f"❌ Error applying formatting: {str(e)}"
            print(error_msg)
            raise Exception(error_msg)

    def create_chart(self, sheet_name: str, chart_type: str, data_range: str,
                     position: str = "A1", title: str = "",
                     x_axis_title: str = "", y_axis_title: str = "") -> str:
        """
         * Create a chart in the Excel sheet.
         *
         * Supports multiple chart types: bar, line, pie, scatter, and area.
         * The data_range should include headers for the chart to use automatically.
         *
         * @param sheet_name: Target sheet name
         * @param chart_type: Type of chart: "bar", "line", "pie", "scatter", "area"
         * @param data_range: Data range for the chart (e.g., "A1:B10")
         * @param position: Top-left cell for chart placement (default: "A1")
         * @param title: Chart title (optional)
         * @param x_axis_title: X-axis title (optional)
         * @param y_axis_title: Y-axis title (optional)
         *
         * @return: Success message string
         *
         * @throws: ValueError if chart_type is not supported
         *
         * @example:
         * ```python
         * # Create a bar chart of sales data
         * toolkit.create_chart(
         *     "Charts",
         *     "bar",
         *     "A1:B10",  # A1:A10 = Categories, B1:B10 = Values
         *     position="D2",
         *     title="Sales by Region",
         *     x_axis_title="Region",
         *     y_axis_title="Revenue"
         * )
         * ```
        """
        try:
            sheet = self.get_sheet(sheet_name)

            # Map chart type names to openpyxl classes
            chart_classes = {
                'bar': BarChart,
                'line': LineChart,
                'pie': PieChart,
                'scatter': ScatterChart,
                'area': AreaChart
            }

            # Validate chart type
            if chart_type.lower() not in chart_classes:
                raise ValueError(f"Unsupported chart type: {chart_type}. Available: {list(chart_classes.keys())}")

            # Create chart instance
            chart_class = chart_classes[chart_type.lower()]
            chart = chart_class()

            # Set chart properties
            if title:
                chart.title = title
            if x_axis_title and hasattr(chart, 'x_axis'):
                chart.x_axis.title = x_axis_title
            if y_axis_title and hasattr(chart, 'y_axis'):
                chart.y_axis.title = y_axis_title

            # Add data to chart
            data = Reference(sheet, range_string=data_range)
            chart.add_data(data, titles_from_data=True)

            # Place chart on sheet
            sheet.add_chart(chart, position)

            message = f"✅ Created {chart_type} chart from {data_range} at {position} in sheet '{sheet_name}'"
            print(message)
            return message

        except Exception as e:
            error_msg = f"❌ Error creating chart: {str(e)}"
            print(error_msg)
            raise Exception(error_msg)

    def add_formula(self, sheet_name: str, cell_ref: str, formula: str) -> str:
        """
         * Add an Excel formula to a cell.
         *
         * Automatically prepends "=" if missing. The formula is stored as text
         * and Excel calculates it when the file is opened.
         *
         * @param sheet_name: Target sheet name
         * @param cell_ref: Cell reference in A1 notation (e.g., "C1")
         * @param formula: Excel formula (e.g., "SUM(A1:A10)" or "=SUM(A1:A10)")
         *
         * @return: Success message string
         *
         * @throws: ValueError if cell reference format is invalid
         *
         * @example:
         * ```python
         * # Add a SUM formula
         * toolkit.add_formula("SalesData", "C1", "SUM(A1:B1)")
         *
         * # Add a complex formula
         * toolkit.add_formula("SalesData", "D1", "IF(A1>100, 'High', 'Low')")
         * ```
        """
        try:
            sheet = self.get_sheet(sheet_name)

            # Validate cell reference
            if not re.match(r'^[A-Z]+[0-9]+$', cell_ref.upper()):
                raise ValueError(f"Invalid cell reference: {cell_ref}")

            # Ensure formula starts with "="
            if not formula.startswith('='):
                formula = '=' + formula

            # Set the formula
            sheet[cell_ref] = formula

            message = f"✅ Added formula '{formula}' to cell {cell_ref} in sheet '{sheet_name}'"
            print(message)
            return message

        except Exception as e:
            error_msg = f"❌ Error adding formula: {str(e)}"
            print(error_msg)
            raise Exception(error_msg)

    def _parse_color(self, color: str) -> str:
        """
         * Helper method to convert color names to hex format.
         *
         * Supports common color names and hex codes. Used internally
         * by apply_formatting() to normalize color inputs.
         *
         * @param color: Color name (e.g., "red") or hex code (e.g., "#FF0000")
         *
         * @return: 6-digit hex color code without "#" (e.g., "FF0000")
         *
         * @example:
         * ```python
         * # Internal use - not typically called directly
         * hex_color = toolkit._parse_color("red")      # Returns: "FF0000"
         * hex_color = toolkit._parse_color("#00FF00")  # Returns: "00FF00"
         * ```
        """
        # Color name to hex mapping
        color_names = {
            'red': 'FF0000', 'green': '00FF00', 'blue': '0000FF',
            'yellow': 'FFFF00', 'orange': 'FFA500', 'purple': '800080',
            'pink': 'FFC0CB', 'brown': 'A52A2A', 'black': '000000',
            'white': 'FFFFFF', 'gray': '808080', 'grey': '808080'
        }

        if color.startswith('#'):
            return color[1:]  # Remove "#" prefix
        elif color.lower() in color_names:
            return color_names[color.lower()]
        else:
            # Assume it's already a hex code
            return color

    def get_helper_functions_dict(self) -> Dict:
        """
         * Return dictionary of all helper functions for AI code sandbox.
         *
         * This method returns a mapping of function names to function objects.
         * It's used by the ExecutionModule to expose these methods to the AI
         * in a controlled way. The AI can then call them by name in generated code.
         *
         * Why This Pattern?
         * =================
         * Instead of giving AI direct access to the entire toolkit object,
         * we provide a dictionary of specific functions. This:
         * - **Controls API surface**: AI can only call whitelisted methods
         * - **Simplifies code generation**: AI uses function names directly
         * - **Improves security**: Prevents accidental access to internal methods
         * - **Enables sandboxing**: Functions can be injected into isolated namespace
         *
         * @return: Dictionary mapping function names to function objects
         *
         * @example:
         * ```python
         * # In ExecutionModule, this dictionary is added to code_globals
         * helpers = toolkit.get_helper_functions_dict()
         * code_globals.update(helpers)
         *
         * # AI can then generate code like:
         * # data = get_sheet_as_dataframe("Sales")
         * # toolkit.search("total")
         * ```
        """
        return {
            # Reading functions
            'get_sheet': self.get_sheet,
            'inspector': self.inspector,
            'inspector_attribute': self.inspector_attribute,
            'search': self.search,
            'get_sheet_as_dataframe': self.get_sheet_as_dataframe,

            # Visualization
            'save_plot_to_excel': self.save_plot_to_excel,

            # File operations
            'save_workbook': self.save_workbook,

            # Editing functions
            'insert_rows': self.insert_rows,
            'insert_columns': self.insert_columns,
            'delete_rows': self.delete_rows,
            'delete_columns': self.delete_columns,
            'set_cell_value': self.set_cell_value,
            'set_range_values': self.set_range_values,
            'copy_range': self.copy_range,
            'apply_formatting': self.apply_formatting,
            'create_chart': self.create_chart,
            'add_formula': self.add_formula
        }