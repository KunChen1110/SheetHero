"""Python execution runner for isolated code execution."""

import io
import sys
import traceback


class SandboxExecutionError(Exception):
    """Carry partial stdout/stderr when exec() fails."""

    def __init__(self, original_exc: Exception, stdout: str, stderr: str, traceback_text: str):
        super().__init__(str(original_exc))
        self.original_exc = original_exc
        self.stdout = stdout
        self.stderr = stderr
        self.traceback_text = traceback_text


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

            # Execute directly in the provided globals/locals namespaces.
            exec(code, globals_dict, locals_dict)

            return {
                "stdout": stdout_capture.getvalue(),
                "stderr": stderr_capture.getvalue(),
            }
        except Exception as exc:
            raise SandboxExecutionError(
                original_exc=exc,
                stdout=stdout_capture.getvalue(),
                stderr=stderr_capture.getvalue(),
                traceback_text=traceback.format_exc(),
            ) from exc

        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
