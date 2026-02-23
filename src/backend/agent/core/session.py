"""Session state for multi-turn SheetHero interactions."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import uuid


@dataclass
class SheetHeroSession:
    """State container persisted across step() calls."""

    original_query: str
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state: str = "init"

    # temporary understanding from the agent
    understanding: Optional[str] = None
    spreadsheet_summary: Optional[str] = None

    # understanding of context (stable)
    context_understanding: Optional[str] = None

    # workbooks
    current_workbooks: Optional[Dict[str, Any]] = None
    previous_workbooks: Optional[Dict[str, Any]] = None
    result: Optional[Any] = None

    # Used for UI display
    ui_thoughts: list[dict] = field(default_factory=list)
    ui_thought_cursor: int = 0
    pending_execution_result: Optional[Dict[str, Any]] = None
    pending_execution_context: Optional[str] = None
