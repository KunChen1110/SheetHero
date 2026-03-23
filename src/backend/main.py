import argparse
import json
import re
import runpy
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config.settings import Config
from .diagnose_benchmark import run_diagnose_benchmark
from .service.sheethero_service import SheetHeroService
from .service.stream_dialogue_driver import StreamDialogueDriver

# CLI backend debug mode: python3 -m src.backend.main
@dataclass
class InputBuffer:
    excel_paths: list[str] = field(default_factory=list)
    prompt: str | None = None

    def clear(self) -> None:
        self.excel_paths.clear()
        self.prompt = None

    def ready(self) -> bool:
        return self.prompt is not None


def _mask_key(api_key: str | None) -> str:
    key = (api_key or "").strip()
    if not key:
        return "(empty)"
    if len(key) <= 8:
        return "***"
    return f"{key[:4]}...{key[-4:]}"


def _print_llm_config(config: Config) -> None:
    base_url = (config.base_url or "").strip() or "(OpenAI default)"
    print(
        "[llm config] "
        f"deployment={config.deployment}, "
        f"base_url={base_url}, "
        f"api_key={_mask_key(config.api_key)}"
    )


def _handle_llm_command(service: SheetHeroService, line: str) -> None:
    parser = argparse.ArgumentParser(prog="!llm", add_help=False)
    parser.add_argument("--show", action="store_true")
    parser.add_argument("--switch--offline", dest="switch_offline",
                        nargs="?", const="__PROMPT__", default=None)

    try:
        args = parser.parse_args(shlex.split(line)[1:])
    except SystemExit:
        print(
            "Error: usage `!llm --show` or "
            "`!llm --switch--offline <model_full_name>`"
        )
        return

    has_update = args.switch_offline is not None
    if args.show:
        _print_llm_config(service.config)
    if not args.show and not has_update:
        print("Error: usage `!llm --show` or `!llm --switch--offline <model_full_name>`")
        return

    if has_update:
        model_name = args.switch_offline
        if model_name == "__PROMPT__":
            model_name = input("Model full name (e.g. qwen2.5-coder:7b-instruct): ").strip()
        else:
            model_name = (model_name or "").strip()

        if not model_name:
            print("Error: model full name is required.")
            return

        service.config.api_key = ""
        service.config.base_url = "http://localhost:11434/v1"
        service.config.deployment = model_name
        print("[llm switched] offline mode enabled.")
        _print_llm_config(service.config)


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
                details = str(event.get("details_markdown") or "").strip()
                if details:
                    user_reply = input(f"Agent: {question}\n\n{details}\nYou: ")
                else:
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


def _build_task_output_filename(task: dict[str, Any], index: int) -> str:
    task_id = str(task.get("task_id") or f"task{index}")
    normalized = re.sub(r"[^A-Za-z0-9_-]+", "", task_id).lower()
    if not normalized:
        normalized = f"task{index}"
    return f"{normalized}_output.xlsx"


def _resolve_dataset_output_path(
    root: Path,
    task: dict[str, Any],
    index: int,
    output_path_arg: str | None,
) -> Path:
    default_output_dir = root / "artifacts" / "output"
    filename = _build_task_output_filename(task, index)

    if output_path_arg is None or output_path_arg.strip() == "":
        return (default_output_dir / filename).resolve()

    candidate = Path(output_path_arg).expanduser()
    if not candidate.is_absolute():
        candidate = default_output_dir / candidate

    if candidate.suffix.lower() == ".xlsx":
        return candidate.resolve()
    return (candidate / filename).resolve()



def _handle_dataset_command(service: SheetHeroService, buffer: InputBuffer, line: str) -> None:
    parser = argparse.ArgumentParser(prog="!dataset", add_help=False)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--index", type=int)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--output_path", type=str, default=None)
    try:
        args = parser.parse_args(shlex.split(line)[1:])
    except SystemExit:
        print(
            "Error: usage `!dataset --list` or "
            "`!dataset --index N [--prepare] [--output_path PATH]`"
        )
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

    if loaded:
        try:
            tasks, _ = _load_tasks()
            task = tasks[args.index - 1]
            root = Path(__file__).resolve().parents[2]
            resolved_output = _resolve_dataset_output_path(
                root=root,
                task=task,
                index=args.index,
                output_path_arg=args.output_path
            )
            service.config.output_mode = "file"
            service.config.output_file = str(resolved_output)
            print(f"[output path set] {resolved_output}")
        except (FileNotFoundError, json.JSONDecodeError, IndexError) as e:
            print(f"Error: failed to resolve output path: {e}")
            return

    if loaded and not args.prepare and buffer.ready():
        _execute_turn(service, buffer)


def _handle_diagnose_benchmark_command(line: str) -> None:
    parser = argparse.ArgumentParser(prog="!DiagnosebenchmarkTest", add_help=False)
    parser.add_argument(
        "split",
        nargs="?",
        choices=["small", "median", "all"],
        default="small",
    )
    parser.add_argument("--limit", type=int, default=0)
    try:
        args = parser.parse_args(shlex.split(line)[1:])
    except SystemExit:
        print(
            "Error: usage `!DiagnosebenchmarkTest` or "
            "`!DiagnosebenchmarkTest small|median|all [--limit N]`"
        )
        return

    split_map = {
        "small": "dataset_small",
        "median": "dataset_median",
        "all": "all",
    }
    resolved_split = split_map[args.split]
    print(f"[diagnose benchmark] running split={resolved_split}...")
    result = run_diagnose_benchmark(split=resolved_split, limit=args.limit)
    print(f"[diagnose benchmark] report={result['report_path']}")
    print(
        "[diagnose benchmark] "
        f"cases={result['cases_evaluated']}, "
        f"loose_matches={result['matched']}/{result['expected_total']}"
    )


def _handle_family_synthetic_command() -> None:
    root = Path(__file__).resolve().parents[2]
    script_path = root / "test" / "utils" / "run_family_synthetic_regression.py"
    print("[family synthetic] running abstract family regression...")
    try:
        runpy.run_path(str(script_path), run_name="__main__")
        print("[family synthetic] passed")
        return
    except Exception as exc:
        print(f"[family synthetic] failed: {exc}")


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
    print("Type `!dataset --index N --output_path Task01_output.xlsx` to load and run a dataset task.")
    print("Type `!llm --show` to view active model endpoint settings.")
    print("Type `!llm --switch--offline <model_full_name>` to switch to local LLM.")
    print("Type `!DiagnosebenchmarkTest` to run the small diagnose benchmark.")
    print("Type `!DiagnosebenchmarkTest median` to run the medium diagnose benchmark.")
    print("Type `!DiagnosebenchmarkTest all` to run all diagnose benchmark cases.")
    print("Type `!DiagnosebenchmarkTest --limit N` to run only the first N benchmark cases.")
    print("Type `!FamilySyntheticTest` to run the abstract family synthetic regression.")
    _print_llm_config(config)

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

        if line.lower().startswith("!diagnosebenchmarktest"):
            _handle_diagnose_benchmark_command(line)
            continue

        if line.lower().startswith("!familysynthetictest"):
            _handle_family_synthetic_command()
            continue

        if line.startswith("!llm"):
            _handle_llm_command(service, line)
            continue

        if line == "run":
            _execute_turn(service, buffer)
            continue

        # Treat any other input as a prompt only; run on explicit `run`.
        buffer.prompt = line
        print(f"[prompt set] {buffer.prompt}")


if __name__ == "__main__":
    main()
