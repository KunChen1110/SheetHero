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
        normalized_paths = [p for p in excel_paths if p]
        if self._agent is None or normalized_paths != self._excel_paths:
            self._agent = SheetHero(
                excel_paths=normalized_paths,
                config=self.config,
                load_excel=self.load_excel,
            )
            self._excel_paths = normalized_paths
            self._session = None

        if self._session is None:
            self._session = self._agent.start_session(prompt)
            response: Dict[str, object] = self._agent.step(self._session)
        else:
            if self._session.state == "qa":
                return {
                    "type": "clarification",
                    "message": "Session is awaiting clarification. Please call submit_clarification().",
                }
            if self._session.state == "done":
                self._reset_session(prompt)
                response = self._agent.step(self._session)
            else:
                self._reset_session(prompt)
                response = self._agent.step(self._session)

        return self._finalize_response(self._auto_step_until_blocked(response))

    def submit_clarification(self, user_reply: str) -> Dict[str, object]:
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

        response = self._agent.step(self._session, user_reply)
        return self._finalize_response(self._auto_step_until_blocked(response))

    def _reset_session(self, prompt: str) -> None:
        if self._session is None:
            return
        self._session.state = "init"
        self._session.result = None
        self._session.understanding = None
        self._session.original_query = prompt

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
        if response.get("type") == "final" and not response.get("message"):
            response["message"] = self._extract_message(response)
        return response

    @staticmethod
    def _extract_message(response: Dict[str, object]) -> str:
        result = response.get("result")
        if isinstance(result, dict):
            final_answer = result.get("final_answer")
            if final_answer is not None:
                return str(final_answer)
        return ""
