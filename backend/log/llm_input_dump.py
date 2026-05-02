"""Dump LLM call inputs to a dedicated log file under artifacts/loggers/."""

from __future__ import annotations

import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

_lock = threading.Lock()
_counter = 0
_file_handle: Optional[Any] = None
_file_path: Optional[Path] = None


def _enabled() -> bool:
    flag = os.getenv("SHEETHERO_DUMP_LLM_INPUT", "1").strip().lower()
    return flag not in {"0", "false", "no", "off", ""}


def _ensure_file() -> Optional[Any]:
    global _file_handle, _file_path
    if _file_handle is not None:
        return _file_handle

    log_dir = Path("artifacts/loggers").resolve()
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    _file_path = log_dir / f"llm_{timestamp}.md"
    _file_handle = open(_file_path, "w", encoding="utf-8")
    _file_handle.write(f"# LLM Input Log\n\n")
    _file_handle.write(
        f"**Session started:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    )
    _file_handle.write("---\n\n")
    _file_handle.flush()
    return _file_handle


def dump_llm_input(deployment: str, messages: list, **kwargs: Any) -> None:
    if not _enabled():
        return

    global _counter
    with _lock:
        handle = _ensure_file()
        if handle is None:
            return
        _counter += 1
        idx = _counter

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        handle.write(f"## [#{idx}] {now} — model: `{deployment}`\n\n")
        if kwargs:
            handle.write(f"**kwargs:** `{kwargs}`\n\n")
        handle.write(f"**messages ({len(messages)}):**\n\n")
        for i, msg in enumerate(messages):
            role = msg.get("role", "?") if isinstance(msg, dict) else "?"
            content = msg.get("content", "") if isinstance(msg, dict) else str(msg)
            if isinstance(content, list):
                content = "".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in content
                )
            handle.write(f"### [{i}] {role}\n\n")
            handle.write("```\n")
            handle.write(str(content))
            handle.write("\n```\n\n")
        handle.write("---\n\n")
        handle.flush()
