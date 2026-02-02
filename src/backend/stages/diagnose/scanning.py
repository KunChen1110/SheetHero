"""Early scanning utilities for diagnose stage."""

from __future__ import annotations

import re
from typing import Any, Dict, List

import pandas as pd

_MULTISPACE_RE = re.compile(r"\s{2,}")


def scan_tables(workbook_view: Dict[str, pd.DataFrame],
                max_rows: int = 100,
                max_examples: int = 3) -> List[Dict[str, Any]]:
    """
    Scan all tables and return structured ambiguity findings.

    Returns a list of per-sheet dictionaries:
    {
      "sheet_name": "...",
      "leftmost_column": "...",
      "issues": [
        {
          "column": "...",
          "issue_type": "...",
          "signatures": {...},
          "examples": [{"value": "...", "row_anchor": "..."}]
        },
        ...
      ]
    }
    """
    results: List[Dict[str, Any]] = []
    if not isinstance(workbook_view, dict):
        return results

    for sheet_name, df in workbook_view.items():
        if df is None or not hasattr(df, "columns"):
            continue
        if df.empty or len(df.columns) == 0:
            results.append({
                "sheet_name": sheet_name,
                "leftmost_column": "",
                "issues": [],
            })
            continue

        leftmost_column = str(df.columns[0])
        issues: List[Dict[str, Any]] = []

        for column in df.columns:
            if str(column) == leftmost_column:
                continue
            issues.extend(
                _scan_column_for_ambiguity(
                    sheet_name,
                    df,
                    str(column),
                    leftmost_column,
                    max_rows=max_rows,
                    max_examples=max_examples,
                )
            )

        results.append({
            "sheet_name": sheet_name,
            "leftmost_column": leftmost_column,
            "issues": issues,
        })

    return results


def format_scan_results(scan_results: List[Dict[str, Any]]) -> str:
    """Format scan results into an LLM-friendly report string."""
    lines: List[str] = []

    if not scan_results:
        return "No scan results."

    for sheet in scan_results:
        lines.append(f"Sheet: {sheet.get('sheet_name', '')}")
        lines.append(
            f"Leftmost column (row anchor): {sheet.get('leftmost_column', '')}"
        )
        lines.append("")

        issues = sheet.get("issues") or []
        if not issues:
            lines.append("No potential format inconsistencies detected.")
            lines.append("")
            continue

        lines.append("Detected potential format inconsistencies:")
        lines.append("")

        for idx, issue in enumerate(issues, start=1):
            lines.append("Issue:")
            lines.append(f"- column: {issue.get('column', '')}")
            if issue.get("issue_family"):
                lines.append(f"- family: {issue.get('issue_family', '')}")
            else:
                lines.append(f"- type: {issue.get('issue_type', '')}")

            issue_types = issue.get("issue_types") or []
            if issue_types:
                lines.append(f"- issue_types: {issue_types}")

            signatures = issue.get("signatures") or {}
            if signatures:
                lines.append("- observed_patterns:")
                for key, value in signatures.items():
                    lines.append(f"  - {key}: {value}")

            impact_hint = issue.get("impact_hint")
            if impact_hint:
                lines.append(f"- impact: {impact_hint}")

            lines.append("- examples:")
            for example in issue.get("examples") or []:
                lines.append(
                    f"  - \"{example.get('value', '')}\" "
                    f"({sheet.get('leftmost_column', '')} = "
                    f"{example.get('row_anchor', '')})"
                )
            lines.append("")
            lines.append("Clarification needed:")
            lines.append("-")
            lines.append("")

    return "\n".join(lines).strip()


def compress_scan_results(scan_results: List[Dict[str, Any]],
                          dedup_across_sheets: bool = True,
                          max_examples: int = 3,
                          max_issues_in_summary: int = 3) -> List[Dict[str, Any]]:
    """
    Compress issues per sheet by column name only (no cross-sheet merging).
    """
    issue_family_map = {
        "SEPARATOR_INCONSISTENT": "FORMAT_VARIATION",
        "TOKEN_COUNT_INCONSISTENT": "FORMAT_VARIATION",
        "CASING_INCONSISTENT": "FORMAT_VARIATION",
        "WHITESPACE_INCONSISTENT": "FORMAT_VARIATION",
        "ID_STRUCTURE_INCONSISTENT": "STRUCTURE_VARIATION",
        "EMPTY_VALUE_INCONSISTENT": "EMPTY_VARIATION",
        "NON_EMAIL_VALUE": "INVALID_VALUE",
        "SEMANTIC_MISMATCH": "SCHEMA_CONTAMINATION",
        "VALUE_RANGE_DIFFERENT": "NUMERIC_VARIATION",
    }

    impact_hint = {
        "FORMAT_VARIATION": "may affect grouping or matching",
        "STRUCTURE_VARIATION": "may affect joins or ID matching",
        "EMPTY_VARIATION": "may affect completeness or aggregation",
        "INVALID_VALUE": "may affect validity or correctness",
        "SCHEMA_CONTAMINATION": "may indicate wrong values in this column",
        "NUMERIC_VARIATION": "may affect aggregates or thresholds",
        "OTHER": "",
    }

    compressed: List[Dict[str, Any]] = []
    family_priority = {
        "INVALID_VALUE": 5,
        "SCHEMA_CONTAMINATION": 4,
        "STRUCTURE_VARIATION": 3,
        "NUMERIC_VARIATION": 2,
        "EMPTY_VARIATION": 2,
        "FORMAT_VARIATION": 1,
        "OTHER": 0,
    }

    for sheet in scan_results:
        sheet_name = sheet.get("sheet_name", "")
        leftmost_column = sheet.get("leftmost_column", "")
        issues = sheet.get("issues") or []
        by_column: Dict[str, Dict[str, Any]] = {}

        for issue in issues:
            col = issue.get("column", "")
            if not col:
                continue
            issue_type = issue.get("issue_type", "") or "OTHER"
            family = issue_family_map.get(issue_type, "OTHER")
            item = by_column.get(col)
            if item is None:
                item = by_column[col] = {
                    "column": col,
                    "issue_types": set(),
                    "issue_families": set(),
                    "signatures": {},
                    "examples": [],
                }

            item["issue_types"].add(issue_type)
            item["issue_families"].add(family)
            _merge_signatures(item["signatures"], issue.get("signatures") or {})
            item["examples"] = _merge_examples_dedup(
                item["examples"],
                issue.get("examples") or [],
                max_examples,
            )

        if not by_column:
            continue

        sheet_issues: List[Dict[str, Any]] = []
        for col, item in by_column.items():
            families = sorted(item.get("issue_families", set()))
            top_family = max(
                families,
                key=lambda family: family_priority.get(family, 0),
            ) if families else "OTHER"
            issue_types = sorted(item.get("issue_types", set()))
            issue_type_families = {
                issue_type: issue_family_map.get(issue_type, "OTHER")
                for issue_type in issue_types
            }
            main_issue_types = [
                issue_type
                for issue_type, family in issue_type_families.items()
                if family not in {"NUMERIC_VARIATION", "EMPTY_VARIATION"}
            ]
            side_issue_types = [
                issue_type
                for issue_type, family in issue_type_families.items()
                if family in {"NUMERIC_VARIATION", "EMPTY_VARIATION"}
            ]

            def _compress_main_types(types: list[str]) -> list[str]:
                families_present = {issue_family_map.get(t, "OTHER") for t in types}
                if "INVALID_VALUE" in families_present:
                    return [t for t in types if issue_family_map.get(t, "OTHER") == "INVALID_VALUE"]
                if "SCHEMA_CONTAMINATION" in families_present:
                    return [
                        t for t in types
                        if issue_family_map.get(t, "OTHER") in {"SCHEMA_CONTAMINATION", "STRUCTURE_VARIATION"}
                    ]
                if "STRUCTURE_VARIATION" in families_present:
                    return [t for t in types if issue_family_map.get(t, "OTHER") == "STRUCTURE_VARIATION"]
                return types

            compressed_main_types = _compress_main_types(main_issue_types)
            compressed_types = sorted(set(compressed_main_types + side_issue_types))
            compressed_families = sorted({issue_family_map.get(t, "OTHER") for t in compressed_types})
            top_family = max(
                compressed_families,
                key=lambda family: family_priority.get(family, 0),
            ) if compressed_families else "OTHER"

            sheet_issues.append({
                "column": col,
                "issue_family": top_family,
                "issue_families": compressed_families,
                "issue_types": compressed_types,
                "signatures": item.get("signatures", {}),
                "examples": item.get("examples", []),
                "impact_hint": impact_hint.get(top_family, ""),
            })

        sheet_issues.sort(key=lambda issue: issue.get("column", ""))
        sheet_issues = sheet_issues[:max_issues_in_summary]
        sheet_issues = _finalize_issues(sheet_issues)
        compressed.append({
            "sheet_name": sheet_name,
            "leftmost_column": leftmost_column,
            "issues": sheet_issues,
        })

    return _finalize_compressed(compressed)


def _scan_column_for_ambiguity(sheet_name: str,
                               df: pd.DataFrame,
                               column: str,
                               leftmost_column: str,
                               max_rows: int = 100,
                               max_examples: int = 3) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    if column not in df.columns or leftmost_column not in df.columns:
        return issues

    col_series = df[column]
    anchor_series = df[leftmost_column]

    seen = {
        "separators": set(),
        "token_counts": set(),
        "case_categories": set(),
        "has_leading_trailing_space": set(),
        "alnum_patterns": set(),
        "is_empty": set(),
        "email_valid": set(),
        "name_like": set(),
    }

    examples: List[Dict[str, Any]] = []
    empty_examples: List[Dict[str, Any]] = []
    non_empty_examples: List[Dict[str, Any]] = []
    non_empty_values: List[str] = []
    non_empty_seen = 0

    column_lower = str(column).strip().lower()
    check_email = _column_has_keyword(column_lower, {"email", "e-mail"})
    check_contamination = _column_has_keyword(
        column_lower,
        {"department", "dept", "program", "course", "subject", "major", "role", "position"},
    )

    for idx, value in enumerate(col_series):
        if idx >= max_rows:
            break

        raw = value
        if raw is None or (isinstance(raw, float) and pd.isna(raw)):
            seen["is_empty"].add(True)
            _maybe_add_example(empty_examples, max_examples, "(empty)", anchor_series, idx)
            continue

        text = str(raw)
        if text.strip() == "":
            seen["is_empty"].add(True)
            _maybe_add_example(empty_examples, max_examples, "(empty)", anchor_series, idx)
            continue

        seen["is_empty"].add(False)
        non_empty_seen += 1

        stripped = text.strip()
        non_empty_values.append(stripped)

        # separators
        if " " in stripped:
            seen["separators"].add("space")
        if "-" in stripped:
            seen["separators"].add("hyphen")
        if "/" in stripped:
            seen["separators"].add("slash")
        if "," in stripped:
            seen["separators"].add("comma")
        if all(sep not in stripped for sep in (" ", "-", "/", ",")):
            seen["separators"].add("none")

        # token count
        token_count = len([t for t in stripped.split() if t])
        seen["token_counts"].add(token_count)

        # casing
        letters = "".join(ch for ch in stripped if ch.isalpha())
        if letters:
            if letters.isupper():
                seen["case_categories"].add("upper")
            elif letters.islower():
                seen["case_categories"].add("lower")
            elif letters.istitle():
                seen["case_categories"].add("title")
            else:
                seen["case_categories"].add("mixed")

        # whitespace
        seen["has_leading_trailing_space"].add(text != stripped or bool(_MULTISPACE_RE.search(text)))

        # ID-like pattern (A for alpha, D for digit, X for other)
        pattern = []
        for ch in stripped:
            if ch.isalpha():
                pattern.append("A")
            elif ch.isdigit():
                pattern.append("D")
            else:
                pattern.append("X")
        seen["alnum_patterns"].add("".join(pattern))

        if check_email:
            seen["email_valid"].add(_looks_like_email(stripped))
        if check_contamination:
            seen["name_like"].add(_looks_like_person_name(stripped))

        _maybe_add_example(non_empty_examples, max_examples, stripped, anchor_series, idx)

        if _early_stop(seen, column, non_empty_values):
            break

    if non_empty_seen == 0:
        return issues

    if len(seen["is_empty"]) > 1:
        examples = _merge_empty_examples(
            empty_examples,
            non_empty_examples,
            max_examples,
        )
        issues.append(_new_issue(
            sheet_name,
            column,
            "EMPTY_VALUE_INCONSISTENT",
            {},
            examples,
        ))

    is_structural = _is_structural_column(column, non_empty_values)
    is_numeric = _is_numeric_column(non_empty_values)

    if is_structural and len(seen["separators"]) > 1:
        examples = _merge_examples(non_empty_examples, max_examples)
        issues.append(_new_issue(
            sheet_name,
            column,
            "SEPARATOR_INCONSISTENT",
            {"separators": sorted(seen["separators"])},
            examples,
        ))

    if is_structural and len(seen["token_counts"]) > 1:
        examples = _merge_examples(non_empty_examples, max_examples)
        issues.append(_new_issue(
            sheet_name,
            column,
            "TOKEN_COUNT_INCONSISTENT",
            {"token_counts": sorted(seen["token_counts"])},
            examples,
        ))

    if is_structural and len(seen["case_categories"]) > 1:
        examples = _merge_examples(non_empty_examples, max_examples)
        issues.append(_new_issue(
            sheet_name,
            column,
            "CASING_INCONSISTENT",
            {"case_categories": sorted(seen["case_categories"])},
            examples,
        ))

    if _should_flag_whitespace(non_empty_values, seen):
        examples = _merge_examples(non_empty_examples, max_examples)
        issues.append(_new_issue(
            sheet_name,
            column,
            "WHITESPACE_INCONSISTENT",
            {},
            examples,
        ))

    if (not is_numeric) and is_structural and _should_check_id_structure(non_empty_values) and len(seen["alnum_patterns"]) > 1:
        examples = _merge_examples(non_empty_examples, max_examples)
        issues.append(_new_issue(
            sheet_name,
            column,
            "ID_STRUCTURE_INCONSISTENT",
            {
                "patterns": sorted(seen["alnum_patterns"]),
                "normalized": sorted(_normalize_patterns(seen["alnum_patterns"])),
            },
            examples,
        ))

    if is_numeric and len({value.strip() for value in non_empty_values}) > 1:
        examples = _merge_examples(non_empty_examples, max_examples)
        issues.append(_new_issue(
            sheet_name,
            column,
            "VALUE_RANGE_DIFFERENT",
            {},
            examples,
        ))

    if check_email and False in seen["email_valid"]:
        examples = _merge_examples(non_empty_examples, max_examples)
        issues.append(_new_issue(
            sheet_name,
            column,
            "NON_EMAIL_VALUE",
            {},
            examples,
        ))

    if check_contamination and True in seen["name_like"] and False in seen["name_like"]:
        examples = _merge_examples(non_empty_examples, max_examples)
        issues.append(_new_issue(
            sheet_name,
            column,
            "SEMANTIC_MISMATCH",
            {},
            examples,
        ))

    return issues


def _new_issue(sheet_name: str,
               column: str,
               issue_type: str,
               signatures: Dict[str, Any],
               examples: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "sheet": sheet_name,
        "column": column,
        "issue_type": issue_type,
        "signatures": signatures,
        "examples": list(examples),
    }


def _maybe_add_example(examples: List[Dict[str, Any]],
                       max_examples: int,
                       value: str,
                       anchor_series: pd.Series,
                       idx: int) -> None:
    if len(examples) >= max_examples:
        return
    if any(example.get("value") == value for example in examples):
        return
    try:
        anchor_value = anchor_series.iloc[idx]
    except Exception:
        anchor_value = ""
    examples.append({
        "value": value,
        "row_anchor": "" if anchor_value is None else str(anchor_value),
    })


def _early_stop(seen: Dict[str, Any], column: str, non_empty_values: List[str]) -> bool:
    is_structural = _is_structural_column(column, non_empty_values)
    check_id_structure = is_structural and _should_check_id_structure(non_empty_values)
    return (
        len(seen["is_empty"]) > 1
        or (is_structural and len(seen["separators"]) > 1)
        or (is_structural and len(seen["token_counts"]) > 1)
        or (is_structural and len(seen["case_categories"]) > 1)
        or (True in seen["has_leading_trailing_space"]
            and False in seen["has_leading_trailing_space"])
        or (check_id_structure and len(seen["alnum_patterns"]) > 1)
    )


def _should_check_id_structure(values: List[str]) -> bool:
    if not values:
        return False
    def _is_alpha_space(value: str) -> bool:
        stripped = value.strip()
        if not stripped:
            return False
        return all(ch.isalpha() or ch.isspace() for ch in stripped)

    if all(_is_alpha_space(value) for value in values):
        return False
    if all(value.isalpha() for value in values):
        lengths = {len(value) for value in values}
        if lengths and (max(lengths) - min(lengths)) >= 3:
            return False
    return True


def _normalize_whitespace(value: str) -> str:
    return " ".join(value.strip().split())


def _should_flag_whitespace(values: List[str], seen: Dict[str, Any]) -> bool:
    if not values:
        return False
    if not (True in seen["has_leading_trailing_space"] and False in seen["has_leading_trailing_space"]):
        return False
    normalized = {_normalize_whitespace(value) for value in values if value.strip()}
    return len(normalized) == 1


def _column_has_keyword(column_lower: str, keywords: set[str]) -> bool:
    for keyword in keywords:
        if keyword in column_lower:
            return True
    return False


def _looks_like_email(value: str) -> bool:
    if "@" not in value:
        return False
    local, _, domain = value.partition("@")
    if not local or "." not in domain:
        return False
    if any(ch.isspace() for ch in value):
        return False
    return True


def _looks_like_person_name(value: str) -> bool:
    if not value:
        return False
    if any(ch.isdigit() for ch in value):
        return False
    tokens = [token for token in value.replace("-", " ").split() if token]
    if len(tokens) < 2:
        return False
    if len(tokens) > 4:
        return False
    for token in tokens:
        clean = token.strip(".")
        if not clean:
            return False
        if not clean[0].isalpha():
            return False
        if not clean[0].isupper():
            return False
        if any(ch in "@_/" for ch in clean):
            return False
    return True


def _is_numeric_column(values: List[str]) -> bool:
    if not values:
        return False
    for value in values:
        text = value.strip()
        if not text:
            continue
        try:
            float(text.replace(",", ""))
        except ValueError:
            return False
    return True


def _is_structural_column(column: str, values: List[str]) -> bool:
    if not values:
        return False
    strong_symbols = {"@", "_", "/", ":", "#"}
    score = 0
    total_len = 0

    column_lower = (column or "").strip().lower()
    natural_keywords = {
        "name", "department", "program", "course", "subject", "major",
        "title", "role", "position", "city", "state", "country",
    }
    structural_keywords = {
        "id", "code", "email", "room", "phone", "tel", "zip",
        "postal", "ssn", "number", "ref", "key",
    }
    if any(keyword in column_lower for keyword in structural_keywords):
        score += 2
    if any(keyword in column_lower for keyword in natural_keywords):
        score -= 2

    for value in values:
        total_len += len(value)
        if any(ch.isdigit() for ch in value):
            score += 2
        if any(ch in strong_symbols for ch in value):
            score += 2
        stripped = value.strip()
        if stripped and all(ch.isalpha() or ch.isspace() or ch in {".", "-"} for ch in stripped):
            score -= 1
    avg_len = total_len / max(len(values), 1)
    if avg_len > 15:
        score -= 1
    return score >= 2


def _merge_empty_examples(empty_examples: List[Dict[str, Any]],
                          non_empty_examples: List[Dict[str, Any]],
                          max_examples: int) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    for example in empty_examples:
        if len(merged) >= max_examples:
            break
        merged.append(example)
    for example in non_empty_examples:
        if len(merged) >= max_examples:
            break
        merged.append(example)
    return merged


def _merge_examples(examples: List[Dict[str, Any]],
                    max_examples: int) -> List[Dict[str, Any]]:
    return list(examples)[:max_examples]


def _merge_examples_dedup(existing: List[Dict[str, Any]],
                          incoming: List[Dict[str, Any]],
                          max_examples: int) -> List[Dict[str, Any]]:
    merged = list(existing)
    for example in incoming:
        if len(merged) >= max_examples:
            break
        value = example.get("value")
        key = str(value).strip().lower() if value is not None else ""
        if any(str(item.get("value")).strip().lower() == key for item in merged):
            continue
        merged.append(example)
    return merged


def _merge_signatures(dst: Dict[str, Any], src: Dict[str, Any]) -> None:
    for key, value in src.items():
        if key not in dst:
            if isinstance(value, (list, set, tuple)):
                dst[key] = set(value)
            else:
                dst[key] = {value}
        else:
            if isinstance(value, (list, set, tuple)):
                dst[key].update(value)
            else:
                dst[key].add(value)


def _finalize_signatures(signatures: Dict[str, Any]) -> Dict[str, Any]:
    finalized = {}
    for key, value in signatures.items():
        if isinstance(value, set):
            finalized[key] = sorted(value)
        else:
            finalized[key] = value
    return finalized


def _finalize_issues(issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    finalized = []
    for issue in issues:
        issue = dict(issue)
        issue["signatures"] = _finalize_signatures(issue.get("signatures", {}))
        for value in issue.get("signatures", {}).values():
            assert not isinstance(value, set), "signature still contains set"
        issue_types = issue.get("issue_types", [])
        issue["issue_types"] = sorted(issue_types)
        finalized.append(issue)
    return finalized


def _finalize_compressed(compressed: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    finalized = []
    for sheet in compressed:
        sheet = dict(sheet)
        sheet["issues"] = _finalize_issues(sheet.get("issues", []))
        finalized.append(sheet)
    return finalized


def _normalize_patterns(patterns: set) -> set:
    normalized = set()
    for pattern in patterns:
        if not pattern:
            continue
        compact = []
        last = None
        for ch in pattern:
            if ch != last:
                compact.append(ch)
                last = ch
        normalized.add("".join(compact))
    return normalized
