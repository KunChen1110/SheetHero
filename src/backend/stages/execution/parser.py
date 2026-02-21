"""Response parsing for execution outputs."""

import re
from typing import Optional, Tuple

from ..base.response_parser import BaseResponseParser


class ExecutionResponseParser(BaseResponseParser):
    """Parse assistant responses into thought, code, and final answers."""

    def parse(self, content: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract thought and code from LLM response."""
        code_match = re.search(r"```python\s*(.*?)\s*```", content, re.DOTALL)
        if code_match:
            code = code_match.group(1).strip()
            return None, code

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
