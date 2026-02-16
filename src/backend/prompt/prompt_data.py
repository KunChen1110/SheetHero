"""Dataclasses for prompt templates."""

from __future__ import annotations

from dataclasses import dataclass
from .prompt_texts import (_UNDERSTANDING_PROMPT,
                           _QUALITY_DIAG_PROMPT,
                           _UNDERSTANDING_CONTEXT_MATCH_PROMPT,
                           _DIAGNOSE_CODE_PROMPT,
                           _DIAGNOSE_PROMPT,
                           _DIAGNOSE_PRIORITIZE_PROMPT,
                           _DIAGNOSE_ROUTER_PROMPT,
                           _ENHANCED_UNDERSTANDING_PROMPT,
                           _EXECUTION_HELPER_SECTIONS_PART1,
                           _EXECUTION_SYSTEM_INTRO,
                           _EXECUTION_HELPER_SECTIONS_PART2,
                           _EXECUTION_USER_PROMPT,
                           _QA_PROMPT,
                           _QA_QUESTION_PROMPT,
                           _QA_ACTIONS_PROMPT,
                           _QA_MATCH_PROMPT,
                           _QA_INSTRUCTION_PROMPT,
                           _QA_DECISION_PROMPT,
                           _VALIDATION_PROMPT,
                           _EXECUTION_USER_PROMPT,
                           _CLEANING_CODE_PROMPT,
                           _INTERACT_NEEDS_SPREADSHEET_PROMPT,
                           _INTERACT_CONTEXT_MATCH_PROMPT,
                           _INTERACT_CONTEXT_SUMMARY_PROMPT)


@dataclass(frozen=True)
class UnderstandingPrompts:
    prompt: str = _UNDERSTANDING_PROMPT
    enhanced_prompt: str = _ENHANCED_UNDERSTANDING_PROMPT
    quality_prompt: str = _QUALITY_DIAG_PROMPT
    diagnose_code_prompt: str = _DIAGNOSE_CODE_PROMPT
    context_match_prompt: str = _UNDERSTANDING_CONTEXT_MATCH_PROMPT


@dataclass(frozen=True)
class DiagnosePrompts:
    prompt: str = _DIAGNOSE_PROMPT
    code_prompt: str = _DIAGNOSE_CODE_PROMPT
    prioritize_prompt: str = _DIAGNOSE_PRIORITIZE_PROMPT
    router_prompt: str = _DIAGNOSE_ROUTER_PROMPT


@dataclass(frozen=True)
class QAPrompts:
    prompt: str = _QA_PROMPT
    question_prompt: str = _QA_QUESTION_PROMPT
    actions_prompt: str = _QA_ACTIONS_PROMPT
    match_prompt: str = _QA_MATCH_PROMPT
    instruction_prompt: str = _QA_INSTRUCTION_PROMPT
    decision_prompt: str = _QA_DECISION_PROMPT


@dataclass(frozen=True)
class ExecutionPrompts:
    system_intro: str = _EXECUTION_SYSTEM_INTRO
    helper_sections_part1: str = _EXECUTION_HELPER_SECTIONS_PART1
    helper_sections_part2: str = _EXECUTION_HELPER_SECTIONS_PART2
    user_prompt: str = _EXECUTION_USER_PROMPT


@dataclass(frozen=True)
class ValidationPrompts:
    prompt: str = _VALIDATION_PROMPT


@dataclass(frozen=True)
class CleaningPrompts:
    code_prompt: str = _CLEANING_CODE_PROMPT


@dataclass(frozen=True)
class InteractPrompts:
    needs_spreadsheet_prompt: str = _INTERACT_NEEDS_SPREADSHEET_PROMPT
    context_match_prompt: str = _INTERACT_CONTEXT_MATCH_PROMPT
    context_summary_prompt: str = _INTERACT_CONTEXT_SUMMARY_PROMPT
