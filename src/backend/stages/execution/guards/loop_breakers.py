"""Task-family loop-breaker templates for execution repair prompts."""

from __future__ import annotations

from ....task_families import detect_task_family


def get_task_specific_loop_breaker(user_question: str) -> str:
    family = detect_task_family(user_question)
    if family is None:
        return ""
    return family.loop_breaker or ""
