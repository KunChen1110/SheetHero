"""Skill-based execution prompt augmentation helpers."""

from typing import TYPE_CHECKING

from ....skills import (
    detect_skill, select_helper,
    build_execution_strict_rules, build_loop_breaker, build_skill_hint,
    build_compact_skill_workflow,
    build_fallback_strategy,
)

if TYPE_CHECKING:
    from ..runtime import ExecutionRuntime


class ExecutionSkillPromptAdvisor:
    """Own skill-based execution prompt augmentation."""

    def __init__(self, runtime: "ExecutionRuntime"):
        self.runtime = runtime

    def augment_initial_prompt(self, user_content: str, user_question: str) -> str:
        runtime = self.runtime
        basenames = runtime._available_workbook_basenames()
        schema_snapshot = runtime._build_schema_snapshot()
        is_offline_strict = bool(getattr(runtime, "_is_offline_strict", False))
        if basenames and not (is_offline_strict and schema_snapshot):
            file_lines = "\n".join(f"- `{name}`" for name in basenames)
            user_content += (
                "\n\n**AVAILABLE INPUT FILES (STRICT):**\n"
                f"{file_lines}\n"
                "Use ONLY these names for input lookups."
            )
        if schema_snapshot:
            user_content += (
                "\n\n**SCHEMA SNAPSHOT (RUNTIME, TRUST THIS):**\n"
                f"{schema_snapshot}\n"
                "Use these real headers for all select/merge operations. Do not invent columns."
            )

        skill = detect_skill(user_question)
        if skill:
            helper = select_helper(skill, user_question)
            if helper is not None:
                observed_headers = sorted(runtime._observed_header_set())
                plan_summary = ""
                try:
                    plan = runtime.question_inference.infer_runtime_plan(
                        skill.name,
                        helper.name,
                        user_question,
                        observed_headers,
                    )
                except Exception:
                    plan = None
                if plan is not None:
                    plan_summary = plan.to_prompt_summary()
                workflow_doc = (
                    build_compact_skill_workflow(skill, helper)
                    if is_offline_strict
                    else build_skill_hint(skill, helper)
                )
                user_content += (
                    f"\n\n**PRIMARY SKILL WORKFLOW [{skill.name.upper()}]:**\n"
                    f"{workflow_doc}"
                )
                user_content += build_execution_strict_rules(
                    skill,
                    helper,
                    plan_summary=plan_summary,
                )
                user_content += build_loop_breaker(
                    skill,
                    helper,
                    plan_summary=plan_summary,
                )
        else:
            # No skill matched — inject signal-aware fallback so the LLM always
            # gets schema grounding rules and relevant computation hints.
            user_content += f"\n\n{build_fallback_strategy(user_question)}"

        return user_content
