"""Service layer for orchestrating SheetHero single-task sessions."""

from __future__ import annotations

from typing import Dict, Optional

from ..agent import SheetHero
from ..config.settings import Config
from ..agent.core.session import SheetHeroSession


class SheetHeroService:
    """Dialogue-level service: each user turn creates a new agent and reuses one session."""

    def __init__(self, config: Config, load_excel: bool = True) -> None:
        self.config = config
        self.load_excel = load_excel
        self._agent: Optional[SheetHero] = None
        self._session: Optional[SheetHeroSession] = None
        self._excel_paths: list[str] = []
        self._last_context_understanding: str = ""

    def submit_turn(
        self,
        prompt: str,
        excel_paths: list[str],
    ) -> Dict[str, object]:
        """
        Runs a single user turn:
        - creates a new agent
        - reuses a persisted session
        - auto-advances internal progress steps until blocked by clarification/final/error
        """
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

    def _reset_session(self, prompt: str) -> None:
        if self._session is None:
            return
        self._session.state = "init"
        self._session.result = None
        self._session.understanding = None
        self._session.original_query = prompt
        self._session.ui_thoughts.clear()
        self._session.ui_thought_cursor = 0

    def _prepare_turn(self, prompt: str, excel_paths: list[str]) -> Dict[str, object]:
        normalized_paths = [p for p in excel_paths if p]
        if self._agent is None or normalized_paths != self._excel_paths:
            self._cache_session_context()
            self._agent = SheetHero(
                excel_paths=normalized_paths,
                config=self.config,
                load_excel=self.load_excel,
            )
            self._excel_paths = normalized_paths
            self._session = None

        if self._session is None:
            self._session = self._agent.start_session(prompt)
            if self._last_context_understanding:
                self._session.context_understanding = self._last_context_understanding
            return self._agent.step(self._session)

        if self._session.state == "qa":
            return {
                "type": "clarification",
                "stage": "qa",
                "message": "Session is awaiting clarification. Please call submit_clarification().",
            }

        self._reset_session(prompt)
        return self._agent.step(self._session)

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
        self._cache_session_context()
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

    def _cache_session_context(self) -> None:
        if self._session is None:
            return
        context = (self._session.context_understanding or "").strip()
        if context:
            self._last_context_understanding = context

    @staticmethod
    def _extract_message(response: Dict[str, object]) -> str:
        result = response.get("result")
        if isinstance(result, dict):
            final_answer = result.get("final_answer")
            if final_answer is not None:
                return str(final_answer)
        return ""
