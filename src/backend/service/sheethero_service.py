"""Service layer for orchestrating SheetHero single-task sessions."""

from __future__ import annotations

from typing import Callable, Dict, Optional

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
        user_input_callback: Callable[[str], str],
    ) -> Dict[str, object]:
        """
        Runs a single user turn:
        - creates a new agent
        - reuses a persisted session
        - returns the response dict for this turn
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
            if self._session.state == "done":
                self._session.state = "init"
                self._session.result = None
                self._session.understanding = None
                self._session.original_query = prompt
                response = self._agent.step(self._session)
            else:
                response = self._agent.step(self._session, prompt)

        return response
