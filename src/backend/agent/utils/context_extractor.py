"""Utilities for extracting stable context snippets from model outputs."""

from __future__ import annotations

import re


class ContextExtractor:
    """Helper methods for extracting structured context from free-form text."""

    @staticmethod
    def extract_workbook_purpose_domain(understanding_output: str) -> str:
        if not understanding_output:
            return ""
        text = understanding_output.strip()

        # Preferred parse: capture the "Workbook Purpose & Domain" block across lines.
        block_pattern = re.compile(
            r"\*\*Workbook\s+Purpose\s*&\s*Domain\*\*\s*[:：]\s*"
            r"(?P<body>.*?)(?:\n\s*\n|\n\s*[-*]?\s*\*\*|\Z)",
            re.IGNORECASE | re.DOTALL,
        )
        block_match = block_pattern.search(text)
        if block_match:
            body = (block_match.group("body") or "").strip()
            if body:
                first_non_empty = next((ln.strip() for ln in body.splitlines() if ln.strip()), "")
                if first_non_empty:
                    return first_non_empty

        # Fallback: line-by-line tolerant extraction.
        lines = text.splitlines()
        inline_pattern = re.compile(
            r"\*\*Workbook\s+Purpose\s*&\s*Domain\*\*\s*[:：]\s*(.+)",
            re.IGNORECASE,
        )
        header_pattern = re.compile(
            r"\*\*Workbook\s+Purpose\s*&\s*Domain\*\*\s*[:：]\s*$",
            re.IGNORECASE,
        )
        for idx, raw_line in enumerate(lines):
            line = raw_line.strip()
            inline_match = inline_pattern.search(line)
            if inline_match:
                value = inline_match.group(1).strip()
                if value:
                    return value
            if header_pattern.search(line):
                for next_line in lines[idx + 1:]:
                    candidate = next_line.strip()
                    if not candidate:
                        continue
                    if candidate.startswith("**") or candidate.startswith("- **"):
                        break
                    return candidate
        return ""
