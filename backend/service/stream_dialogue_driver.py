"""Stream dialogue driver for SheetHero service."""

from __future__ import annotations

from typing import Dict, Iterator, Optional

from .sheethero_service import SheetHeroService


class StreamDialogueDriver:
    """Small adapter that switches between turn stream and clarification stream."""

    def __init__(self, service: SheetHeroService):
        self.service = service
        self._stream: Optional[Iterator[Dict[str, object]]] = None

    def start(self, prompt: str, excel_paths: list[str]):
        self._stream = self.service.stream_turn(prompt, excel_paths)
        return self._consume()

    def reply(self, user_reply: str):
        self._stream = self.service.stream_clarification(user_reply)
        return self._consume()

    def _consume(self):
        if self._stream is None:
            return
        for event in self._stream:
            yield event
            if event.get("type") in {"clarification", "final", "error"}:
                return
