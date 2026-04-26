from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .environment.sandbox.sandbox import Sandbox
from .router.diagnose_router import DiagnoseRouter


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BENCHMARK_ROOT = (
    PROJECT_ROOT
    / "dataset"
    / "DiagnoseBenchmark"
    / "SpreadsheetDiagnosisData"
)
DEFAULT_TEMP_OUTPUT_PATH = Path(os.getenv("TMPDIR", "/tmp")) / "sheethero_diagnose_benchmark_output.xlsx"


@dataclass
class ExpectedIssue:
    table: str
    issue_type: str
    description: str
    business_context: str
    locations: list[str]


def _load_issue_json(path: Path) -> list[ExpectedIssue]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_items = payload if isinstance(payload, list) else [payload]
    results: list[ExpectedIssue] = []
    for item in raw_items:
        locations = item.get("locations")
        if locations is None and item.get("location"):
            locations = [str(item["location"])]
        results.append(
            ExpectedIssue(
                table=str(item.get("table", "")),
                issue_type=str(item.get("issue_type", "")),
                description=str(item.get("description", "")),
                business_context=str(item.get("business_context", "")),
                locations=[str(value) for value in (locations or [])],
            )
        )
    return results


def _benchmark_question(expected_issues: list[ExpectedIssue]) -> str:
    contexts = [
        issue.business_context.strip()
        for issue in expected_issues
        if issue.business_context.strip()
    ]
    context_text = " ".join(dict.fromkeys(contexts))
    base = (
        "Please inspect these spreadsheet tables for data quality issues that would affect "
        "cleaning, matching, grouping, totals, averages, and downstream reporting. "
        "Identify missing values, inconsistencies, shifted rows, or implausible values that should be clarified."
    )
    if context_text:
        return f"{base} Business context: {context_text}"
    return base


def _expected_to_detected_family(issue_type: str) -> set[str]:
    normalized = issue_type.strip().lower()
    if normalized == "missing":
        return {"missing_value", "missing_key_column"}
    if normalized == "inconsistency":
        return {
            "format_inconsistency",
            "unit_or_time_format",
            "row_alignment",
            "duplicate_conflicting_rows",
        }
    if normalized == "semantic_anomaly":
        return {"semantic_anomaly"}
    return {normalized}


def _evaluate_case(expected: list[ExpectedIssue], detected: list[dict[str, Any]]) -> tuple[int, int]:
    detected_types = [str(issue.get("issue_type", "")) for issue in detected]
    matched = 0
    for issue in expected:
        acceptable = _expected_to_detected_family(issue.issue_type)
        if any(detected_type in acceptable for detected_type in detected_types):
            matched += 1
    return matched, len(expected)


def _render_expected(issue: ExpectedIssue) -> str:
    lines = [
        f"- table: `{issue.table}`",
        f"  - issue_type: `{issue.issue_type}`",
    ]
    if issue.locations:
        lines.append(f"  - locations: {', '.join(issue.locations)}")
    if issue.description:
        lines.append(f"  - description: {issue.description}")
    return "\n".join(lines)


def _render_detected(issue: dict[str, Any]) -> str:
    metadata = issue.get("metadata") or {}
    lines = [
        f"- issue_type: `{issue.get('issue_type', '')}`",
        f"  - question: {issue.get('question', '')}",
    ]
    if metadata.get("sheet_key"):
        lines.append(f"  - sheet_key: `{metadata['sheet_key']}`")
    details = str(issue.get("details_markdown") or "").strip()
    if details:
        lines.append("  - preview:")
        for detail_line in details.splitlines():
            lines.append(f"    {detail_line}")
    return "\n".join(lines)


def _collect_cases(root: Path, split: str) -> list[Path]:
    if split == "all":
        case_dirs = sorted(root.glob("dataset_*/*"))
    else:
        case_dirs = sorted((root / split).glob("case*"))
    return [path for path in case_dirs if path.is_dir()]


def _run_case(case_dir: Path) -> dict[str, Any]:
    csv_paths = sorted(case_dir.glob("table*.csv"))
    if not csv_paths:
        raise ValueError(f"No CSV tables found in {case_dir}")

    expected = _load_issue_json(case_dir / "issue.json")
    question = _benchmark_question(expected)

    sandbox = Sandbox(
        excel_paths=[str(path) for path in csv_paths],
        output_preferences={"mode": "text", "file_path": None},
        output_path=str(DEFAULT_TEMP_OUTPUT_PATH),
        enabled_namespaces=["spreadsheet"],
        load_excel=True,
    )
    workbook_view = sandbox.get_workbook_view()
    detected = DiagnoseRouter._detect_blocking_data_issues(workbook_view, question)
    matched, total = _evaluate_case(expected, detected)
    return {
        "case_name": case_dir.name,
        "question": question,
        "expected": expected,
        "detected": detected,
        "matched": matched,
        "expected_total": total,
        "input_files": [path.name for path in csv_paths],
    }


def _build_report(results: list[dict[str, Any]], split: str) -> str:
    total_expected = sum(item["expected_total"] for item in results)
    total_matched = sum(item["matched"] for item in results)
    lines = [
        "# Diagnose Benchmark Report",
        "",
        f"- Split: `{split}`",
        f"- Cases evaluated: `{len(results)}`",
        f"- Loose expected-family matches: `{total_matched}/{total_expected}`",
        "",
        "> Note: this is a diagnose/QA benchmark, not an end-to-end task benchmark.",
        "> Matching uses loose issue-family mapping rather than exact label equality.",
        "",
    ]

    for item in results:
        lines.extend([
            f"## {item['case_name']}",
            "",
            f"- Input files: {', '.join(f'`{name}`' for name in item['input_files'])}",
            f"- Loose expected-family matches: `{item['matched']}/{item['expected_total']}`",
            f"- Benchmark prompt: {item['question']}",
            "",
            "### Expected Issues",
        ])
        for expected_issue in item["expected"]:
            lines.append(_render_expected(expected_issue))
        if not item["expected"]:
            lines.append("- none")

        lines.extend(["", "### Detected Issues"])
        if item["detected"]:
            for detected_issue in item["detected"]:
                lines.append(_render_detected(detected_issue))
        else:
            lines.append("- none")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def build_default_diagnose_report_path(split: str) -> Path:
    return (
        PROJECT_ROOT
        / "artifacts"
        / "test_report"
        / "diagnose_benchmark"
        / f"latest_{split}.md"
    )


def run_diagnose_benchmark(
    benchmark_root: str | Path | None = None,
    split: str = "dataset_small",
    limit: int = 0,
    report_path: str | Path | None = None,
) -> dict[str, Any]:
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/mpl")
    resolved_root = Path(benchmark_root or DEFAULT_BENCHMARK_ROOT).resolve()
    if not resolved_root.exists():
        raise FileNotFoundError(f"Benchmark root not found: {resolved_root}")

    cases = _collect_cases(resolved_root, split)
    if limit > 0:
        cases = cases[:limit]
    if not cases:
        raise ValueError(f"No cases found under {resolved_root} for split {split}")

    results = [_run_case(case_dir) for case_dir in cases]
    report = _build_report(results, split)

    resolved_report_path = Path(report_path).resolve() if report_path else build_default_diagnose_report_path(split)
    resolved_report_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_report_path.write_text(report, encoding="utf-8")

    total_matched = sum(item["matched"] for item in results)
    total_expected = sum(item["expected_total"] for item in results)
    return {
        "report_path": str(resolved_report_path),
        "cases_evaluated": len(results),
        "matched": total_matched,
        "expected_total": total_expected,
        "split": split,
        "results": results,
    }
