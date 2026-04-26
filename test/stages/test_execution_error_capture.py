import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from backend.environment.sandbox.runner import SandboxRunner
from backend.stages.execution.core.executor import CodeExecutor


class _SandboxStub:
    def __init__(self):
        self.code_globals = {}
        self.code_locals = self.code_globals
        self.runner = SandboxRunner()

    def run(self, code: str):
        return self.runner.run(code, self.code_globals, self.code_locals)


def test_code_executor_keeps_stdout_when_execution_errors():
    sandbox = _SandboxStub()
    executor = CodeExecutor(sandbox)

    result = executor.execute(
        "print('share columns:', ['Year', 'Vivo'])\nraise KeyError('Time')"
    )

    assert "Output:\nshare columns:" in result
    assert "Execution error: 'Time'" in result
    assert "Traceback:" in result
