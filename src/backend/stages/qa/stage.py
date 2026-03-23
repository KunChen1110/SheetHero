"""Quality assurance stage (LLM-assisted matching + cleaning action)."""

from copy import deepcopy
import re
from typing import Any, Dict, Optional

from ...prompt.prompt_builder import PromptBuilder
from ...log.logger_registry import LoggerRegistry

logger = LoggerRegistry.setup_logger(__name__)


class QualityAssuranceStage:
    """QA stage for multi-turn clarification."""

    def __init__(self, client, deployment: str, progress_logger=None,
                 prompt_profile: str = "online_rich"):
        self.client = client
        self.deployment = deployment
        self.progress_logger = progress_logger
        self.prompt_builder = PromptBuilder(profile=prompt_profile)
        self.quality_table = []
        self.original_question = ""
        self.unresolved_problems = []
        self.current_problem = None
        self.answers = []
        self.cleaning_actions = []
        self.interpretation_policies = []
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
        self.interpretation_policies = []
        self.qa_rounds = 0
        self.last_mismatch = ""

    def start(self, question_list: Optional[list], original_question: str) -> None:
        self.reset()
        self.quality_table = self._filter_format_questions(question_list or [])
        self.original_question = original_question
        self.unresolved_problems = []
        for idx, item in enumerate(self.quality_table):
            if isinstance(item, dict):
                problem = deepcopy(item)
                problem.setdefault("id", idx)
                problem.setdefault("description", self._problem_description(item))
                problem.setdefault("question", "")
                problem.setdefault("details_markdown", "")
            else:
                problem = {
                    "id": idx,
                    "description": self._problem_description(item),
                    "question": "",
                    "details_markdown": "",
                }
            self.unresolved_problems.append(problem)
        self._log_progress(
            f"[QA] Started with {len(self.unresolved_problems)} issue(s) to clarify."
        )

    def next_question_payload(self) -> Optional[Dict[str, str]]:
        if not self.unresolved_problems and self.current_problem is None:
            return None
        if self.qa_rounds >= self.max_qa_rounds:
            self._log_progress("[QA] Reached max QA rounds. Stopping questions.")
            self.current_problem = None
            return None

        if self.current_problem is None:
            self.current_problem = self.unresolved_problems.pop(0)
            self.qa_rounds += 1

        description = str(self.current_problem.get("description") or "").strip()
        direct_question = str(self.current_problem.get("question") or "").strip()
        details_markdown = str(self.current_problem.get("details_markdown") or "").strip()
        self._log_progress(f"[QA] Question about: {description}")

        if direct_question:
            return {
                "message": direct_question,
                "details_markdown": details_markdown,
            }

        prompt_text = self.prompt_builder.build_qa_question_prompt(
            self._format_quality_table(self.quality_table),
            description
        )
        messages = [{"role": "user", "content": prompt_text}]

        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=messages,
        )

        content = (response.choices[0].message.content or "").strip()
        question = content or "Please clarify your preferences for data cleaning."
        return {
            "message": self._ensure_qa_scope(question),
            "details_markdown": details_markdown,
        }

    def next_question(self) -> Optional[str]:
        payload = self.next_question_payload()
        if not payload:
            return None
        return payload.get("message")

    def consume_user_reply(self, reply: str) -> None:
        if self.current_problem is None:
            return
        matched, action, feedback = self._match_reply(self.current_problem, reply)
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
            "action": action or "NO_OP",
            "policy": self._build_interpretation_policy(self.current_problem, reply, action or "NO_OP"),
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
            policy = item.get("policy")
            if problem and action and action != "NO_OP":
                last_action[problem] = action
            if policy:
                self.interpretation_policies.append(str(policy))
        self.cleaning_actions = list(last_action.values())
        self._log_progress(
            f"[QA] actions={self._truncate(self.cleaning_actions)}"
        )
        if self.interpretation_policies:
            self._log_progress(
                f"[QA] policies={self._truncate(self.interpretation_policies)}"
            )

    def export_cleaning_actions(self) -> list:
        return self.cleaning_actions or []

    def clear_cleaning_actions(self) -> None:
        self.cleaning_actions = []
        self.interpretation_policies = []

    def export_interpretation_policies(self) -> list:
        return self.interpretation_policies or []

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

    @staticmethod
    def _normalize_reply(reply: str) -> str:
        return " ".join((reply or "").strip().lower().split())

    def _heuristic_match_reply(self, question: str, reply: str, problem: Optional[Dict[str, Any]] = None) -> Optional[tuple[bool, str, str]]:
        normalized_reply = self._normalize_reply(reply)
        normalized_question = self._normalize_reply(question)
        if not normalized_reply:
            return False, "", "Please answer the question directly."

        no_change_tokens = (
            "ignore",
            "keep",
            "keep as is",
            "keep as-is",
            "leave it as is",
            "leave as is",
            "leave blank",
            "do nothing",
            "no change",
            "as is",
            "as-is",
        )
        if any(token in normalized_reply for token in no_change_tokens):
            return True, "NO_OP", ""

        if "depends on" in normalized_question and (
            "root task" in normalized_reply
            or "root" in normalized_reply
            or "no prerequisite" in normalized_reply
            or "no dependency" in normalized_reply
            or "does not depend on" in normalized_reply
            or "doesn't depend on" in normalized_reply
            or "depend on no other" in normalized_reply
        ):
            return True, "NO_OP", ""

        issue_type = str((problem or {}).get("issue_type") or "")
        metadata = (problem or {}).get("metadata") or {}
        if issue_type == "missing_value":
            numeric_reply = (reply or "").strip().replace(",", "")
            numeric_reply = re.sub(r"^[£$€]\s*", "", numeric_reply)
            if re.fullmatch(r"[-+]?\d+(?:\.\d+)?", numeric_reply):
                sheet_key = str(metadata.get("sheet_key") or "current sheet")
                column_name = str(metadata.get("column") or "value")
                excel_row = metadata.get("excel_row")
                row_text = f" at Excel row {excel_row}" if excel_row else ""
                return (
                    True,
                    f"Fill the missing value in `{column_name}`{row_text} in `{sheet_key}` with {numeric_reply}.",
                    "",
                )

        return None

    def _build_interpretation_policy(self, problem: Dict[str, Any], reply: str, action: str) -> str:
        if action != "NO_OP":
            return ""
        normalized_reply = self._normalize_reply(reply)
        question_text = self._normalize_reply(
            str(problem.get("question") or problem.get("description") or "")
        )
        metadata = problem.get("metadata") or {}
        issue_type = str(problem.get("issue_type") or "")

        if issue_type == "missing_value" and "depends on" in question_text and (
            "root task" in normalized_reply
            or "root" in normalized_reply
            or "no prerequisite" in normalized_reply
            or "no dependency" in normalized_reply
            or "does not depend on" in normalized_reply
            or "doesn't depend on" in normalized_reply
            or "depend on no other" in normalized_reply
        ):
            sheet_key = str(metadata.get("sheet_key") or "current sheet")
            column_name = str(metadata.get("column") or "Depends on")
            excel_row = metadata.get("excel_row")
            row_text = f" at Excel row {excel_row}" if excel_row else ""
            return (
                f"Interpret blank `{column_name}`{row_text} in `{sheet_key}` as meaning the task is a root task "
                "with no prerequisite dependency."
            )
        return ""

    def _match_reply(self, question_or_problem: Any, reply: str) -> tuple[bool, str, str]:
        if isinstance(question_or_problem, dict):
            problem = question_or_problem
            question = str(problem.get("question") or problem.get("description") or "")
        else:
            problem = None
            question = str(question_or_problem or "")

        heuristic = self._heuristic_match_reply(question, reply, problem)
        if heuristic is not None:
            return heuristic

        prompt_text = self.prompt_builder.build_qa_match_prompt(question, reply)
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
            if isinstance(item, dict) and item.get("source") == "router_evidence":
                filtered.append(item)
                continue
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
