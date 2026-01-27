"""Response parsing for execution outputs."""

import re
from typing import Optional, Tuple

from ..base.response_parser import BaseResponseParser


class ExecutionResponseParser(BaseResponseParser):
    """Parse assistant responses into thought, code, and final answers."""

    def parse(self, content: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract thought and code from LLM response."""
        if "Final Answer:" in content:
            return content.strip(), None

        code_match = re.search(r"```python\s*(.*?)\s*```", content, re.DOTALL)
        if code_match:
            code = code_match.group(1).strip()
            return None, code

        return content.strip(), None

    @staticmethod
    def extract_final_answer(thought: str) -> Optional[str]:
        if not thought:
            return None
        if "Final Answer:" in thought:
            final_answer_match = re.search(r"Final Answer:\s*(.*?)$", thought, re.DOTALL)
            if final_answer_match:
                return final_answer_match.group(1).strip()
            return thought.replace("Final Answer:", "").strip()
        return None
