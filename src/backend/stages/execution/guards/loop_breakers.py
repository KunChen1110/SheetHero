"""Skill-based loop breaker providers."""

from ....skills import detect_skill, select_helper, build_loop_breaker


def get_task_specific_loop_breaker(user_question: str) -> str:
    skill = detect_skill(user_question)
    if skill is None:
        return ""
    helper = select_helper(skill, user_question)
    if helper is None:
        return ""
    return build_loop_breaker(skill, helper)
