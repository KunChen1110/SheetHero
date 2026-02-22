
from dataclasses import dataclass
from typing import Optional, Dict, Any

@dataclass
class DialogueMemory:
    """Cross-session memory for dialogue continuity."""

    last_context_understanding: str = ""
    last_workbooks: Optional[Dict[str, Any]] = None