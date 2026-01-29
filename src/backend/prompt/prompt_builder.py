"""Prompt builder backed by dataclasses."""

from __future__ import annotations

from typing import Any, Dict, Optional

from .prompt_data import ExecutionPrompts, UnderstandingPrompts, ValidationPrompts


class PromptBuilder:
    """Builds prompts from templates and placeholder values."""

    _default_understanding = UnderstandingPrompts()
    _default_execution = ExecutionPrompts()
    _default_validation = ValidationPrompts()

    def __init__(self,
                 understanding: Optional[UnderstandingPrompts] = None,
                 execution: Optional[ExecutionPrompts] = None,
                 validation: Optional[ValidationPrompts] = None):
        self._understanding = understanding or self._default_understanding
        self._execution = execution or self._default_execution
        self._validation = validation or self._default_validation

    def _render(self, template: str, values: Dict[str, Any]) -> str:
        result = template
        for key, value in values.items():
            token = f"<<{key}>>"
            result = result.replace(token, "" if value is None else str(value))
        return result

    def build_understanding_prompt(self, user_question: str,
                                   excel_context_understanding: str) -> str:
        template = self._understanding.prompt
        return self._render(template, {
            "user_question": user_question,
            "excel_context_understanding": excel_context_understanding
        })

    def build_enhanced_understanding_prompt(self, understanding_output: str,
                                            last_validation: Dict[str, Any]) -> str:
        template = self._understanding.enhanced_prompt
        issues = "; ".join(last_validation.get("issues_found", []))
        return self._render(template, {
            "understanding_output": understanding_output,
            "improvement_feedback": last_validation.get("improvement_feedback", ""),
            "issues_to_address": issues,
        })

    def build_execution_system_prompt(self, output_instruction: str) -> str:
        system_intro = self._execution.system_intro
        helper_parts = [
            self._execution.helper_sections_part1,
            self._execution.helper_sections_part2,
        ]

        system_parts = [system_intro]
        if output_instruction:
            system_parts.append(
                f"\n**OUTPUT REQUIREMENTS:**\n{output_instruction}\n"
            )
        system_parts.append("\n\n".join(helper_parts))
        return "".join(system_parts)

    def build_execution_user_prompt(self, excel_context_execution: str,
                                    understanding_output: str,
                                    user_question: str) -> str:
        template = self._execution.user_prompt
        return self._render(template, {
            "excel_context_execution": excel_context_execution,
            "understanding_output": understanding_output,
            "user_question": user_question
        })

    def build_validation_prompt(self, user_question: str,
                                excel_context_understanding: str,
                                execution_success: bool,
                                total_turns: int,
                                final_answer: str,
                                execution_summary: Dict[str, Any],
                                conversation_history_text: str) -> str:
        template = self._validation.prompt
        return self._render(template, {
            "user_question": user_question,
            "excel_context_understanding": excel_context_understanding,
            "execution_success": execution_success,
            "total_turns": total_turns,
            "final_answer": final_answer,
            "total_code_executions": execution_summary.get("total_code_executions", 0),
            "successful_executions": execution_summary.get("successful_executions", 0),
            "failed_executions": execution_summary.get("failed_executions", 0),
            "conversation_history_text": conversation_history_text,
        })
