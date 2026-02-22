"""Response parsing for execution outputs."""

import re
from typing import Optional, Tuple

from ..base.response_parser import BaseResponseParser


class ExecutionResponseParser(BaseResponseParser):
    """Parse assistant responses into thought, code, and final answers."""

    def parse(self, content: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract thought and code from LLM response."""
        if not content:
            return None, None

        # Preferred: closed fenced code block (python/py/unspecified), case-insensitive.
        code_match = re.search(r"```(?:python|py)?\s*(.*?)\s*```", content, re.DOTALL | re.IGNORECASE)
        if code_match:
            code = code_match.group(1).strip()
            if code:
                return None, code

        # Fallback: opening fence exists but closing fence may be truncated by the model.
        open_only_match = re.search(r"```(?:python|py)?\s*(.*)$", content, re.DOTALL | re.IGNORECASE)
        if open_only_match:
            code = open_only_match.group(1).strip()
            if code:
                return None, code

        # Last resort for bounded mode style outputs: content may be plain code without fences.
        if re.search(r"^\s*(import\s+\w+|from\s+\w+\s+import|all_files\s*=|create_output_sheet\s*\()", content):
            return None, content.strip()

        if "Final Answer:" in content:
            return content.strip(), None

        return content.strip(), None

    @staticmethod
    def extract_final_answer(thought: str) -> Optional[str]:
        """Extract final answer from thought. Returns None if result looks like template/markdown."""
        if not thought:
            return None
        if "Final Answer:" not in thought:
            return None
        # Prefer first line after "Final Answer:" to avoid pulling in code blocks
        final_answer_match = re.search(r"Final Answer:\s*(.+?)(?:\n|$)", thought, re.DOTALL)
        if final_answer_match:
            raw = final_answer_match.group(1).strip()
        else:
            raw = thought.replace("Final Answer:", "").strip()
        # Strip backticks and take first line only
        raw = raw.split("\n")[0].strip().strip("`").strip()
        # Reject template/markdown garbage so downstream does not treat it as file path
        if not raw:
            return None
        reject_substrings = ("```", "python", "B) One line", "Final Answer:", "your answer here")
        if any(s in raw for s in reject_substrings):
            return None
        # Reject placeholder paths (e.g. /path/to/saved/file or <path>)
        raw_lower = raw.lower()
        if "/path/to" in raw_lower or "path/to" in raw_lower or "<path" in raw_lower:
            return None
        return raw
