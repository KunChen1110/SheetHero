import argparse
import json
import logging
import sys
from pathlib import Path

from .agent import SheetHero, OutputFormatter
from .config.settings import Config



def _suppress_console_logging():
    logging.getLogger().setLevel(logging.CRITICAL)
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        if isinstance(handler, logging.StreamHandler):
            root_logger.removeHandler(handler)

    for logger_name in list(logging.Logger.manager.loggerDict.keys()):
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.CRITICAL)
        for handler in logger.handlers[:]:
            if isinstance(handler, logging.StreamHandler):
                logger.removeHandler(handler)


def _load_task_from_json(json_path: str, task_id: str = None,
                         task_index: int = 0) -> tuple[dict, Path]:
    path = Path(json_path).expanduser().resolve()
    tasks = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(tasks, list) or not tasks:
        raise ValueError(f"No tasks found in {path}")

    if task_id:
        for task in tasks:
            if task.get("task_id") == task_id:
                return task, path.parent
        available = [task.get("task_id") for task in tasks]
        raise ValueError(f"Task '{task_id}' not found. Available: {available}")

    if task_index < 0 or task_index >= len(tasks):
        raise ValueError(
            f"task_index {task_index} out of range (0..{len(tasks) - 1})"
        )

    return tasks[task_index], path.parent


def main():
    parser = argparse.ArgumentParser(
        description="SheetHero - AI-powered Excel analysis"
    )

    # === Optional Task JSON ===
    parser.add_argument("--task-json",
                        help="Path to a task JSON file (e.g., docs/task01.json)")
    parser.add_argument("--task-id",
                        help="Task ID to select from JSON (e.g., 'Test 1')")
    parser.add_argument("--task-index", type=int, default=0,
                        help="Task index to select from JSON (default: 0)")

    # === Positional Arguments (used when no task JSON) ===
    parser.add_argument("question", nargs="?",
                        help="Question to ask about the Excel file")
    parser.add_argument("excel_paths", nargs='*',
                        help="Path(s) to the Excel file(s)")

    # === Optional Arguments ===
    parser.add_argument("--output-mode", choices=["text", "file"], default=None,
                        help="Choose 'text' for inline answers or 'file' to save results")
    parser.add_argument("--output-file",
                        help="When --output-mode=file, optional custom output filepath")
    parser.add_argument("--deployment",
                        help="Override model deployment (default: config)")
    parser.add_argument("--base-url",
                        help="Override OpenAI base URL (default: config)")
    parser.add_argument("--api-key",
                        help="Override OpenAI API key (default: config)")
    parser.add_argument("--max-turns", type=int,
                        help="Override max iteration turns (default: config)")
    parser.add_argument("--max-qa-rounds", type=int,
                        help="Override max QA rounds (default: config)")
    parser.add_argument("--token-budget", type=int,
                        help="Override total token budget (default: config)")
    parser.add_argument("--no-load-excel", action="store_true",
                        help="Skip loading Excel files (use provided context only)")
    parser.add_argument("--verbose", action="store_true",
                        help="Enable console logging")

    args = parser.parse_args()

    try:
        if not args.verbose:
            _suppress_console_logging()

        config = Config()
        question = args.question
        excel_paths = args.excel_paths

        if args.task_json:
            task, base_dir = _load_task_from_json(
                args.task_json,
                task_id=args.task_id,
                task_index=args.task_index
            )
            question = task.get("prompt", "")
            excel_paths = [
                str((base_dir / path).resolve())
                for path in task.get("spreadsheets", [])
            ]

            expected_output = task.get("expected_output_file", [])
            if args.output_file:
                config.output_file = args.output_file
            elif expected_output:
                config.output_file = str((base_dir / expected_output[0]).resolve())
            else:
                config.output_file = None

            if args.output_mode:
                config.output_mode = args.output_mode
            else:
                config.output_mode = "file" if expected_output else "text"
        else:
            if not question or not excel_paths:
                raise ValueError("question and excel_paths are required without --task-json")
            config.output_mode = args.output_mode or "text"
            config.output_file = args.output_file

        if args.deployment:
            config.deployment = args.deployment
        if args.base_url:
            config.base_url = args.base_url
        if args.api_key:
            config.api_key = args.api_key
        if args.max_turns is not None:
            config.max_turns = args.max_turns
        if args.max_qa_rounds is not None:
            config.max_qa_rounds = args.max_qa_rounds
        if args.token_budget is not None:
            config.total_token_budget = args.token_budget

        agent = SheetHero(
            excel_paths=excel_paths,
            config=config,
            load_excel=not args.no_load_excel
        )

        session = agent.start_session(question)
        response = agent.step(session)

        progress_steps = 0
        while response.get("type") in {"clarification", "progress"}:
            if response.get("type") == "clarification":
                print(f"Agent: {response.get('message')}")
                user_reply = input("You: ").strip()
                if not user_reply:
                    print("Error: empty reply is not allowed.", file=sys.stderr)
                    sys.exit(1)
                response = agent.step(session, user_reply)
                continue

            progress_steps += 1
            if progress_steps > config.max_turns:
                print("Error: progress loop exceeded max turns.", file=sys.stderr)
                sys.exit(1)
            response = agent.step(session)

        if response.get("type") == "error":
            print(f"Error: {response.get('message')}", file=sys.stderr)
            sys.exit(1)
        if response.get("type") != "final":
            print(f"Error: unexpected response type {response.get('type')}", file=sys.stderr)
            sys.exit(1)

        result = response.get("result")
        if result and "execution_result" in result:
            exec_result = result.get("execution_result", {})
            val_result = result.get("validation_result", {})
            final_answer = result.get(
                "final_answer",
                exec_result.get("answer", "")
            )
            result = {
                "success": exec_result.get("success", False),
                "answer": final_answer,
                "confidence_score": val_result.get("confidence_score", 0.0),
                "validation_passed": val_result.get("validation_passed", False),
                "total_iterations": exec_result.get("total_turns", 0),
                "all_execution_results": [exec_result],
                "all_validation_results": [val_result] if val_result else [],
                "conversation_history": exec_result.get("conversation_history", []),
                "issues_found": val_result.get("issues_found", []),
                "improvement_feedback": val_result.get("improvement_feedback", ""),
                "total_duration": exec_result.get("total_duration", 0.0),
            }
        if not question:
            print("Warning: empty question provided; results may be unreliable.", file=sys.stderr)

        output = OutputFormatter().format_user_mode(
            result,
            excel_paths,
            question,
            output_mode=config.output_mode
        )

        print(output)

        sys.exit(0 if result and result.get('success') else 1)

    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
