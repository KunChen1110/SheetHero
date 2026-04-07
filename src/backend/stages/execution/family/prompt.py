"""Skill-based execution prompt augmentation helpers."""

from typing import TYPE_CHECKING

from ....task_skills import (
    detect_skill, select_helper,
    build_execution_strict_rules, build_loop_breaker,
)

if TYPE_CHECKING:
    from ..runtime import ExecutionRuntime


class ExecutionFamilyPromptAdvisor:
    """Own skill-based execution prompt augmentation."""

    def __init__(self, runtime: "ExecutionRuntime"):
        self.runtime = runtime

    def augment_initial_prompt(self, user_content: str, user_question: str) -> str:
        runtime = self.runtime
        basenames = runtime._available_workbook_basenames()
        if basenames:
            file_lines = "\n".join(f"- `{name}`" for name in basenames)
            user_content += (
                "\n\n**AVAILABLE INPUT FILES (STRICT):**\n"
                f"{file_lines}\n"
                "Use ONLY these names for input lookups."
            )
        schema_snapshot = runtime._build_schema_snapshot()
        if schema_snapshot:
            user_content += (
                "\n\n**SCHEMA SNAPSHOT (RUNTIME, TRUST THIS):**\n"
                f"{schema_snapshot}\n"
                "Use these real headers for all select/merge operations. Do not invent columns."
            )

        skill = detect_skill(user_question)
        if skill is not None:
            helper = select_helper(skill, user_question)
            if helper is not None:
                user_content += build_execution_strict_rules(skill, helper)
                user_content += build_loop_breaker(skill, helper)
                observed_headers = sorted(runtime._observed_header_set())
                grounded_hint = runtime.question_inference.build_family_grounded_call_hint(
                    skill.name,
                    user_question,
                    observed_headers,
                )
                if grounded_hint:
                    user_content += (
                        "\n\n**GROUNDED HELPER HINT (USE REAL HEADERS):**\n"
                        f"- Observed headers: {', '.join(f'`{header}`' for header in observed_headers[:20])}\n"
                        f"- Preferred grounded helper call:\n  `{grounded_hint}`\n"
                        "- Prefer this grounded call over invented column names.\n"
                    )

        return user_content
