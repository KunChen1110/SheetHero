"""Python code execution for the sandboxed environment."""

import traceback


class CodeExecutor:
    """Executes generated Python code within the sandbox."""

    def __init__(self, sandbox):
        self.sandbox = sandbox

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

            # 尝试显示最后一个表达式的结果（从 locals 中取）
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

