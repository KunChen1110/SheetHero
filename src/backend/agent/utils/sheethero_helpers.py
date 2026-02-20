"""Helper utilities for SheetHero orchestration."""

import os
from typing import Any, Dict, Optional


def summarize_workbooks(workbooks: Optional[object]) -> str:
    if workbooks is None:
        return "none"
    if isinstance(workbooks, dict):
        keys = list(workbooks.keys())
        preview = ", ".join(str(k) for k in keys[:5])
        more = " ..." if len(keys) > 5 else ""
        return f"{len(keys)} workbook(s): {preview}{more}"
    if isinstance(workbooks, (list, tuple)):
        return f"{len(workbooks)} workbook(s)"
    return type(workbooks).__name__


def append_ui_thought(session: Any, stage: str, status: str, content: Any) -> None:
    session.ui_thoughts.append(
        {
            "stage": stage,
            "status": status,
            "content": content,
        }
    )


def build_clarification_message(result: Dict[str, Any]) -> str:
    feedback = (result.get("improvement_feedback") or "").strip()
    issues = result.get("issues_found") or []

    lines = ["I need a bit more detail to continue."]
    if feedback:
        lines.append(feedback)
    if issues:
        lines.append("Issues detected:")
        for issue in issues:
            lines.append(f"- {issue}")
    lines.append("Please clarify or provide additional context.")
    return "\n".join(lines)


def build_output_instruction(output_preferences: Dict[str, Any], output_path: str) -> str:
    """Generate AI instructions for output format based on user preferences."""
    mode = output_preferences.get("mode", "text")
    if mode == "file":
        return (
            "**OUTPUT REQUIREMENTS:**\n"
            f"1. Save final results to: `output_path` (variable available in code: \"{output_path}\")\n"
            "2. Use the UNIFIED OUTPUT WORKFLOW:\n"
            "   - Convert DataFrame to 2D list: `[df.columns.tolist()] + df.values.tolist()`\n"
            "   - Create output sheet: `create_output_sheet(\"Output\")`\n"
            "   - Write data: `write_dataframe_to_sheet(data_2d, \"Output\", \"A1\")`\n"
            "   - Add summary if needed: `add_summary_row(\"Output\", row_num, {\"Total\": val, \"Average\": avg})`\n"
            "   - Highlight important rows: `highlight_rows(\"Output\", [row_nums], {\"fill_color\": \"red\"})`\n"
            "   - Save: `save_workbook_to(output_path)`\n"
            "3. Return the saved file path in Final Answer\n"
            "4. DO NOT use DataFrame.to_excel() or pd.ExcelWriter()"
        )

    return (
        "Final results must be presented directly in the final answer as a clean markdown "
        "table or list. Do not save any files unless the user explicitly asks."
    )


def build_default_output_path(excel_paths: list[str], module_file: str) -> str:
    first_input = excel_paths[0] if excel_paths else "output"
    base_name = os.path.splitext(os.path.basename(first_input))[0]
    task_dir = os.path.basename(os.path.dirname(first_input)) or "output"
    project_root = os.path.abspath(
        os.path.join(os.path.dirname(module_file), "../../../..")
    )
    artifacts_dir = os.path.join(project_root, "artifacts", task_dir)
    os.makedirs(artifacts_dir, exist_ok=True)
    return os.path.join(artifacts_dir, f"{base_name}_output.xlsx")


def log_final_report(progress_logger: Any, session: Any) -> None:
    if not progress_logger:
        return

    exec_result = (session.result or {}).get("execution_result", {})
    val_result = (session.result or {}).get("validation_result", {})

    progress_logger.log("\n" + "=" * 80, to_terminal=False)
    progress_logger.log("🎯 [FINAL SUMMARY]", to_terminal=False)
    progress_logger.log("=" * 80, to_terminal=False)
    progress_logger.log(
        f"Success: {'✅ YES' if exec_result.get('success') else '❌ NO'}",
        to_terminal=False
    )
    progress_logger.log(
        f"Validation Passed: {'✅ YES' if val_result.get('validation_passed') else '❌ NO'}",
        to_terminal=False
    )
    progress_logger.log(
        f"Confidence Score: {val_result.get('confidence_score', 0.0):.2f}/1.0",
        to_terminal=False
    )
    progress_logger.log(
        f"Final Answer: {exec_result.get('answer', '')}",
        to_terminal=False
    )
    progress_logger.log("=" * 80, to_terminal=False)


def log_session_context(
    progress_logger: Any,
    session: Any,
    current_request: str,
) -> None:
    if not progress_logger:
        return
    context = (session.context_understanding or "").strip() or "<empty>"
    current_wb_summary = summarize_workbooks(session.current_workbooks)
    previous_wb_summary = summarize_workbooks(session.previous_workbooks)
    safe_request = (current_request or "").replace("`", "'").strip() or "<empty>"
    progress_logger.log_raw(
        "\n### [SESSION CONTEXT]\n"
        f"- state: `{session.state}`\n"
        f"- request: `{safe_request}`\n"
        f"- context_understanding:\n```\n{context}\n```\n"
        f"- current_workbooks: `{current_wb_summary}`\n"
        f"- previous_workbooks: `{previous_wb_summary}`\n"
    )
