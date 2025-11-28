"""
Output formatting utilities for SheetBrain results.
Provides user-friendly and verbose output modes.
"""
import os
import re
from typing import Dict, Any, Tuple, Optional, List

import pandas as pd


def _is_table_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.count("|") >= 2


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


def _extract_first_table(lines: List[str]) -> Tuple[List[str], List[int]]:
    table_lines: List[str] = []
    table_indices: List[int] = []
    collecting = False

    for idx, line in enumerate(lines):
        if _is_table_line(line):
            collecting = True
            table_lines.append(line)
            table_indices.append(idx)
        else:
            if collecting:
                break

    return table_lines, table_indices


def extract_table_from_answer(answer: str) -> Tuple[str, Optional[str]]:
    """
    Extract markdown table from answer if present.
    
    Args:
        answer: The answer string that may contain markdown tables.
    
    Returns:
        Tuple of (answer_without_table, table_content)
        - answer_without_table: Answer text without the table
        - table_content: Extracted table content, or None if no table found
    """
    lines = answer.split('\n')
    table_lines, table_indices = _extract_first_table(lines)

    if table_lines:
        non_table_lines = [
            line for idx, line in enumerate(lines) if idx not in table_indices
        ]
        return '\n'.join(non_table_lines).strip(), '\n'.join(table_lines)

    return answer.strip(), None


def extract_table_from_history(conversation_history: Optional[List[Dict[str, Any]]]) -> Optional[str]:
    """
    Search conversation history for the most recent markdown table.
    """
    if not conversation_history:
        return None

    for message in reversed(conversation_history):
        if isinstance(message, dict):
            raw_content = message.get("content", "")
        else:
            raw_content = getattr(message, "content", "")

        _, table = extract_table_from_answer(_content_to_text(raw_content))
        if table:
            return table

    return None


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


def read_table_from_file(file_path: str) -> Optional[str]:
    """
    Read tabular data from a spreadsheet/CSV file and convert it to markdown.
    """
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

    return _format_dataframe_to_markdown(df)


def _detect_file_path(text: str) -> Optional[str]:
    if not text:
        return None

    matches = re.findall(r"([A-Za-z0-9_./\\-]+\.(?:xlsx|xls|xlsm|xltx|xltm|csv))", text)
    if matches:
        return matches[-1]

    stripped = text.strip()
    if stripped.endswith((".xlsx", ".xls", ".xlsm", ".xltx", ".xltm", ".csv")):
        return stripped

    return None


def format_output_user_mode(result: Dict[str, Any], excel_paths: list, question: str, output_mode: str = "text") -> str:
    """
    Format output in user-friendly mode (default, concise).
    
    Args:
        result: Dictionary containing analysis results
        excel_paths: List of input file paths
        question: User's question
    
    Returns:
        Formatted output string
    """
    output_lines = []
    output_lines.append("================ SheetBrain Result ================")
    
    # Question
    output_lines.append("Question:")
    # Wrap long questions
    question_lines = question.split('\n')
    for q_line in question_lines:
        output_lines.append(f"  {q_line.strip()}")
    
    # Input files
    output_lines.append("\nInput files:")
    for path in excel_paths:
        # Show relative path if possible
        try:
            rel_path = os.path.relpath(path)
            output_lines.append(f"  - {rel_path}")
        except ValueError:
            output_lines.append(f"  - {path}")
    
    # Status and metrics
    status_emoji = "✅ Success" if result['success'] else "❌ Failed"
    output_lines.append(f"\nStatus:      {status_emoji}")
    output_lines.append(f"Confidence:  {result['confidence_score']:.2f}")
    output_lines.append(f"Iterations:  {result['total_iterations']}")
    output_lines.append(f"Duration:    {result['total_duration']:.2f}s")
    
    if output_mode == "file":
        answer_path = result.get('answer', '').strip()
        output_lines.append("\nResult:")
        if answer_path:
            output_lines.append(f"  Result file saved to: {answer_path}")
        else:
            output_lines.append("  Result file saved successfully.")
    else:
        # Extract and display table if present
        answer = result['answer']
        answer_without_table, table_content = extract_table_from_answer(answer)

        if not table_content:
            table_content = extract_table_from_history(result.get('conversation_history'))

        if not table_content:
            file_path = _detect_file_path(answer_without_table) or _detect_file_path(answer)
            if file_path:
                table_from_file = read_table_from_file(file_path)
                if table_from_file:
                    table_content = table_from_file
                    answer_without_table = ""

        if table_content:
            output_lines.append("\nResult table:")
            output_lines.append(table_content)
        elif answer_without_table:
            # If no table, show answer (truncated if too long)
            answer_preview = answer_without_table[:200] + "..." if len(answer_without_table) > 200 else answer_without_table
            output_lines.append(f"\nAnswer:\n  {answer_preview}")
    
    # Issues
    if result['issues_found']:
        output_lines.append("\nIssues:")
        for issue in result['issues_found']:
            output_lines.append(f"  - {issue}")
    else:
        output_lines.append("\nIssues:")
        output_lines.append("  - None")
    
    output_lines.append("===================================================")
    
    return '\n'.join(output_lines)


def format_output_verbose_mode(result: Dict[str, Any], excel_paths: list, question: str) -> str:
    """
    Format output in verbose mode (detailed, for debugging).
    
    Args:
        result: Dictionary containing analysis results
        excel_paths: List of input file paths
        question: User's question
    
    Returns:
        Formatted output string with detailed information
    """
    output_lines = []
    output_lines.append("\n" + "="*60)
    output_lines.append("ANALYSIS RESULTS")
    output_lines.append("="*60)
    
    # Show key information about the analysis
    output_lines.append(f"Success: {'✅' if result['success'] else '❌'}")
    output_lines.append(f"Answer: {result['answer']}")
    output_lines.append(f"Confidence: {result['confidence_score']:.2f}/1.0")
    output_lines.append(f"Iterations: {result['total_iterations']}")
    output_lines.append(f"Duration: {result['total_duration']:.2f}s")
    output_lines.append(f"Validation Passed: {'✅' if result.get('validation_passed', False) else '❌'}")
    
    # Display any problems found in the Excel file
    if result['issues_found']:
        output_lines.append(f"\nIssues Found:")
        for issue in result['issues_found']:
            output_lines.append(f"  - {issue}")
    
    # Show detailed feedback if available
    if result.get('improvement_feedback'):
        output_lines.append(f"\nImprovement Feedback:")
        output_lines.append(result['improvement_feedback'])
    
    # Show execution history if available
    if result.get('all_execution_results'):
        output_lines.append(f"\nExecution History:")
        for i, exec_result in enumerate(result['all_execution_results'], 1):
            output_lines.append(f"  Iteration {i}:")
            output_lines.append(f"    Success: {exec_result.get('success', False)}")
            output_lines.append(f"    Turns: {exec_result.get('total_turns', 0)}")
    
    output_lines.append("="*60)
    
    return '\n'.join(output_lines)

