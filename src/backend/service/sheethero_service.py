"""Service layer for orchestrating SheetHero single-task sessions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from ..agent import SheetHero
from ..config.settings import Config
from ..agent.core.session import SheetHeroSession


@dataclass
class DialogueMemory:
    """Cross-session memory for dialogue continuity."""

    last_context_understanding: str = ""
    last_workbooks: Optional[Dict[str, Any]] = None


class SheetHeroService:
    """Dialogue-level service: each new user task creates a new session."""

    def __init__(self, config: Config, load_excel: bool = True) -> None:
        self.config = config
        self.load_excel = load_excel
        self._agent: Optional[SheetHero] = None
        self._session: Optional[SheetHeroSession] = None
        self._memory = DialogueMemory()

    def submit_turn(self, prompt: str, excel_paths: list[str]) -> Dict[str, object]:
        # Clarification must continue via submit_clarification().
        if self._session is not None and self._session.state == "qa":
            return {
                "type": "clarification",
                "stage": "qa",
                "message": "Session is awaiting clarification. Please call submit_clarification().",
            }
        response = self._prepare_turn(prompt, excel_paths)
        return self._finalize_response(self._auto_step_until_blocked(response))

    def submit_clarification(self, user_reply: str) -> Dict[str, object]:
        response = self._prepare_clarification(user_reply)
        return self._finalize_response(self._auto_step_until_blocked(response))

    def _prepare_clarification(self, user_reply: str) -> Dict[str, object]:
        if self._agent is None or self._session is None:
            return {
                "type": "error",
                "message": "No active session for clarification.",
            }
        if self._session.state != "qa":
            return {
                "type": "error",
                "message": "Session is not awaiting clarification.",
            }
        return self._agent.step(self._session, user_reply)

    def _prepare_turn(self, prompt: str, excel_paths: list[str]) -> Dict[str, object]:
        incoming_paths = self._resolve_excel_paths(excel_paths)

        # Cache prior session memory before switching task/session.
        self._cache_session_memory()

        # Build a new agent for each new task turn.
        self._agent = SheetHero(
            excel_paths=incoming_paths,
            config=self.config,
            load_excel=self.load_excel,
        )

        # New task -> always create a new session.
        self._session = self._agent.start_session(prompt)
        self._restore_session_memory(session=self._session)
        return self._agent.step(self._session)

    def _resolve_excel_paths(self, excel_paths: list[str]) -> list[str]:
        """Normalize current-turn workbook paths.

        Note: no_excel means no files provided in this turn.
        We intentionally do not back-fill from history here.
        """
        return [p for p in (excel_paths or []) if p]

    def _auto_step_until_blocked(
        self,
        response: Dict[str, object],
        max_auto_steps: int = 50,
    ) -> Dict[str, object]:
        if self._agent is None or self._session is None:
            return {"type": "error", "message": "Agent session not initialized."}

        for _ in range(max_auto_steps):
            response_type = response.get("type")
            if response_type == "progress":
                response = self._agent.step(self._session)
                continue
            return response

        return {
            "type": "error",
            "message": "Exceeded internal turn limit.",
        }

    def _finalize_response(self, response: Dict[str, object]) -> Dict[str, object]:
        if self._session:
            new_thoughts = self._session.ui_thoughts[self._session.ui_thought_cursor:]
            self._session.ui_thought_cursor = len(self._session.ui_thoughts)
            if new_thoughts:
                response["ui_thoughts"] = new_thoughts
        if response.get("type") == "final" and not response.get("message"):
            response["message"] = self._extract_message(response)
        self._cache_session_memory()
        return response

    def _auto_step_stream(
        self,
        initial_response: Dict[str, object],
        max_auto_steps: int = 50,
    ):
        response = initial_response
        for _ in range(max_auto_steps):
            yield self._finalize_response(response)
            if response.get("type") != "progress":
                return
            if self._agent is None or self._session is None:
                yield self._finalize_response(
                    {"type": "error", "message": "Agent session not initialized."}
                )
                return
            response = self._agent.step(self._session)
        yield self._finalize_response(
            {"type": "error", "message": "Exceeded internal turn limit."}
        )

    def stream_turn(self, prompt: str, excel_paths: list[str]):
        initial = self._prepare_turn(prompt, excel_paths)
        yield from self._auto_step_stream(initial)

    def stream_clarification(self, user_reply: str):
        initial = self._prepare_clarification(user_reply)
        yield from self._auto_step_stream(initial)

    def _cache_session_memory(self) -> None:
        if self._session is None:
            return
        context = (self._session.context_understanding or "").strip()
        if context:
            self._memory.last_context_understanding = context
        active = self._session.get_active_workbooks()
        if active:
            self._memory.last_workbooks = active

    def _restore_session_memory(self, session: SheetHeroSession) -> None:
        if self._memory.last_context_understanding:
            session.context_understanding = self._memory.last_context_understanding
        session.previous_workbooks = self._memory.last_workbooks

    @staticmethod
    def _extract_message(response: Dict[str, object]) -> str:
        result = response.get("result")
        if isinstance(result, dict):
            final_answer = result.get("final_answer")
            if final_answer is not None:
                return str(final_answer)
        return ""
