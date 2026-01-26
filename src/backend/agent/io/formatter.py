"""Output formatting utilities for SheetHero results."""

import os
import re
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


class OutputFormatter:
    """Formats SheetHero results for user-friendly output."""

    def format_user_mode(self, result: Dict[str, Any], excel_paths: list,
                         question: str, output_mode: str = "text") -> str:
        output_lines = []
        output_lines.append("================ SheetHero Result ================")

        output_lines.append("Question:")
        question_lines = question.split('\n')
        for q_line in question_lines:
            output_lines.append(f"  {q_line.strip()}")

        output_lines.append("\nInput files:")
        for path in excel_paths:
            try:
                rel_path = os.path.relpath(path)
                output_lines.append(f"  - {rel_path}")
            except ValueError:
                output_lines.append(f"  - {path}")

        status_text = "Success" if result['success'] else "Failed"
        output_lines.append(f"\nStatus:      {status_text}")
        output_lines.append(f"Confidence:  {result['confidence_score']:.2f}")
        output_lines.append(f"Iterations:  {result['total_iterations']}")
        output_lines.append(f"Duration:    {result['total_duration']:.2f}s")

        if output_mode == "file":
            answer_path = result.get('answer', '').strip()
            output_lines.append("\nResult:")
            if answer_path:
                output_lines.append(f"  Result file saved to: {answer_path}")
                verbose_log_path = result.get('verbose_log_path')
                if verbose_log_path:
                    output_lines.append(f"  Verbose log: {verbose_log_path}")
            else:
                output_lines.append("  Result file not saved or path not available")
        else:
            output_lines.append("\nAnswer:")
            answer = result.get('answer', '')

            answer_without_table, table_content = self.extract_table_from_answer(answer)

            if not table_content:
                table_content = self.extract_table_from_history(
                    result.get('conversation_history')
                )

            if not table_content:
                file_path = self._detect_file_path(answer)
                if file_path:
                    table_from_file = self.read_table_from_file(file_path)
                    if table_from_file:
                        table_content = table_from_file

            if table_content:
                if answer_without_table:
                    output_lines.append(answer_without_table)
                output_lines.append("\nTable:")
                output_lines.append(table_content)
            else:
                output_lines.append(answer)

        issues = result.get('issues_found')
        if issues:
            output_lines.append("\nIssues:")
            for issue in issues:
                output_lines.append(f"  - {issue}")

        improvement_feedback = result.get('improvement_feedback')
        if improvement_feedback:
            output_lines.append("\nFeedback:")
            output_lines.append(improvement_feedback)

        return "\n".join(output_lines)

    def extract_table_from_answer(self, answer: str) -> Tuple[str, Optional[str]]:
        lines = answer.split('\n')
        table_lines, table_indices = self._extract_first_table(lines)

        if table_lines:
            non_table_lines = [
                line for idx, line in enumerate(lines) if idx not in table_indices
            ]
            return '\n'.join(non_table_lines).strip(), '\n'.join(table_lines)

        return answer.strip(), None

    def extract_table_from_history(self,
                                   conversation_history: Optional[List[Dict[str, Any]]]
                                   ) -> Optional[str]:
        if not conversation_history:
            return None

        for message in reversed(conversation_history):
            if isinstance(message, dict):
                raw_content = message.get("content", "")
            else:
                raw_content = getattr(message, "content", "")

            _, table = self.extract_table_from_answer(self._content_to_text(raw_content))
            if table:
                return table

        return None

    def read_table_from_file(self, file_path: str) -> Optional[str]:
        if not file_path:
            return None

        resolved_path = os.path.abspath(os.path.expanduser(file_path))
        if not os.path.exists(resolved_path):
            return None

        _, ext = os.path.splitext(resolved_path)
        ext = ext.lower()

        try:
            if ext in {".xlsx", ".xls", ".xlsm", ".xltx", ".xltm"}:
                df = pd.read_excel(resolved_path)
            elif ext == ".csv":
                df = pd.read_csv(resolved_path)
            else:
                return None
        except Exception:
            return None

        if df.empty:
            return None

        return self._format_dataframe_to_markdown(df)

    @staticmethod
    def _is_table_line(line: str) -> bool:
        stripped = line.strip()
        return stripped.startswith("|") and stripped.count("|") >= 2

    @staticmethod
    def _content_to_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    parts.append(item.get("text", ""))
                else:
                    parts.append(str(item))
            return "\n".join(parts)
        return str(content) if content is not None else ""

    def _extract_first_table(self, lines: List[str]) -> Tuple[List[str], List[int]]:
        table_lines: List[str] = []
        table_indices: List[int] = []
        collecting = False

        for idx, line in enumerate(lines):
            if self._is_table_line(line):
                collecting = True
                table_lines.append(line)
                table_indices.append(idx)
            else:
                if collecting:
                    break

        return table_lines, table_indices

    @staticmethod
    def _format_dataframe_to_markdown(df: pd.DataFrame) -> str:
        columns = [str(col).strip() for col in df.columns]
        header = "| " + " | ".join(columns) + " |"
        separator = "| " + " | ".join(["-" * max(3, len(col) or 3) for col in columns]) + " |"
        rows = []
        for _, row in df.iterrows():
            cells = []
            for value in row:
                if pd.isna(value):
                    cells.append("")
                else:
                    cells.append(str(value).replace("\n", " ").strip())
            rows.append("| " + " | ".join(cells) + " |")
        return "\n".join([header, separator] + rows)

    @staticmethod
    def _detect_file_path(text: str) -> Optional[str]:
        if not text:
            return None

        matches = re.findall(
            r"([A-Za-z0-9_./\\-]+\.(?:xlsx|xls|xlsm|xltx|xltm|csv))",
            text
        )
        if matches:
            return matches[-1]

        stripped = text.strip()
        if stripped.endswith((".xlsx", ".xls", ".xlsm", ".xltx", ".xltm", ".csv")):
            return stripped

        return None
