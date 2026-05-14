import argparse
import json
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib import request, error

from .config.settings import Config
from .diagnose_benchmark import run_diagnose_benchmark
from .service.sheethero_service import SheetHeroService
from .service.stream_dialogue_driver import StreamDialogueDriver

# CLI backend debug mode: python3 -m backend.main
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
        f"understanding={config.resolve_stage_deployment('understanding')}, "
        f"qa={config.resolve_stage_deployment('qa')}, "
        f"cleaning={config.resolve_stage_deployment('cleaning')}, "
        f"execution={config.resolve_stage_deployment('execution')}, "
        f"base_url={base_url}, "
        f"api_key={_mask_key(config.api_key)}"
    )


def _fetch_offline_model_names() -> list[str]:
    try:
        with request.urlopen("http://localhost:11434/v1/models", timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError, error.URLError):
        return []
    models = payload.get("data") if isinstance(payload, dict) else []
    names: list[str] = []
    for item in models if isinstance(models, list) else []:
        model_id = str((item or {}).get("id") or "").strip()
        if model_id:
            names.append(model_id)
    return sorted(dict.fromkeys(names))


def _prompt_for_offline_model(prompt_text: str = "Model full name") -> str:
    models = _fetch_offline_model_names()
    if models:
        print("Available offline models:")
        for idx, model_name in enumerate(models, start=1):
            print(f"{idx:>2}. {model_name}")
        raw = input(f"{prompt_text} (number or full name): ").strip()
        if raw.isdigit():
            index = int(raw)
            if 1 <= index <= len(models):
                return models[index - 1]
        return raw
    return input(f"{prompt_text} (e.g. qwen3:8b): ").strip()


def _print_output_config(config: Config) -> None:
    output_path = (config.output_file or "").strip() or "(auto)"
    print(
        "[output config] "
        f"mode={config.output_mode}, "
        f"output_file={output_path}"
    )


def _normalize_split_flag_tokens(argv: list[str]) -> list[str]:
    normalized: list[str] = []
    index = 0
    while index < len(argv):
        token = argv[index]
        if token == "--" and index + 1 < len(argv):
            next_token = argv[index + 1]
            if re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", next_token):
                normalized.append(f"--{next_token}")
                index += 2
                continue
        normalized.append(token)
        index += 1
    return normalized


def _print_cli_banner(config: Config) -> None:
    print("SheetHero CLI")
    print("")
    print("[Core]")
    print("  prompt text                         set current user request")
    print("  run | reset | exit                  execute, clear buffer, or quit")
    print("  !status                             show compact model/output config")
    print("")
    print("[Input / Output]")
    print("  !path=[\"/abs/file.xlsx\"]            set input files manually")
    print("  !output --show | file | text        inspect or switch output mode")
    print("  !dataset --list | --index N         run original development task N")
    print("")
    print("[Benchmarks]")
    print("  !benchmark dev --list | --index N")
    print("                                      original Task01-Task27 suite")
    print("  !benchmark diagnose small|median|all [--limit N]")
    print("                                      diagnose-stage benchmark")
    print("  !benchmark evaluation clean|median|large --list | --index N")
    print("                                      final suite; always runs LLM judge")
    print("  !judge dev|evaluation ... --index N score latest output with LLM judger")
    print("")
    print("[Model]")
    print("  !llm --show | --list-offline        inspect current/available models")
    print("  !llm --switch--offline <model>      switch all stages to local model")
    print("  !llm --switch--offline-<stage> <model>")
    print("                                      switch one stage: understanding, qa, cleaning, execution")
    print("")


def _print_status(config: Config) -> None:
    base_url = (config.base_url or "").strip() or "OpenAI default"
    output_path = (config.output_file or "").strip() or "auto"
    print(
        "[status] "
        f"model={config.deployment}, "
        f"base_url={base_url}, "
        f"output={config.output_mode}, "
        f"output_path={output_path}"
    )


def _print_help(topic: str = "") -> None:
    normalized = topic.strip().lower()
    if normalized in {"benchmark", "bench", "eval"}:
        print("Benchmark commands:")
        print("  !benchmark dev --list")
        print("  !benchmark dev --index N")
        print("  !benchmark diagnose small|median|all [--limit N]")
        print("  !benchmark evaluation clean|median|large --list")
        print("  !benchmark evaluation clean|median|large --index N")
        print("  !judge dev --index N")
        print("  !judge evaluation clean|median|large --index N [--logger PATH]")
        return
    if normalized == "llm":
        print("LLM commands:")
        print("  !llm --show")
        print("  !llm --list-offline")
        print("  !llm --switch--offline <model>")
        print("  !llm --switch--offline-understanding <model>")
        print("  !llm --switch--offline-qa <model>")
        print("  !llm --switch--offline-cleaning <model>")
        print("  !llm --switch--offline-execution <model>")
        return
    if normalized in {"io", "input", "output"}:
        print("Input/output commands:")
        print("  !path=[\"/absolute/input.xlsx\"]")
        print("  !output --show")
        print("  !output file|text")
        print("  !dataset --list")
        print("  !dataset --index N [--prepare] [--output_path PATH]")
        return

    print("Main commands:")
    print("  run                         execute current prompt/files")
    print("  reset                       clear current prompt/files")
    print("  !benchmark ...              run development, diagnose, or evaluation suites")
    print("  !judge ...                  score latest output with the LLM judger")
    print("  !llm ...                    inspect or switch model endpoints")
    print("  !path=... / !output ...     set input files and output mode")
    print("  !status                     show compact runtime status")
    print("  !help benchmark|llm|io      show detailed command groups")


def _handle_llm_command(service: SheetHeroService, line: str) -> None:
    parser = argparse.ArgumentParser(prog="!llm", add_help=False)
    parser.add_argument("--show", action="store_true")
    parser.add_argument("--list-offline", action="store_true")
    parser.add_argument("--switch--offline", dest="switch_offline",
                        nargs="?", const="__PROMPT__", default=None)
    parser.add_argument("--switch--offline-understanding", dest="switch_offline_understanding",
                        nargs="?", const="__PROMPT__", default=None)
    parser.add_argument("--switch--offline-qa", dest="switch_offline_qa",
                        nargs="?", const="__PROMPT__", default=None)
    parser.add_argument("--switch--offline-cleaning", dest="switch_offline_cleaning",
                        nargs="?", const="__PROMPT__", default=None)
    parser.add_argument("--switch--offline-execution", dest="switch_offline_execution",
                        nargs="?", const="__PROMPT__", default=None)

    try:
        args = parser.parse_args(_normalize_split_flag_tokens(shlex.split(line)[1:]))
    except SystemExit:
        print(
            "Error: usage `!llm --show` or "
            "`!llm --switch--offline <model_full_name>`"
        )
        return

    has_update = any(
        value is not None
        for value in (
            args.switch_offline,
            args.switch_offline_understanding,
            args.switch_offline_qa,
            args.switch_offline_cleaning,
            args.switch_offline_execution,
        )
    )
    if args.list_offline:
        models = _fetch_offline_model_names()
        if not models:
            print("No offline models found at http://localhost:11434/v1/models")
        else:
            print("Available offline models:")
            for idx, model_name in enumerate(models, start=1):
                print(f"{idx:>2}. {model_name}")
    if args.show:
        _print_llm_config(service.config)
    if not args.show and not args.list_offline and not has_update:
        print("Error: usage `!llm --show` or `!llm --switch--offline <model_full_name>`")
        return
    if args.list_offline and not has_update:
        return

    def _resolve_model_name(raw_value: str | None) -> str:
        model_name = raw_value
        if model_name == "__PROMPT__":
            model_name = _prompt_for_offline_model("Model full name")
        else:
            model_name = (model_name or "").strip()
        return model_name

    if has_update:
        global_model_name = _resolve_model_name(args.switch_offline)
        understanding_model_name = _resolve_model_name(args.switch_offline_understanding)
        qa_model_name = _resolve_model_name(args.switch_offline_qa)
        cleaning_model_name = _resolve_model_name(args.switch_offline_cleaning)
        execution_model_name = _resolve_model_name(args.switch_offline_execution)

        model_names = [
            global_model_name,
            understanding_model_name,
            qa_model_name,
            cleaning_model_name,
            execution_model_name,
        ]
        if not any(model_names):
            print("Error: model full name is required.")
            return

        service.config.api_key = ""
        service.config.base_url = "http://localhost:11434/v1"
        if global_model_name:
            service.config.deployment = global_model_name
            service.config.set_all_stage_deployments(global_model_name)
        if understanding_model_name:
            service.config.understanding_deployment = understanding_model_name
        if qa_model_name:
            service.config.qa_deployment = qa_model_name
        if cleaning_model_name:
            service.config.cleaning_deployment = cleaning_model_name
        if execution_model_name:
            service.config.execution_deployment = execution_model_name
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


def _handle_output_command(service: SheetHeroService, line: str) -> None:
    parser = argparse.ArgumentParser(prog="!output", add_help=False)
    parser.add_argument("--show", action="store_true")
    parser.add_argument("mode", nargs="?", choices=["file", "text"])

    try:
        args = parser.parse_args(_normalize_split_flag_tokens(shlex.split(line)[1:]))
    except SystemExit:
        print("Error: usage `!output --show` or `!output file|text`")
        return

    if args.show:
        _print_output_config(service.config)
        return

    if not args.mode:
        print("Error: usage `!output --show` or `!output file|text`")
        return

    service.config.output_mode = args.mode
    if args.mode == "text":
        service.config.output_file = None
    print(f"[output switched] mode={service.config.output_mode}")
    _print_output_config(service.config)


def _load_tasks(dataset_dir: Path | None = None) -> tuple[list[dict[str, Any]], Path]:
    root = Path(__file__).resolve().parents[1]
    candidates = (
        [dataset_dir / "dataset.json"]
        if dataset_dir is not None
        else [
            root / "dataset" / "DevelopmentBenchmark" / "dataset.json",
            root / "dataset.json",
        ]
    )
    for json_path in candidates:
        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                tasks = json.load(f)
            dataset_dir = json_path.parent / "dataset" if json_path.name == "dataset.json" and json_path.parent == root else json_path.parent
            return tasks, dataset_dir
    checked = ", ".join(str(path) for path in candidates)
    raise FileNotFoundError(f"dataset.json not found. Checked: {checked}")


def _print_dataset_list(tasks: list[dict[str, Any]]) -> None:
    if not tasks:
        print("No tasks found in dataset index.")
        return
    print("Available dataset tasks:")
    for idx, task in enumerate(tasks, start=1):
        task_id = task.get("task_id", "?")
        title = task.get("title", "")
        print(f"{idx:>2}. {task_id} - {title}".rstrip(" -"))


def _load_dataset_task(buffer: InputBuffer, index: int, dataset_dir_arg: Path | None = None) -> bool:
    tasks, dataset_dir = _load_tasks(dataset_dir_arg)
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


def _clarification_replies_for_task(task: dict[str, Any]) -> list[str]:
    conversations = task.get("conversations")
    if not isinstance(conversations, list):
        return []
    replies: list[str] = []
    for item in conversations[1:]:
        if not isinstance(item, dict) or item.get("role") != "user":
            continue
        content = str(item.get("content") or "").strip()
        if content:
            replies.append(content)
    return replies


def _pick_clarification_reply(replies: list[str], index: int) -> str | None:
    if not replies:
        return None
    if index < len(replies):
        return replies[index]
    return replies[-1]


def _extract_success_fields(response: dict[str, Any]) -> tuple[bool, float, float, str]:
    result = response.get("result") or {}
    execution_result = result.get("execution_result") or {}
    validation_result = result.get("validation_result") or {}
    success = bool(
        result.get("success", False)
        or (
            execution_result.get("success") is True
            and validation_result.get("validation_passed") is True
        )
        or (
            response.get("type") == "final"
            and validation_result.get("validation_passed") is True
        )
    )
    confidence = float(
        result.get("confidence_score")
        or validation_result.get("confidence_score")
        or 0.0
    )
    duration = float(
        result.get("total_duration")
        or response.get("total_duration")
        or 0.0
    )
    short_answer = str(
        result.get("short_answer")
        or response.get("message")
        or ""
    ).strip()
    return success, confidence, duration, short_answer


def _print_benchmark_summary(
    task: dict[str, Any],
    prompt: str,
    output_path: Path,
    response: dict[str, Any],
) -> None:
    success, confidence, duration, short_answer = _extract_success_fields(response)
    print(f"Task:       {task.get('task_id', '?')}")
    print(f"Prompt:     {prompt[:80]}{'...' if len(prompt) > 80 else ''}")
    print(f"Success:    {'YES' if success else 'NO'}")
    print(f"Confidence: {confidence:.2f}")
    print(f"Duration:   {duration:.2f}s")
    print(f"Output:     {output_path}")
    if short_answer:
        print(f"Summary:    {short_answer}")


def _run_external_judge(task: dict[str, Any], dataset_dir: Path) -> None:
    task_id = str(task.get("task_id") or "").strip()
    if not task_id:
        print("[judge] skipped: task_id missing")
        return
    dataset_path = dataset_dir / "dataset.json"
    try:
        from .Judger.evaluator import evaluate_task
        from .Judger.loader import find_latest_logger

        logger_path = find_latest_logger(task_id)
        result = evaluate_task(task_id, logger_path, dataset_path=str(dataset_path))
    except Exception as exc:
        print(f"[judge] ERROR: {exc}")
        return

    print(
        "[judge] "
        f"score={result.get('total_score')}/100, "
        f"table_raw={result.get('table_raw')}/100, "
        f"text_raw={result.get('text_raw')}/100"
    )
    feedback = str(result.get("table_feedback") or result.get("text_feedback") or "").strip()
    if feedback:
        print(f"[judge feedback] {feedback}")


def _run_benchmark_task(
    service: SheetHeroService,
    dataset_dir: Path,
    index: int,
    output_path_arg: str | None,
    run_judge: bool,
) -> None:
    tasks, _ = _load_tasks(dataset_dir)
    if index < 1 or index > len(tasks):
        print(f"Error: dataset index out of range. Valid range: 1..{len(tasks)}")
        return

    task = tasks[index - 1]
    prompt = str(task.get("prompt") or "").strip()
    spreadsheets = task.get("spreadsheets", [])
    if not prompt:
        print(f"Error: task {index} has empty prompt.")
        return
    if not isinstance(spreadsheets, list) or not spreadsheets:
        print(f"Error: task {index} has no spreadsheets.")
        return

    input_paths: list[str] = []
    missing_files: list[str] = []
    for rel in spreadsheets:
        full_path = dataset_dir / str(rel).strip()
        if full_path.exists():
            input_paths.append(str(full_path.resolve()))
        else:
            missing_files.append(str(full_path))
    if missing_files:
        print("Error: some dataset files are missing:")
        for path in missing_files:
            print(f"- {path}")
        return

    root = Path(__file__).resolve().parents[1]
    output_path = _resolve_dataset_output_path(root, task, index, output_path_arg)
    service.config.output_mode = "file"
    service.config.output_file = str(output_path)

    print(
        f"[dataset loaded] index={index}, task={task.get('task_id', '?')}, "
        f"title={task.get('title', '')}, files={len(input_paths)}"
    )
    print(f"[output path set] {output_path}")

    response = service.submit_turn(prompt, input_paths)
    replies = _clarification_replies_for_task(task)
    clarification_index = 0
    while response.get("type") == "clarification":
        reply = _pick_clarification_reply(replies, clarification_index)
        if reply is None:
            print(f"[CLARIFICATION REQUIRED] {response.get('message', '')}")
            return
        print(f"[auto clarification] {reply}")
        response = service.submit_clarification(reply)
        clarification_index += 1

    _print_benchmark_summary(task, prompt, output_path, response)
    if run_judge:
        _run_external_judge(task, dataset_dir)


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
                    result_kind = event.get("result_kind")
                    has_output_file = event.get("has_output_file")
                    output_path = event.get("output_path")
                    truncated = event.get("truncated")
                    meta_parts = []
                    if result_kind is not None:
                        meta_parts.append(f"result_kind={result_kind}")
                    if has_output_file is not None:
                        meta_parts.append(f"has_output_file={has_output_file}")
                    if truncated:
                        meta_parts.append("truncated=True")
                    if output_path:
                        meta_parts.append(f"output_path={output_path}")
                    if meta_parts:
                        print("[result meta] " + ", ".join(meta_parts))
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
        args = parser.parse_args(_normalize_split_flag_tokens(shlex.split(line)[1:]))
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
            root = Path(__file__).resolve().parents[1]
            resolved_output = _resolve_dataset_output_path(
                root=root,
                task=task,
                index=args.index,
                output_path_arg=args.output_path
            )
            if service.config.output_mode == "file":
                service.config.output_file = str(resolved_output)
                print(f"[output path set] {resolved_output}")
            else:
                service.config.output_file = str(resolved_output)
                print("[text preview mode] structured outputs will be rendered as text previews.")
        except (FileNotFoundError, json.JSONDecodeError, IndexError) as e:
            print(f"Error: failed to resolve output path: {e}")
            return

    if loaded and not args.prepare and buffer.ready():
        _execute_turn(service, buffer)


def _system_evaluation_dataset_dir(split: str) -> Path:
    root = Path(__file__).resolve().parents[1]
    split_map = {
        "clean": "clean_cases",
        "median": "median_clean_cases",
        "large": "large_clean_cases",
    }
    return root / "dataset" / "SystemEvaluationBenchmark" / split_map[split]


def _handle_dataset_like_benchmark_command(
    service: SheetHeroService,
    buffer: InputBuffer,
    dataset_dir: Path,
    argv: list[str],
    prog: str,
    judge_default: bool = False,
) -> None:
    parser = argparse.ArgumentParser(prog=prog, add_help=False)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--index", type=int)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--output_path", type=str, default=None)
    try:
        args = parser.parse_args(_normalize_split_flag_tokens(argv))
    except SystemExit:
        print(
            f"Error: usage `{prog} --list` or "
            f"`{prog} --index N [--prepare] [--output_path PATH]`"
        )
        return

    if args.list:
        try:
            tasks, _ = _load_tasks(dataset_dir)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error: {e}")
            return
        _print_dataset_list(tasks)
        return

    if args.index is None:
        print(f"Error: `{prog}` requires `--index N` or `--list`.")
        return

    if not args.prepare:
        _run_benchmark_task(
            service=service,
            dataset_dir=dataset_dir,
            index=args.index,
            output_path_arg=args.output_path,
            run_judge=judge_default,
        )
        return

    try:
        loaded = _load_dataset_task(buffer, args.index, dataset_dir)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error: {e}")
        return

    if loaded:
        try:
            tasks, _ = _load_tasks(dataset_dir)
            task = tasks[args.index - 1]
            root = Path(__file__).resolve().parents[1]
            resolved_output = _resolve_dataset_output_path(
                root=root,
                task=task,
                index=args.index,
                output_path_arg=args.output_path
            )
            service.config.output_file = str(resolved_output)
            if service.config.output_mode == "file":
                print(f"[output path set] {resolved_output}")
            else:
                print("[text preview mode] structured outputs will be rendered as text previews.")
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
        args = parser.parse_args(_normalize_split_flag_tokens(shlex.split(line)[1:]))
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


def _handle_benchmark_command(service: SheetHeroService, buffer: InputBuffer, line: str) -> None:
    tokens = shlex.split(line)
    if len(tokens) < 2:
        print(
            "Error: usage `!benchmark dev|diagnose|evaluation ...` "
            "or `!benchmark evaluation clean|median|large --index N`"
        )
        return

    suite = tokens[1].lower()
    root = Path(__file__).resolve().parents[1]

    if suite in {"dev", "legacy"}:
        dataset_dir = root / "dataset" / "DevelopmentBenchmark"
        _handle_dataset_like_benchmark_command(
            service,
            buffer,
            dataset_dir,
            tokens[2:],
            "!benchmark dev",
            judge_default=False,
        )
        return

    if suite == "diagnose":
        diagnose_line = "!DiagnosebenchmarkTest " + " ".join(tokens[2:])
        _handle_diagnose_benchmark_command(diagnose_line)
        return

    if suite in {"evaluation", "eval"}:
        if len(tokens) < 3:
            print("Error: usage `!benchmark evaluation clean|median|large --index N`")
            return
        split = tokens[2].lower()
        if split not in {"clean", "median", "large"}:
            print("Error: evaluation split must be one of: clean, median, large")
            return
        _handle_dataset_like_benchmark_command(
            service,
            buffer,
            _system_evaluation_dataset_dir(split),
            tokens[3:],
            f"!benchmark evaluation {split}",
            judge_default=True,
        )
        return

    print("Error: benchmark suite must be one of: dev, diagnose, evaluation")


def _handle_judge_command(line: str) -> None:
    parser = argparse.ArgumentParser(prog="!judge", add_help=False)
    parser.add_argument("suite", choices=["dev", "legacy", "evaluation", "eval"])
    parser.add_argument("split", nargs="?", choices=["clean", "median", "large"])
    parser.add_argument("--index", type=int, required=True)
    parser.add_argument("--logger", type=str, default="")
    parser.add_argument("--save", action="store_true")
    try:
        args = parser.parse_args(_normalize_split_flag_tokens(shlex.split(line)[1:]))
    except SystemExit:
        print(
            "Error: usage `!judge dev --index N` or "
            "`!judge evaluation clean|median|large --index N [--logger PATH] [--save]`"
        )
        return

    root = Path(__file__).resolve().parents[1]
    if args.suite in {"dev", "legacy"}:
        dataset_path = root / "dataset" / "DevelopmentBenchmark" / "dataset.json"
    else:
        if not args.split:
            print("Error: evaluation judging requires split: clean, median, or large.")
            return
        dataset_path = _system_evaluation_dataset_dir(args.split) / "dataset.json"

    task_id = f"Test {args.index}"
    try:
        from .Judger.evaluator import evaluate_task
        from .Judger.loader import find_latest_logger

        logger_path = args.logger or find_latest_logger(task_id)
        result = evaluate_task(
            task_id,
            logger_path,
            dataset_path=str(dataset_path),
            save_normalized=args.save,
        )
    except Exception as e:
        print(f"[judge error] {e}")
        return

    print(
        "[judge result] "
        f"task={task_id}, "
        f"score={result.get('total_score')}, "
        f"table={result.get('table_raw')}, "
        f"text={result.get('text_raw')}"
    )



def main() -> None:
    root = Path(__file__).resolve().parents[1]
    default_output_dir = root / "artifacts" / "output"

    config = Config()
    config.output_mode = "file"
    config.output_file = str(default_output_dir)

    service = SheetHeroService(config=config)
    buffer = InputBuffer()

    _print_cli_banner(config)

    while True:
        line = input(">>> ").strip()

        if line == "exit":
            break

        if line == "reset":
            buffer.clear()
            print("[buffer cleared]")
            continue

        if line == "!status":
            _print_status(service.config)
            continue

        if line.startswith("!help"):
            parts = shlex.split(line)
            _print_help(parts[1] if len(parts) > 1 else "")
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

        if line.lower().startswith("!benchmark"):
            _handle_benchmark_command(service, buffer, line)
            continue

        if line.lower().startswith("!judge"):
            _handle_judge_command(line)
            continue

        if line.startswith("!llm"):
            _handle_llm_command(service, line)
            continue

        if line.startswith("!output"):
            _handle_output_command(service, line)
            continue

        if line == "run":
            _execute_turn(service, buffer)
            continue

        # Treat any other input as a prompt only; run on explicit `run`.
        buffer.prompt = line
        print(f"[prompt set] {buffer.prompt}")


if __name__ == "__main__":
    main()
