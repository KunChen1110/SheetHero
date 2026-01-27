"""Dataclasses for prompt templates."""

from __future__ import annotations

from dataclasses import dataclass
from .prompt_texts import (_UNDERSTANDING_PROMPT, 
                           _ENHANCED_UNDERSTANDING_PROMPT,
                           _EXECUTION_HELPER_SECTIONS_PART1,
                           _EXECUTION_SYSTEM_INTRO,
                           _EXECUTION_HELPER_SECTIONS_PART2,
                           _EXECUTION_USER_PROMPT,
                           _VALIDATION_PROMPT,
                           _EXECUTION_USER_PROMPT)


@dataclass(frozen=True)
class UnderstandingPrompts:
    prompt: str = _UNDERSTANDING_PROMPT
    enhanced_prompt: str = _ENHANCED_UNDERSTANDING_PROMPT


@dataclass(frozen=True)
class ExecutionPrompts:
    system_intro: str = _EXECUTION_SYSTEM_INTRO
    helper_sections_part1: str = _EXECUTION_HELPER_SECTIONS_PART1
    helper_sections_part2: str = _EXECUTION_HELPER_SECTIONS_PART2
    user_prompt: str = _EXECUTION_USER_PROMPT


@dataclass(frozen=True)
class ValidationPrompts:
    prompt: str = _VALIDATION_PROMPT


