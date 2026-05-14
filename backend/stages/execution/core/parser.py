"""Response parsing for execution outputs."""

import re
from typing import Optional, Tuple

from ...base.response_parser import BaseResponseParser


class ExecutionResponseParser(BaseResponseParser):
    """Parse assistant responses into thought, code, and final answers."""

    @staticmethod
    def _normalize_code_tail(code: str) -> str:
        lines = code.splitlines()
        while lines and not lines[-1].strip():
            lines.pop()
        if not lines:
            return code

        has_function_or_class_block = any(
            re.match(r"^\s*(def|class)\s+\w+", line)
            for line in lines
        )
        normalized_lines = []
        for line in lines:
            if not has_function_or_class_block and re.match(r"^\s*return\s+.+$", line):
                expr = re.sub(r"^\s*return\s+", "", line, count=1).rstrip()
                normalized_lines.append(expr)
                continue
            normalized_lines.append(line)
        return "\n".join(normalized_lines)

    @staticmethod
    def _looks_like_bare_code(content: str) -> bool:
        lines = [line.rstrip() for line in content.splitlines() if line.strip()]
        if not lines:
            return False

        code_like = re.compile(
            r"^\s*(#|import\s+\w+|from\s+\w+\s+import|tables\s*=|all_files\s*=|"
            r"create_output_sheet\s*\(|write_dataframe_to_sheet\s*\(|saved_file\s*=|"
            r"print\s*\(|for\s+\w+\s+in\s+|if\s+.+:|elif\s+.+:|else:|try:|except\b|"
            r"with\s+.+:|def\s+\w+\s*\(|[A-Za-z_]\w*\s*=)"
        )

        first_line = lines[0].strip()
        if not code_like.match(first_line):
            return False

        code_like_count = sum(1 for line in lines[:8] if code_like.match(line.strip()))
        return code_like_count >= max(2, min(len(lines), 3))

    @staticmethod
    def _strip_think_blocks(content: str) -> str:
        cleaned = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r"^\s*\w*<think>\s*", "", cleaned, flags=re.IGNORECASE)
        return cleaned.strip()

    def parse(self, content: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract thought and code from LLM response."""
        if not content:
            return None, None
        content = self._strip_think_blocks(content)

        begin_solution_match = re.search(
            r"BEGIN SOLUTION\s*(.*?)\s*END SOLUTION",
            content,
            re.DOTALL | re.IGNORECASE,
        )
        if begin_solution_match:
            code = self._normalize_code_tail(begin_solution_match.group(1).strip())
            if code:
                return None, code

        # Preferred: closed fenced code block (python/py/unspecified), case-insensitive.
        code_match = re.search(r"```(?:python|py)?\s*(.*?)\s*```", content, re.DOTALL | re.IGNORECASE)
        if code_match:
            code = self._normalize_code_tail(code_match.group(1).strip())
            if code:
                return None, code

        # Fallback: opening fence exists but closing fence may be truncated by the model.
        open_only_match = re.search(r"```(?:python|py)?\s*(.*)$", content, re.DOTALL | re.IGNORECASE)
        if open_only_match:
            code = self._normalize_code_tail(open_only_match.group(1).strip())
            if code:
                return None, code

        # Last resort for bounded mode style outputs: content may be plain code without fences.
        if self._looks_like_bare_code(content):
            return None, self._normalize_code_tail(content.strip())

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
