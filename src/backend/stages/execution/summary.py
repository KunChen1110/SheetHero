"""Execution summary construction."""

from typing import Optional


class ExecutionSummary:
    """Builds summary information for execution steps."""

    @staticmethod
    def build(execution_steps: list, final_answer: Optional[str]) -> dict:
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
