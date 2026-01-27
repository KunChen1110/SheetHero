"""Python execution runner for isolated code execution."""

import io
import sys


class SandboxRunner:
    """Executes code in provided globals/locals dictionaries."""

    def __init__(self, timeout: float | None = None):
        self.timeout = timeout

    def run(self, code: str, globals_dict: dict, locals_dict: dict):
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        try:
            sys.stdout = stdout_capture
            sys.stderr = stderr_capture

            # ✅ 正确做法：直接在真实 globals / locals 中执行
            exec(code, globals_dict, locals_dict)

            return {
                "stdout": stdout_capture.getvalue(),
                "stderr": stderr_capture.getvalue(),
            }

        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
