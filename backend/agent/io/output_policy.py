"""Output preference helpers for SheetHero."""

import os
from typing import Dict, Optional


class OutputPolicy:
    """Normalizes user preferences for output delivery."""

    @staticmethod
    def build_preferences(mode: str = "text",
                          file_path: Optional[str] = None) -> Dict[str, Optional[str]]:
        normalized_mode = (mode or "text").strip().lower()
        if normalized_mode not in {"text", "file"}:
            raise ValueError("output mode must be 'text' or 'file'")

        if normalized_mode == "file":
            normalized_path = file_path or os.path.join(
                os.getcwd(), "sheethero_output.xlsx"
            )
        else:
            normalized_path = None

        return {
            "mode": normalized_mode,
            "file_path": os.path.abspath(normalized_path) if normalized_path else None
        }

    @classmethod
    def output_mode(cls, mode: str = "text",
                    file_path: Optional[str] = None) -> Dict[str, Optional[str]]:
        return cls.build_preferences(mode, file_path)
