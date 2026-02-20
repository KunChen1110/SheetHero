import argparse
import json
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config.settings import Config
from .service.sheethero_service import SheetHeroService
from .service.stream_dialogue_driver import StreamDialogueDriver


@dataclass
class InputBuffer:
    excel_paths: list[str] = field(default_factory=list)
    prompt: str | None = None

    def clear(self) -> None:
        self.excel_paths.clear()
        self.prompt = None

    def ready(self) -> bool:
        return self.prompt is not None


def _handle_path(buffer: InputBuffer, line: str) -> None:
    payload = line[len("!path="):].strip()
    if not payload:
        buffer.excel_paths = []
        print("[paths set] []")
        return
    try:
        buffer.excel_paths = json.loads(payload)
        print(f"[paths set] {buffer.excel_paths}")
    except json.JSONDecodeError:
        print("Error: !path expects a JSON list, e.g. !path=[\"a.xlsx\"]")


def _load_tasks() -> tuple[list[dict[str, Any]], Path]:
    root = Path(__file__).resolve().parents[2]
    candidates = [root / "dataset" / "dataset.json", root / "dataset.json"]
    for json_path in candidates:
        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                tasks = json.load(f)
            dataset_dir = json_path.parent / "dataset" if json_path.name == "dataset.json" and json_path.parent == root else json_path.parent
            return tasks, dataset_dir
    raise FileNotFoundError("dataset.json not found. Checked: dataset/dataset.json and dataset.json")


def _print_dataset_list(tasks: list[dict[str, Any]]) -> None:
    if not tasks:
        print("No tasks found in dataset index.")
        return
    print("Available dataset tasks:")
    for idx, task in enumerate(tasks, start=1):
        task_id = task.get("task_id", "?")
        title = task.get("title", "")
        print(f"{idx:>2}. {task_id} - {title}".rstrip(" -"))


def _load_dataset_task(buffer: InputBuffer, index: int) -> bool:
    tasks, dataset_dir = _load_tasks()
    if index < 1 or index > len(tasks):
        print(f"Error: dataset index out of range. Valid range: 1..{len(tasks)}")
        return False

    task = tasks[index - 1]
    prompt = str(task.get("prompt") or "").strip()
    spreadsheets = task.get("spreadsheets", [])
    if not prompt:
        print(f"Error: task {index} has empty prompt.")
        return False
    if not isinstance(spreadsheets, list) or not spreadsheets:
        print(f"Error: task {index} has no spreadsheets.")
        return False

    excel_paths: list[str] = []
    missing_files: list[str] = []
    for rel in spreadsheets:
        rel_path = str(rel).strip()
        full_path = dataset_dir / rel_path
        if full_path.exists():
            excel_paths.append(str(full_path.resolve()))
        else:
            missing_files.append(str(full_path))
    if missing_files:
        print("Error: some dataset files are missing:")
        for path in missing_files:
            print(f"- {path}")
        return False

    buffer.prompt = prompt
    buffer.excel_paths = excel_paths
    task_id = task.get("task_id", f"Task {index}")
    title = task.get("title", "")
    print(f"[dataset loaded] index={index}, task={task_id}, title={title}, files={len(excel_paths)}")
    return True


def _execute_turn(service: SheetHeroService, buffer: InputBuffer) -> None:
    if not buffer.ready():
        print("Error: prompt not set.")
        return

    driver = StreamDialogueDriver(service)
    stream = driver.start(buffer.prompt or "", buffer.excel_paths)

    while True:
        for event in stream:
            event_type = event.get("type", "")
            stage = event.get("stage")

            if stage:
                print(f"[{event_type}] stage={stage}")
            else:
                print(f"[{event_type}]")

            thoughts = event.get("ui_thoughts")
            if thoughts:
                print(f"[ui_thoughts] +{len(thoughts)}")

            if event_type == "clarification":
                question = event.get("message") or "Please clarify your request."
                user_reply = input(f"Agent: {question}\nYou: ")
                stream = driver.reply(user_reply)
                break  # restart loop with new stream

            if event_type in {"final", "error"}:
                print(f"Agent: {event.get('message')}")
                if event_type == "final":
                    buffer.clear()
                return

        else:
            # for-loop exhausted without break → stream ended unexpectedly
            print("Error: stream ended without final/error.")
            return



def _handle_dataset_command(service: SheetHeroService, buffer: InputBuffer, line: str) -> None:
    parser = argparse.ArgumentParser(prog="!dataset", add_help=False)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--index", type=int)
    parser.add_argument("--prepare", action="store_true")
    try:
        args = parser.parse_args(shlex.split(line)[1:])
    except SystemExit:
        print("Error: usage `!dataset --list` or `!dataset --index N [--prepare]`")
        return

    if args.list:
        try:
            tasks, _ = _load_tasks()
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error: {e}")
            return
        _print_dataset_list(tasks)
        return

    if args.index is None:
        print("Error: `!dataset` requires `--index N` or `--list`.")
        return

    try:
        loaded = _load_dataset_task(buffer, args.index)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error: {e}")
        return

    if loaded and not args.prepare and buffer.ready():
        _execute_turn(service, buffer)


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    default_output_dir = root / "artifacts" / "output"

    config = Config()
    config.output_mode = "file"
    config.output_file = str(default_output_dir)

    service = SheetHeroService(config=config)
    buffer = InputBuffer()

    print("SheetHero CLI (debug mode)")
    print("Type `exit` to quit.")
    print("Type `run` to execute the current turn.")
    print("Type `!dataset --list` to list dataset tasks.")
    print("Type `!dataset --index N` to load and run a dataset task.")

    while True:
        line = input(">>> ").strip()

        if line == "exit":
            break

        if line == "reset":
            buffer.clear()
            print("[buffer cleared]")
            continue

        if line.startswith("!path="):
            _handle_path(buffer, line)
            continue

        if line.startswith("!dataset"):
            _handle_dataset_command(service, buffer, line)
            continue

        if line == "run":
            _execute_turn(service, buffer)
            continue

        # Treat any other input as a prompt only; run on explicit `run`.
        buffer.prompt = line
        print(f"[prompt set] {buffer.prompt}")


if __name__ == "__main__":
    main()
