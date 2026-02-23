"""Prompt builder backed by dataclasses."""

from __future__ import annotations

from typing import Any, Dict, Optional, Literal

from .prompt_data import (ExecutionPrompts, UnderstandingPrompts, ValidationPrompts,
                          QAPrompts, DiagnosePrompts, CleaningPrompts, InteractPrompts)
from .prompt_texts_offline import (
    UNDERSTANDING_PROMPT_OFFLINE,
    _ENHANCED_UNDERSTANDING_PROMPT_OFFLINE,
    _QUALITY_DIAG_PROMPT_OFFLINE,
    _UNDERSTANDING_CONTEXT_MATCH_PROMPT_OFFLINE,
    _UNDERSTANDING_VERIFY_BEFORE_INFER_OFFLINE,
    _DIAGNOSE_CODE_PROMPT_OFFLINE,
    _DIAGNOSE_PROMPT_OFFLINE,
    _DIAGNOSE_PRIORITIZE_PROMPT_OFFLINE,
    _DIAGNOSE_ROUTER_PROMPT_OFFLINE,
    _QA_PROMPT_OFFLINE,
    _QA_QUESTION_PROMPT_OFFLINE,
    _QA_ACTIONS_PROMPT_OFFLINE,
    _QA_MATCH_PROMPT_OFFLINE,
    _QA_INSTRUCTION_PROMPT_OFFLINE,
    _QA_DECISION_PROMPT_OFFLINE,
    _EXECUTION_SYSTEM_INTRO_OFFLINE,
    _EXECUTION_HELPER_SECTIONS_PART1_OFFLINE,
    _EXECUTION_HELPER_SECTIONS_PART2_OFFLINE,
    _EXECUTION_USER_PROMPT_OFFLINE,
    _VALIDATION_PROMPT_OFFLINE,
)

PromptProfile = Literal["offline_strict", "online_rich"]


class PromptBuilder:
    """Builds prompts from templates and placeholder values."""

    _default_understanding = UnderstandingPrompts()
    _default_execution = ExecutionPrompts()
    _default_validation = ValidationPrompts()
    _default_qa = QAPrompts()
    _default_diagnose = DiagnosePrompts()
    _default_cleaning = CleaningPrompts()
    _default_interact = InteractPrompts()

    def __init__(self,
                 profile: PromptProfile = "offline_strict",
                 understanding: Optional[UnderstandingPrompts] = None,
                 execution: Optional[ExecutionPrompts] = None,
                 validation: Optional[ValidationPrompts] = None,
                 qa: Optional[QAPrompts] = None,
                 diagnose: Optional[DiagnosePrompts] = None,
                 cleaning: Optional[CleaningPrompts] = None,
                 interact: Optional[InteractPrompts] = None):
        self.profile = profile

        if profile == "offline_strict":
            self._understanding = understanding or UnderstandingPrompts(
                prompt=UNDERSTANDING_PROMPT_OFFLINE,
                verify_before_infer_offline=_UNDERSTANDING_VERIFY_BEFORE_INFER_OFFLINE,
                enhanced_prompt=_ENHANCED_UNDERSTANDING_PROMPT_OFFLINE,
                quality_prompt=_QUALITY_DIAG_PROMPT_OFFLINE,
                diagnose_code_prompt=_DIAGNOSE_CODE_PROMPT_OFFLINE,
                context_match_prompt=_UNDERSTANDING_CONTEXT_MATCH_PROMPT_OFFLINE,
            )
            self._execution = execution or ExecutionPrompts(
                system_intro=_EXECUTION_SYSTEM_INTRO_OFFLINE,
                helper_sections_part1=_EXECUTION_HELPER_SECTIONS_PART1_OFFLINE,
                helper_sections_part1_offline=_EXECUTION_HELPER_SECTIONS_PART1_OFFLINE,
                helper_sections_part2=_EXECUTION_HELPER_SECTIONS_PART2_OFFLINE,
                user_prompt=_EXECUTION_USER_PROMPT_OFFLINE,
            )
            self._validation = validation or ValidationPrompts(
                prompt=_VALIDATION_PROMPT_OFFLINE
            )
            self._qa = qa or QAPrompts(
                prompt=_QA_PROMPT_OFFLINE,
                question_prompt=_QA_QUESTION_PROMPT_OFFLINE,
                actions_prompt=_QA_ACTIONS_PROMPT_OFFLINE,
                match_prompt=_QA_MATCH_PROMPT_OFFLINE,
                instruction_prompt=_QA_INSTRUCTION_PROMPT_OFFLINE,
                decision_prompt=_QA_DECISION_PROMPT_OFFLINE,
            )
            self._diagnose = diagnose or DiagnosePrompts(
                prompt=_DIAGNOSE_PROMPT_OFFLINE,
                code_prompt=_DIAGNOSE_CODE_PROMPT_OFFLINE,
                prioritize_prompt=_DIAGNOSE_PRIORITIZE_PROMPT_OFFLINE,
                router_prompt=_DIAGNOSE_ROUTER_PROMPT_OFFLINE,
            )
        else:
            self._understanding = understanding or self._default_understanding
            self._execution = execution or self._default_execution
            self._validation = validation or self._default_validation
            self._qa = qa or self._default_qa
            self._diagnose = diagnose or self._default_diagnose

        self._cleaning = cleaning or self._default_cleaning
        self._interact = interact or self._default_interact

    def _render(self, template: str, values: Dict[str, Any]) -> str:
        result = template
        for key, value in values.items():
            token = f"<<{key}>>"
            result = result.replace(token, "" if value is None else str(value))
        return result

    def build_understanding_prompt(self, user_question: str,
                                   excel_context_understanding: str,
                                   session_context_understanding: str = "") -> str:
        template = self._understanding.prompt
        return self._render(template, {
            "user_question": user_question,
            "excel_context_understanding": excel_context_understanding,
            "session_context_understanding": session_context_understanding
        })

    def build_quality_diagnosis_prompt(self, excel_context_understanding: str) -> str:
        template = self._understanding.quality_prompt
        return self._render(template, {
            "excel_context_understanding": excel_context_understanding
        })

    def build_understanding_context_match_prompt(self, user_question: str,
                                                 session_context_understanding: str) -> str:
        template = self._understanding.context_match_prompt
        return self._render(template, {
            "user_question": user_question,
            "session_context_understanding": session_context_understanding
        })

    def build_diagnose_code_prompt(self, schema_summary: str, user_task: str) -> str:
        return self._render(self._diagnose.code_prompt, {
            "schema_summary": schema_summary
            ,
            "user_task": user_task
        })

    def build_diagnose_prompt(self, user_task: str, scan_report: str) -> str:
        return self._render(self._diagnose.prompt, {
            "user_task": user_task,
            "scan_report": scan_report,
        })

    def build_diagnose_prioritize_prompt(self, user_task: str,
                                         questions: list[str]) -> str:
        candidates = "\n".join(f"{idx}. {question}" for idx, question in enumerate(questions, start=1))
        if not candidates:
            candidates = "(none)"
        return self._render(self._diagnose.prioritize_prompt, {
            "user_task": user_task,
            "candidate_questions": candidates,
        })

    def build_diagnose_router_prompt(self, user_question: str,
                                     understanding_output: str) -> str:
        return self._render(self._diagnose.router_prompt, {
            "user_question": user_question,
            "understanding_output": understanding_output
        })

    def build_cleaning_code_prompt(self, schema_summary: str, actions: list[str]) -> str:
        actions_text = "\n".join(f"- {item}" for item in actions) if actions else "(none)"
        return self._render(self._cleaning.code_prompt, {
            "schema_summary": schema_summary,
            "actions": actions_text
        })

    def build_qa_prompt(self, quality_table: str,
                        original_question: str,
                        user_reply: Optional[str]) -> str:
        template = self._qa.prompt
        return self._render(template, {
            "quality_table": quality_table,
            "original_question": original_question,
            "user_reply": user_reply or ""
        })

    def build_qa_question_prompt(self, quality_table: str,
                                 current_problem: str) -> str:
        template = self._qa.question_prompt
        return self._render(template, {
            "quality_table": quality_table,
            "current_problem": current_problem
        })

    def build_qa_decision_prompt(self, quality_table: str,
                                 original_question: str,
                                 answers_summary: str) -> str:
        template = self._qa.decision_prompt
        return self._render(template, {
            "quality_table": quality_table,
            "original_question": original_question,
            "answers_summary": answers_summary
        })

    def build_qa_actions_prompt(self, quality_table: str,
                                answers_summary: str) -> str:
        template = self._qa.actions_prompt
        return self._render(template, {
            "quality_table": quality_table,
            "answers_summary": answers_summary
        })

    def build_qa_match_prompt(self, question: str, reply: str) -> str:
        template = self._qa.match_prompt
        return self._render(template, {
            "question": question,
            "reply": reply
        })

    def build_qa_instruction_prompt(self, problem: str, reply: str) -> str:
        template = self._qa.instruction_prompt
        return self._render(template, {
            "problem": problem,
            "reply": reply
        })

    def build_interact_needs_spreadsheet_prompt(self, user_message: str) -> str:
        return self._render(self._interact.needs_spreadsheet_prompt, {
            "user_message": user_message
        })

    def build_interact_context_match_prompt(self, user_message: str,
                                            context_understanding: str) -> str:
        return self._render(self._interact.context_match_prompt, {
            "user_message": user_message,
            "context_understanding": context_understanding
        })

    def build_interact_context_summary_prompt(self, user_message: str) -> str:
        return self._render(self._interact.context_summary_prompt, {
            "user_message": user_message
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

    def build_execution_system_prompt(
        self,
        output_instruction: str,
        use_bounded_execution: bool = False
    ) -> str:
        system_intro = self._execution.system_intro
        helper_part1 = (
            self._execution.helper_sections_part1_offline
            if use_bounded_execution
            else self._execution.helper_sections_part1
        )
        helper_parts = [helper_part1]
        if not use_bounded_execution:
            helper_parts.append(self._execution.helper_sections_part2)

        system_parts = [system_intro]
        if output_instruction:
            system_parts.append(
                f"\n**OUTPUT REQUIREMENTS:**\n{output_instruction}\n"
            )
        system_parts.append("\n\n".join(helper_parts))
        return "".join(system_parts)

    def build_execution_user_prompt(self, execution_context: str,
                                    understanding_output: str,
                                    user_query: str) -> str:
        template = self._execution.user_prompt
        return self._render(template, {
            "execution_context": execution_context,
            "understanding_output": understanding_output,
            "user_query": user_query
        })

    def build_validation_prompt(self, user_query: str,
                                excel_context_understanding: str,
                                execution_context: str,
                                execution_success: bool,
                                total_turns: int,
                                final_answer: str,
                                execution_summary: Dict[str, Any],
                                conversation_history_text: str) -> str:
        template = self._validation.prompt
        return self._render(template, {
            "user_query": user_query,
            "excel_context_understanding": excel_context_understanding,
            "execution_context": execution_context,
            "execution_success": execution_success,
            "total_turns": total_turns,
            "final_answer": final_answer,
            "total_code_executions": execution_summary.get("total_code_executions", 0),
            "successful_executions": execution_summary.get("successful_executions", 0),
            "failed_executions": execution_summary.get("failed_executions", 0),
            "conversation_history_text": conversation_history_text,
        })
