"""Data models for skills and helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class HelperSpec:
    """One concrete helper function available within a skill."""
    name: str
    self_loading: bool = False
    description: str = ""
    sub_detector: Optional[Callable[[str], bool]] = None


@dataclass(frozen=True)
class SkillSpec:
    """Abstract spreadsheet operation skill.

    Attributes:
        name:         Short identifier (e.g. "merge", "aggregate").
        detector:     Keyword-based function that returns True when the skill matches.
        helpers:      Ordered tuple of helpers; first sub_detector match wins.
        output_mode:  "workbook" (default) or "text" (scan-type skills).
        strategy_doc: Injected into LLM prompts to guide task execution.
    """
    name: str
    detector: Callable[[str], bool]
    helpers: tuple[HelperSpec, ...]
    output_mode: str = "workbook"
    strategy_doc: str = ""
