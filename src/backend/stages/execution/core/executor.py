"""Python code execution for the sandboxed environment."""

import re
import traceback
from typing import Optional


# Forbidden patterns for bounded/offline mode (no pd.read_excel, openpyxl, literal paths)
# Path rules: only forbid string *literals* (e.g. "/Users/...") so list_all_workbooks() return values are allowed
_FORBIDDEN_PATTERNS_BOUNDED = [
    (r"pd\.read_excel\s*\(", "pd.read_excel is prohibited. Use list_all_workbooks() and read_table_multi() instead."),
    (r"(?:pd|pandas)\.read_csv\s*\(", "pd.read_csv is prohibited in bounded mode. Inputs are preloaded; use list_all_workbooks() + read_table_multi() instead."),
    (r"(?:pd|pandas)\.read_table\s*\(", "pd.read_table is prohibited in bounded mode. Inputs are preloaded; use list_all_workbooks() + read_table_multi() instead."),
    (r"pd\.ExcelFile\s*\(", "pd.ExcelFile is prohibited. Use list_all_workbooks() and read_table_multi() instead."),
    (r"from\s+sklearn\b", "sklearn is unavailable in runtime. Use numpy.linalg.lstsq for regression."),
    (r"import\s+sklearn\b", "sklearn is unavailable in runtime. Use numpy.linalg.lstsq for regression."),
    (r"from\s+statsmodels\b", "statsmodels is unavailable in runtime. Use numpy.linalg.lstsq for regression."),
    (r"import\s+statsmodels\b", "statsmodels is unavailable in runtime. Use numpy.linalg.lstsq for regression."),
    (r"\.to_excel\s*\(", "DataFrame.to_excel is prohibited. Use write_dataframe_to_sheet() and save_workbook_to(output_path)."),
    (r"\.to_csv\s*\(", "DataFrame.to_csv is prohibited. Write results with create_output_sheet() + write_dataframe_to_sheet() and save_workbook_to(output_path)."),
    (r"openpyxl", "openpyxl import/use is prohibited. Use helper functions only."),
    (r"load_workbook\s*\(", "load_workbook is prohibited. Use get_workbook() and read_table_multi() instead."),
    (r"['\"]/path/to/", "Placeholder input paths like /path/to/... are prohibited. Use all_files = list_all_workbooks()."),
    (r"all_files\s*=\s*\[", "DO NOT override all_files with literal list (e.g. all_files = [\"example.xlsx\"]). Use all_files = list_all_workbooks() only."),
    (r"with\s+open\s*\(", "File I/O with open() is prohibited. Use helper functions: write_dataframe_to_sheet() and save_workbook_to(output_path)."),
    (r"open\s*\([^)]*,\s*['\"]", "File I/O open() is prohibited. Use helper functions: write_dataframe_to_sheet() and save_workbook_to(output_path)."),
    (r"write_to_sheet\s*\(", "write_to_sheet() does not exist. Use write_dataframe_to_sheet(data, sheet_name, start_cell) instead."),
    (r"create_and_write_to_sheet\s*\(", "create_and_write_to_sheet() does not exist. Use create_output_sheet(sheet_name) then write_dataframe_to_sheet(data, sheet_name, start_cell)."),
    (r"from\s+common_functions\s+import", "Do not import common_functions. Helper functions are already injected into the runtime namespace."),
    (r"\binspector_multi\s*\(", "inspector_multi() is disabled in execution mode. Use read_table_multi(file_path, sheet_name, range_ref) only."),
    (r"\binspector\s*\(", "inspector() is disabled in execution mode. Use read_table_multi(file_path, sheet_name, range_ref) only."),
    (r"\bread_multiple_sheets\s*\(", "read_multiple_sheets() is disabled in execution mode. Use list_all_workbooks()+read_table_multi() only."),
    (r"\bget_sheet_as_dataframe\s*\(", "get_sheet_as_dataframe() is disabled in execution mode. Build DataFrame from read_table_multi() results."),
    (r"get_workbook\s*\(\s*None\s*\)", "get_workbook(None) is invalid. Pass a file path string from list_all_workbooks()."),
    (r"highlight_rows\s*\(\s*[^,]+,\s*\[\s*[^,\]]*\.index\.tolist\(\)\s*\]", "highlight_rows expects a flat list of ints. Do not wrap index.tolist() in an extra list."),
    (r"save_workbook_to\s*\(\s*['\"]", "Use save_workbook_to(output_path) only. Do not hard-code save paths."),
    (r"\bsave_workbook\s*\(", "save_workbook() is disabled in execution mode. Use save_workbook_to(output_path) only."),
    (r"\bwb\.save\s*\(", "Do not call wb.save(...). Use save_workbook_to(output_path) only."),
    (r"\bsheet\.cell\s*\(", "Direct worksheet cell writes are prohibited. Use write_dataframe_to_sheet(data_2d, \"Output\", \"A1\")."),
    (r"output_path\s*=\s*save_workbook_to\s*\(", "Do not reassign output_path. Use: saved_file = save_workbook_to(output_path), then return saved_file."),
    (r"['\"]/(?:Users|home|tmp|var|opt)/", "Hard-coded absolute paths are prohibited. Use list_all_workbooks() for inputs and save_workbook_to(output_path) for outputs."),
    (r"\.columns\.contains\s*\(", "pandas Index has no columns.contains(). Use `'col' in df.columns` or `df.columns.str.contains(...)`."),
    (r"(?:^|\n)\s*//", "C-style '//' comments are invalid in Python. Use '#' comments or remove comments."),
    (r"\.\.\.\s*\(previous code remains unchanged\)", "Do not submit partial patch placeholders. Return one full executable code block."),
    (r"previous code remains unchanged", "Do not rely on previous turn state. Return complete runnable code each turn."),
]


class CodeExecutor:
    """Executes generated Python code within the sandbox."""

    def __init__(self, sandbox):
        self.sandbox = sandbox

    @staticmethod
    def check_forbidden_bounded(code: str) -> Optional[str]:
        """Return error message if code contains forbidden patterns for bounded/offline mode."""
        if not code or not code.strip():
            return None
        for pattern, message in _FORBIDDEN_PATTERNS_BOUNDED:
            if re.search(pattern, code):
                return (
                    f"FORBIDDEN (bounded mode): {message} "
                    "Use list_all_workbooks(), get_workbook(), read_table_multi(), "
                    "create_output_sheet(), write_dataframe_to_sheet(), save_workbook_to(output_path)."
                )
        return None

    def execute(self, code: str) -> str:
        result = ""

        try:
            run_result = self.sandbox.run(code)
            stdout_output = run_result.get("stdout", "")
            stderr_output = run_result.get("stderr", "")

            if stdout_output:
                result += f"Output:\n{stdout_output}\n"

            if stderr_output:
                result += f"Errors/Warnings:\n{stderr_output}\n"

            if not result.strip():
                lines = code.strip().split('\n')
                if lines:
                    last_line = lines[-1].strip()
                    if last_line and not any(last_line.startswith(kw) for kw in [
                        'import ', 'from ', 'def ', 'class ', 'if ',
                        'for ', 'while ', 'try ', 'with ', 'print('
                    ]):
                        try:
                            last_result = eval(last_line,
                                               self.sandbox.code_globals,
                                               self.sandbox.code_locals)
                            if last_result is not None:
                                result = f"Expression result: {last_result}"
                        except Exception:
                            pass

            if not result.strip():
                result = "Code executed successfully (no output)"

        except Exception as e:
            result = f"Execution error: {str(e)}\nTraceback:\n{traceback.format_exc()}"

        if len(result) <= 10000:
            return result

        return result[:10000] + "\n⚠️ **[OUTPUT TRUNCATED]** ⚠️\n"
