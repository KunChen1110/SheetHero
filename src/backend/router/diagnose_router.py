"""Routing logic for whether to run the diagnose stage."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from ..log.logger_registry import LoggerRegistry
from ..prompt.prompt_builder import PromptBuilder

logger = LoggerRegistry.setup_logger(__name__)


@dataclass
class DiagnoseDecision:
    should_diagnose: bool
    reasons: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)


class DiagnoseRouter:
    """Decide whether the diagnose stage should run."""

    def __init__(self, client, deployment: str, progress_logger=None,
                 prompt_profile: str = "online_rich"):
        self.client = client
        self.deployment = deployment
        self.progress_logger = progress_logger
        self.prompt_builder = PromptBuilder(profile=prompt_profile)

    def decide(self, user_question: str, understanding_output: str,
               workbook_view) -> DiagnoseDecision:
        prompt = self.prompt_builder.build_diagnose_router_prompt(
            user_question=user_question,
            understanding_output=understanding_output
        )
        decision = self._ask_llm(prompt)
        should_diagnose = decision is True

        reasons = [f"llm:{'YES' if should_diagnose else 'NO'}"]
        if self.progress_logger:
            self.progress_logger.log(
                f"[ROUTER] Diagnose decision={should_diagnose} ({reasons[0]})",
                to_terminal=False
            )

        return DiagnoseDecision(
            should_diagnose=should_diagnose,
            reasons=reasons,
            issues=[],
        )

    def _ask_llm(self, prompt: str) -> Optional[bool]:
        messages = [{"role": "user", "content": prompt}]
        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=messages,
            )
            content = (response.choices[0].message.content or "").strip()
        except Exception as exc:
            logger.warning("Diagnose router LLM request failed: %s", exc)
            return None

        parsed = self._parse_yes_no(content)
        if parsed is None:
            logger.warning("Diagnose router invalid output: %r", content)
        return parsed

    @staticmethod
    def _parse_yes_no(text: str) -> Optional[bool]:
        upper = (text or "").strip().upper()
        if upper.startswith("YES"):
            return True
        if upper.startswith("NO"):
            return False
        return None
