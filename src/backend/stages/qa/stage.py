"""Quality assurance stage (LLM-assisted matching + cleaning action)."""

from typing import Any, Optional, Dict, List

from ...prompt.prompt_builder import PromptBuilder
from ...log.logger_registry import LoggerRegistry

logger = LoggerRegistry.setup_logger(__name__)


class QualityAssuranceStage:
    """QA stage for multi-turn clarification."""

    def __init__(self, client, deployment: str, progress_logger=None):
        self.client = client
        self.deployment = deployment
        self.progress_logger = progress_logger
        self.quality_table: List[Dict[str, Any]] = []
        self.original_question = ""
        self.unresolved_indices: List[int] = []  # Indices of quality_table entries still pending
        self.current_index: Optional[int] = None  # Currently active index in quality_table
        self.cleaning_actions: List[str] = []
        self.max_qa_rounds = 30
        self.qa_rounds = 0
        self.last_mismatch = ""

    def start(self, question_list: Optional[list], original_question: str) -> None:
        self.quality_table = []
        self.original_question = original_question
        self.unresolved_indices = []
        self.current_index = None
        self.cleaning_actions = []
        self.qa_rounds = 0

        # Build unified quality_table with all fields initialized
        filtered_list = self._filter_format_questions(question_list or [])
        for idx, item in enumerate(filtered_list):
            problem_desc = self._problem_description(item)
            entry = {
                "id": idx,
                "description": problem_desc,
                "question_asked": None,      # Will be set when question is generated
                "reply": None,               # Will be set when user replies
                "selected_option": None,     # NEW: A, B, C, D
                "action": None,              # Will be set when reply is matched
                "status": "pending",         # "pending", "asked", "resolved", "failed"
                "mismatch_feedback": None,    # Store feedback if reply doesn't match
                "other_specification": None  # NEW: Store user's free-form specification when D is selected
            }
            self.quality_table.append(entry)
            self.unresolved_indices.append(idx)

        self._log_progress(
            f"[QA] Started with {len(self.quality_table)} issue(s) to clarify."
        )

    def next_question(self) -> Optional[str]:
        if not self.unresolved_indices:
            return None
        if self.qa_rounds >= self.max_qa_rounds:
            self._log_progress("[QA] Reached max QA rounds. Stopping questions.")
            self.current_index = None
            return None

        # Pop the next pending index
        self.current_index = self.unresolved_indices.pop(0)
        self.qa_rounds += 1

        current_entry = self.quality_table[self.current_index]
        problem_desc = current_entry.get("description", "")

        # Check if this entry needs clarification for "Other" option
        if current_entry.get("status") == "needs_clarification":
            self._log_progress(f"[QA] Asking for clarification on 'Other' for: {problem_desc}")
            # Return a follow-up question
            return f"You selected 'Other' for: {problem_desc}. Please describe what you'd like to do:"

        self._log_progress(f"[QA] Question about: {problem_desc}")

        prompt_text = PromptBuilder().build_qa_question_prompt(
            self._format_quality_table(self.quality_table),
            problem_desc
        )
        messages = [{"role": "user", "content": prompt_text}]

        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=messages,
        )

        content = (response.choices[0].message.content or "").strip()
        question = content or "Please clarify your preferences for data cleaning."
        question = self._ensure_qa_scope(question)

        # SAVE THE QUESTION in the unified table
        current_entry["question_asked"] = question
        current_entry["status"] = "asked"

        return question

    def consume_user_reply(self, reply: str) -> None:
        if self.current_index is None:
            return

        current_entry = self.quality_table[self.current_index]
        problem_desc = current_entry.get("description", "")

        # Check if we're handling a follow-up to "Other" option
        if current_entry.get("status") == "needs_clarification":
            # This is the user's free-form specification
            current_entry["other_specification"] = reply

            # Convert to action using LLM
            action = self._convert_other_to_action(problem_desc, reply)

            self.last_mismatch = ""
            current_entry["reply"] = reply
            current_entry["action"] = action or "NO_OP"
            current_entry["status"] = "resolved"
            current_entry["mismatch_feedback"] = None

            self._log_progress(
                f"[QA] Resolved (Other): '{problem_desc}' | "
                f"Specification: {self._truncate(reply)} | "
                f"Action: {current_entry['action']}"
            )
            self.current_index = None
            return

        # Normal flow: match reply to A/B/C/D options
        matched, selected_option, action, feedback = self._match_reply(
            current_entry.get("question_asked", ""),
            reply
        )

        if not matched:
            self.last_mismatch = feedback or "Please answer with A, B, C, D (or 1, 2, 3, 4), or describe what you want."
            current_entry["mismatch_feedback"] = self.last_mismatch
            current_entry["reply"] = reply
            current_entry["status"] = "failed"

            # Put back at front of queue for retry
            self.unresolved_indices.insert(0, self.current_index)
            self.qa_rounds += 1

            self._log_progress(f"[QA] Reply mismatch for '{problem_desc}': {self.last_mismatch}")
            self.current_index = None
            return

        # Handle "Other" option - need follow-up clarification
        if selected_option == "D" or action == "ASK_CLARIFICATION":
            self.last_mismatch = "You selected 'Other'. Please describe what you'd like to do."
            current_entry["selected_option"] = "D"
            current_entry["reply"] = reply
            current_entry["status"] = "needs_clarification"  # New status
            current_entry["mismatch_feedback"] = self.last_mismatch

            # Keep in queue but mark as needing more info
            self.unresolved_indices.insert(0, self.current_index)
            self.qa_rounds += 1

            self._log_progress(f"[QA] 'Other' selected for '{problem_desc}', awaiting clarification")
            self.current_index = None
            return

        # SUCCESS: Store reply, selected option, and action
        self.last_mismatch = ""
        current_entry["reply"] = reply
        current_entry["selected_option"] = selected_option  # A, B, C, or D
        current_entry["action"] = action or "NO_OP"
        current_entry["status"] = "resolved"
        current_entry["mismatch_feedback"] = None

        self._log_progress(
            f"[QA] Resolved: '{problem_desc}' | "
            f"Option: {selected_option} | "
            f"Q: {self._truncate(current_entry.get('question_asked', ''))} | "
            f"A: {self._truncate(reply)} | "
            f"Action: {current_entry['action']}"
        )
        self.current_index = None


    def _convert_other_to_action(self, problem: str, specification: str) -> str:
        """Convert user's free-form 'Other' specification into a cleaning action."""
        prompt_text = PromptBuilder().build_qa_instruction_prompt(problem, specification)
        messages = [{"role": "user", "content": prompt_text}]

        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=messages,
            )
            content = response.choices[0].message.content or ""
            # Extract action from response (should be one sentence)
            action = content.strip()
            return action if action else "NO_OP"
        except Exception as e:
            logger.warning(f"Error converting 'Other' to action: {type(e).__name__}: {e}")
            return "NO_OP"

    def finalize_decision(self) -> None:
        """Extract cleaning actions from resolved entries."""
        last_action = {}
        for entry in self.quality_table:
            if entry.get("status") == "resolved":
                problem = entry.get("description")
                action = entry.get("action")
                if problem and action and action != "NO_OP":
                    last_action[problem] = action

        self.cleaning_actions = list(last_action.values())
        resolved_count = sum(1 for e in self.quality_table if e.get("status") == "resolved")

        self._log_progress(
            f"[QA] Finalized: {resolved_count}/{len(self.quality_table)} resolved | "
            f"actions={self._truncate(self.cleaning_actions)}"
        )

    def export_cleaning_actions(self) -> list:
        return self.cleaning_actions or []

    def clear_cleaning_actions(self) -> None:
        self.cleaning_actions = []

    def get_last_mismatch(self) -> str:
        return self.last_mismatch

    def clear_last_mismatch(self) -> None:
        self.last_mismatch = ""

    def get_quality_table(self) -> list:
        """Return the complete quality table with all Q&A history."""
        return self.quality_table

    @staticmethod
    def _format_quality_table(quality_table: list) -> str:
        if not quality_table:
            return "(none)"
        lines = []
        for entry in quality_table:
            desc = entry.get("description", "")
            status = entry.get("status", "pending")
            q = entry.get("question_asked")
            a = entry.get("reply")
            opt = entry.get("selected_option", "")

            line = f"- {desc} [{status}]"
            if opt:
                line += f" [Option {opt}]"
            if q and a:
                line += f" (Q: {q[:50]}... A: {a[:30]}...)"
            elif q:
                line += f" (Q: {q[:50]}...)"
            lines.append(line)
        return "\n".join(lines)

    @staticmethod
    def _problem_description(problem: Any) -> str:
        if isinstance(problem, dict):
            return problem.get("description", str(problem))
        return str(problem)

    def _match_reply(self, questions: str, reply: str) -> tuple[bool, str, str, str]:
        """Returns: (matched, selected_option, action, feedback)"""
        prompt_text = PromptBuilder().build_qa_match_prompt(questions, reply)
        messages = [{"role": "user", "content": prompt_text}]
        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=messages,
            )
            content = response.choices[0].message.content or ""
        except Exception as e:
            logger.warning(f"Error in _match_reply: {type(e).__name__}: {e}")
            return False, "", "", "Unable to verify reply."

        match, selected_option, action = self._parse_match_option_action(content)
        feedback = "" if match else "Please answer with A, B, C (or 1, 2, 3)."
        return match, selected_option, action, feedback

    @staticmethod
    def _parse_match_option_action(content: str) -> tuple[bool, str, str]:
        """Parse MATCH, OPTION, and ACTION from LLM response."""
        match = False
        selected_option = ""
        action = ""

        for line in content.splitlines():
            line = line.strip()
            if line.upper().startswith("MATCH:"):
                value = line.split(":", 1)[1].strip().upper()
                match = value == "YES"
            elif line.upper().startswith("OPTION:"):
                selected_option = line.split(":", 1)[1].strip().upper()
                # Normalize 1/2/3/4 to A/B/C/D
                if selected_option in {"1", "A"}:
                    selected_option = "A"
                elif selected_option in {"2", "B"}:
                    selected_option = "B"
                elif selected_option in {"3", "C"}:
                    selected_option = "C"
                elif selected_option in {"4", "D"}:
                    selected_option = "D"
                elif selected_option in {"NONE", "NULL", ""}:
                    selected_option = ""
            elif line.upper().startswith("ACTION:"):
                action = line.split(":", 1)[1].strip()

        # Normalize NO_OP variations
        if match and action.lower() in {"", "none", "no_op", "no action", "ignore", "keep", "keep as-is", "as-is"}:
            action = "NO_OP"

        # Handle ASK_CLARIFICATION for option D
        if match and selected_option == "D" and "ASK_CLARIFICATION" not in action.upper():
            action = "ASK_CLARIFICATION"

        return match, selected_option, action

    def _ensure_qa_scope(self, question: str) -> str:
        if self.current_index is None:
            return question

        original = str(self.quality_table[self.current_index].get("description", "")).strip()
        if not original:
            return question

        original_lower = original.lower()
        question_lower = question.lower()
        forbidden = {"drop", "remove", "delete", "discard", "ignore"}

        if not any(term in original_lower for term in forbidden):
            if any(term in question_lower for term in forbidden):
                return original

        if "format" in original_lower or "standard" in original_lower or "normalize" in original_lower:
            if any(term in question_lower for term in {"drop", "remove", "keep", "ignore"}):
                return original

        return question

    @staticmethod
    def _filter_format_questions(question_list: list) -> list:
        """Filter out low-priority or redundant questions, but keep important ones."""
        if not question_list:
            return []

        # Only filter out specific patterns that are truly redundant
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

            # Only filter email formatting questions (these are usually cosmetic)
            if any(keyword in desc_lower for keyword in email_keywords):
                if any(term in desc_lower for term in email_format_terms):
                    continue  # Skip email formatting issues

            # Keep everything else including date/time format questions
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