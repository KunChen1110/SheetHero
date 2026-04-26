"""
loader.py — reads task info from dataset.json and SheetHero logger files.
"""

import json
import os


def load_task_from_dataset(task_id: str, dataset_path: str) -> dict:
    """Load a task entry from dataset.json by task_id e.g. 'Test 1'."""
    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)
    for entry in dataset:
        if entry.get("task_id", "").strip().lower() == task_id.strip().lower():
            return entry
    raise ValueError(f"Task '{task_id}' not found in {dataset_path}")


def extract_output_from_logger(logger_path: str) -> dict:
    """
    Parse a SheetHero logger .md file and extract:
      - output_text:  Short Answer (new format) or last meaningful Final Answer (old format)
      - output_excel: the saved output .xlsx path

    New format has: 'Short Answer: <summary>'
    Old format has: 'Final Answer: <text or file path>'
    """
    output_text = ""
    output_excel = ""

    with open(logger_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for line in lines:
        stripped = line.strip()

        # New format: Short Answer is always the human-readable summary
        if stripped.startswith("Short Answer:"):
            output_text = stripped.split(":", 1)[1].strip()

        # Both formats: grab Excel file path from Final Answer line
        if stripped.startswith("Final Answer:"):
            value = stripped.split(":", 1)[1].strip()
            if value.lower().endswith(".xlsx") or value.lower().endswith(".xls"):
                output_excel = value
            elif not output_text and not os.path.splitext(value)[1]:
                # Old format fallback: use as text if it is not a file path
                output_text = value

    return {"output_text": output_text, "output_excel": output_excel}


def find_latest_logger(task_id: str) -> str:
    """
    Find the most recent logger .md file for a given task.
    e.g. task_id "Test 1" -> looks for files containing "tc01" in logger dirs.
    """
    import re
    match = re.search(r"\d+", task_id)
    if match:
        num = int(match.group())
        prefix = f"tc{num:02d}"
    else:
        prefix = ""

    script_dir = os.path.dirname(os.path.abspath(__file__))
    search_dirs = [
        os.path.join(script_dir, "../../artifacts/loggers"),
        os.path.join(script_dir, "../../artifacts/logger"),
        os.path.join(script_dir, "../../artifacts/logs"),
        os.path.join(script_dir, "artifacts/loggers"),
        os.path.join(script_dir, "artifacts/logger"),
        os.path.join(script_dir, "artifacts/logs"),
        "artifacts/loggers",
        "artifacts/logger",
        "artifacts/logs",
    ]

    candidates = []
    for d in search_dirs:
        if not os.path.isdir(d):
            continue
        for fname in os.listdir(d):
            if fname.endswith(".md") and (not prefix or prefix in fname.lower()):
                candidates.append(os.path.join(d, fname))

    if not candidates:
        raise FileNotFoundError(
            f"No logger file found for task '{task_id}' "
            f"(looked for files containing '{prefix}' in logger dirs)"
        )

    # Return the most recently modified one
    return max(candidates, key=os.path.getmtime)


def find_dataset() -> str:
    """Search common locations for dataset.json."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    search_paths = [
        os.path.join(script_dir, "dataset.json"),
        os.path.join(script_dir, "../../dataset/DevelopmentBenchmark/dataset.json"),
        "dataset.json",
    ]
    for p in search_paths:
        if os.path.exists(p):
            return p
    raise FileNotFoundError("dataset.json not found. Pass --dataset <path> to specify it.")
