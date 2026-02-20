"""Quality assurance stage (LLM-assisted matching + cleaning action)."""

from typing import Any, Optional

from ...prompt.prompt_builder import PromptBuilder
from ...log.logger_registry import LoggerRegistry

logger = LoggerRegistry.setup_logger(__name__)


class QualityAssuranceStage:
    """QA stage for multi-turn clarification."""

    def __init__(self, client, deployment: str, progress_logger=None):
        self.client = client
        self.deployment = deployment
        self.progress_logger = progress_logger
        self.quality_table = []
        self.original_question = ""
        self.unresolved_problems = []
        self.current_problem = None
        self.answers = []
        self.cleaning_actions = []
        self.max_qa_rounds = 30
        self.qa_rounds = 0
        self.last_mismatch = ""

    def reset(self) -> None:
        """Reset all QA runtime state for a fresh clarification flow."""
        self.quality_table = []
        self.original_question = ""
        self.unresolved_problems = []
        self.current_problem = None
        self.answers = []
        self.cleaning_actions = []
        self.qa_rounds = 0
        self.last_mismatch = ""

    def start(self, question_list: Optional[list], original_question: str) -> None:
        self.reset()
        self.quality_table = self._filter_format_questions(question_list or [])
        self.original_question = original_question
        self.unresolved_problems = [
            {"id": idx, "description": self._problem_description(item)}
            for idx, item in enumerate(self.quality_table)
        ]
        self._log_progress(
            f"[QA] Started with {len(self.unresolved_problems)} issue(s) to clarify."
        )

    def next_question(self) -> Optional[str]:
        if not self.unresolved_problems:
            return None
        if self.qa_rounds >= self.max_qa_rounds:
            self._log_progress("[QA] Reached max QA rounds. Stopping questions.")
            self.current_problem = None
            return None

        if self.current_problem is None:
            self.current_problem = self.unresolved_problems.pop(0)
            self.qa_rounds += 1

        self._log_progress(
            f"[QA] Question about: {self.current_problem.get('description')}"
        )
        prompt_text = PromptBuilder().build_qa_question_prompt(
            self._format_quality_table(self.quality_table),
            self.current_problem.get("description", str(self.current_problem))
        )
        messages = [{"role": "user", "content": prompt_text}]

        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=messages,
        )

        content = (response.choices[0].message.content or "").strip()
        question = content or "Please clarify your preferences for data cleaning."
        return self._ensure_qa_scope(question)

    def consume_user_reply(self, reply: str) -> None:
        if self.current_problem is None:
            return
        matched, action, feedback = self._match_reply(
            self.current_problem.get("description"),
            reply
        )
        if not matched:
            self.last_mismatch = feedback or "Please answer the question directly."
            self.qa_rounds += 1
            self._log_progress(f"[QA] Reply mismatch: {self.last_mismatch}")
            return

        self.last_mismatch = ""
        self.answers.append({
            "problem_id": self.current_problem.get("id"),
            "problem": self.current_problem.get("description"),
            "reply": reply,
            "action": action or "NO_OP"
        })
        self._log_progress(
            f"[QA] Reply received for: {self.current_problem.get('description')}"
        )
        self.current_problem = None

    def finalize_decision(self) -> None:
        last_action = {}
        for item in self.answers:
            problem = item.get("problem")
            action = item.get("action")
            if problem and action and action != "NO_OP":
                last_action[problem] = action
        self.cleaning_actions = list(last_action.values())
        self._log_progress(
            f"[QA] actions={self._truncate(self.cleaning_actions)}"
        )

    def export_cleaning_actions(self) -> list:
        return self.cleaning_actions or []

    def clear_cleaning_actions(self) -> None:
        self.cleaning_actions = []

    def get_last_mismatch(self) -> str:
        return self.last_mismatch

    def clear_last_mismatch(self) -> None:
        self.last_mismatch = ""


    @staticmethod
    def _format_quality_table(quality_table: list) -> str:
        if not quality_table:
            return "(none)"
        lines = []
        for item in quality_table:
            desc = item.get("description") if isinstance(item, dict) else str(item)
            lines.append(f"- {desc}")
        return "\n".join(lines)

    @staticmethod
    def _problem_description(problem: Any) -> str:
        if isinstance(problem, dict):
            return problem.get("description", str(problem))
        return str(problem)

    def _match_reply(self, question: str, reply: str) -> tuple[bool, str, str]:
        prompt_text = PromptBuilder().build_qa_match_prompt(question, reply)
        messages = [{"role": "user", "content": prompt_text}]
        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=messages,
            )
            content = response.choices[0].message.content or ""
        except Exception:
            return False, "", "Unable to verify reply."

        match, action = self._parse_match_action(content)
        feedback = "" if match else "Please answer the question directly."
        return match, action, feedback

    @staticmethod
    def _parse_match_action(content: str) -> tuple[bool, str]:
        match = False
        action = ""
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            upper = line.upper()
            if upper.startswith("MATCH:") or upper.startswith("MATCH ="):
                parts = line.split(":", 1) if ":" in line else line.split("=", 1)
                if len(parts) == 2:
                    value = parts[1].strip().upper()
                    match = value == "YES"
            if upper.startswith("ACTION:") or upper.startswith("ACTION ="):
                parts = line.split(":", 1) if ":" in line else line.split("=", 1)
                if len(parts) == 2:
                    action = parts[1].strip()
        if match and action.lower() in {"", "none", "no_op", "no action", "ignore", "keep", "keep as-is", "as-is"}:
            action = "NO_OP"
        return match, action

    def _ensure_qa_scope(self, question: str) -> str:
        original = str(self.current_problem.get("description", "")).strip()
        if not original:
            return question
        original_lower = original.lower()
        question_lower = question.lower()
        forbidden = {"drop", "remove", "delete", "discard", "ignore"}
        if not any(term in original_lower for term in forbidden):
            if any(term in question_lower for term in forbidden):
                return original
        if ("format" in original_lower or "standard" in original_lower or "normalize" in original_lower):
            if any(term in question_lower for term in {"drop", "remove", "keep", "ignore"}):
                return original
        return question

    @staticmethod
    def _filter_format_questions(question_list: list) -> list:
        if not question_list:
            return []
        keywords = {"time", "times", "day", "days", "date", "dates"}
        email_keywords = {"email", "e-mail"}
        email_format_terms = {
            "format", "casing", "case", "separator", "token", "whitespace", "spacing", "trim"
        }
        filtered = []
        for item in question_list:
            if isinstance(item, dict):
                description = str(item.get("description", "")).strip()
            else:
                description = str(item).strip()
            desc_lower = description.lower()
            if "format" in desc_lower and "inconsist" in desc_lower:
                if any(keyword in desc_lower for keyword in keywords):
                    continue
            if any(keyword in desc_lower for keyword in email_keywords):
                if any(term in desc_lower for term in email_format_terms):
                    continue
            filtered.append(item)
        return filtered

    def _log_progress(self, message: str) -> None:
        if self.progress_logger is None:
            logger.info(message)
            return
        self.progress_logger.log(message, to_terminal=False)

    @staticmethod
    def _truncate(value: Any, limit: int = 300) -> str:
        text = str(value)
        if len(text) <= limit:
            return text
        return text[:limit] + "..."
