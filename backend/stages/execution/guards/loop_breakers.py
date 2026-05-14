"""Skill-based loop breaker providers."""

from ....skills import detect_skills, select_helper, build_loop_breaker


def get_task_specific_loop_breaker(user_question: str) -> str:
    breakers = []
    for skill in detect_skills(user_question):
        helper = select_helper(skill, user_question)
        if helper is None:
            continue
        breaker = build_loop_breaker(skill, helper)
        if breaker:
            breakers.append(breaker)
    return "\n\n".join(breakers)
