#!/usr/bin/env python3
"""Stream test for validating stage-by-stage ui_thoughts emission."""

from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from pathlib import Path
from typing import Any, Iterable


REQUIRED_STAGES = ["understanding", "diagnosing", "cleaning", "executing", "validation"]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_tasks(dataset_dir: Path) -> list[dict]:
    candidates = [
        dataset_dir / "dataset.json",
        _repo_root() / "dataset.json",
    ]
    for path in candidates:
        if path.exists():
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
    raise FileNotFoundError("dataset.json not found in dataset/ or repo root.")


def _select_task(tasks: list[dict], test_id: int) -> dict:
    if test_id <= 0 or test_id > len(tasks):
        raise ValueError(f"test id out of range: {test_id} (valid range 1..{len(tasks)})")
    return tasks[test_id - 1]


def _build_input_paths(dataset_dir: Path, spreadsheets: list[str]) -> list[str]:
    paths: list[str] = []
    for rel in spreadsheets:
        full_path = dataset_dir / rel
        if not full_path.exists():
            raise FileNotFoundError(f"Input file not found: {full_path}")
        paths.append(str(full_path.resolve()))
    return paths


def _print_event(event: dict[str, Any]) -> None:
    event_type = event.get("type", "unknown")
    stage = event.get("stage")
    if stage is None and event_type == "clarification":
        stage = "qa"
    print(f"\n[EVENT] type={event_type} stage={stage}")

    thoughts = event.get("ui_thoughts") or []
    if thoughts:
        print(f"[THOUGHTS] +{len(thoughts)}")
        for idx, thought in enumerate(thoughts, start=1):
            print(
                f"  {idx}. stage={thought.get('stage')} "
                f"status={thought.get('status')} "
                f"content_type={type(thought.get('content')).__name__}"
            )
    else:
        print("[THOUGHTS] +0")

    message = event.get("message")
    if message:
        print(f"[MESSAGE] {str(message).strip()[:300]}")


def _iter_stream_events(
    initial_stream: Iterable[dict[str, Any]],
    service,
    auto_reply: str | None,
    max_clarifications: int,
):
    queue = deque([initial_stream])
    clarification_count = 0

    while queue:
        stream = queue.popleft()
        for event in stream:
            yield event
            if event.get("type") == "clarification":
                if auto_reply is None:
                    return
                clarification_count += 1
                if clarification_count > max_clarifications:
                    raise RuntimeError("Exceeded clarification auto-reply limit.")
                print(f"[AUTO-REPLY] {auto_reply}")
                queue.append(service.stream_clarification(auto_reply))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run streaming mode and verify ui_thoughts stage emission."
    )
    parser.add_argument(
        "--test-id",
        type=int,
        default=22,
        help="Dataset entry index (1-based). Default: 22 (typically includes diagnose/cleaning).",
    )
    parser.add_argument(
        "--dataset-dir",
        type=str,
        default=str(_repo_root() / "dataset"),
        help="Path to dataset directory (default: ./dataset).",
    )
    parser.add_argument(
        "--auto-reply",
        type=str,
        default="fill with 42",
        help="Auto reply used when clarification is requested. Use empty string to disable.",
    )
    parser.add_argument(
        "--max-clarifications",
        type=int,
        default=5,
        help="Maximum clarification rounds for auto-reply.",
    )
    args = parser.parse_args()

    repo_root = _repo_root()
    sys.path.insert(0, str(repo_root))

    from src.backend.config.settings import Config
    from src.backend.service.sheethero_service import SheetHeroService

    dataset_dir = Path(args.dataset_dir)
    tasks = _load_tasks(dataset_dir)
    task = _select_task(tasks, args.test_id)

    spreadsheets = task.get("spreadsheets", [])
    if not spreadsheets:
        raise ValueError("Selected task has no input spreadsheets.")
    input_paths = _build_input_paths(dataset_dir, spreadsheets)

    prompt = str(task.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("Selected task has empty prompt.")

    config = Config()
    if not config.api_key:
        raise ValueError("OpenAI API key is missing in Config")

    service = SheetHeroService(config=config)
    auto_reply = args.auto_reply if args.auto_reply != "" else None

    print(f"Task: {task.get('task_id', 'Unknown')} - {task.get('title', '')}".strip())
    print(f"Prompt: {prompt}")
    print(f"Input files: {len(input_paths)}")
    for path in input_paths:
        print(f"- {path}")

    seen_stages: set[str] = set()
    thought_count = 0
    final_type = None
    final_message = ""

    initial_stream = service.stream_turn(prompt, input_paths)
    for event in _iter_stream_events(
        initial_stream,
        service=service,
        auto_reply=auto_reply,
        max_clarifications=args.max_clarifications,
    ):
        _print_event(event)
        final_type = str(event.get("type", ""))
        if event.get("message"):
            final_message = str(event.get("message"))
        thoughts = event.get("ui_thoughts") or []
        thought_count += len(thoughts)
        for thought in thoughts:
            stage = thought.get("stage")
            if isinstance(stage, str) and stage:
                seen_stages.add(stage)

    print("\n=== STREAM SUMMARY ===")
    print(f"final_type={final_type}")
    print(f"total_ui_thoughts={thought_count}")
    print(f"seen_stages={sorted(seen_stages)}")
    if final_message:
        print(f"final_message={final_message[:500]}")

    missing = [stage for stage in REQUIRED_STAGES if stage not in seen_stages]
    if thought_count == 0:
        print("FAIL: no ui_thoughts received.")
        return 1
    if missing:
        print(f"FAIL: missing required stages: {missing}")
        return 2
    if final_type not in {"final", "error"}:
        print(f"FAIL: stream terminated without final/error event (last={final_type}).")
        return 3

    print("PASS: stream emitted thought process with all required stages.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
