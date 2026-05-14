"""AST-based checks for dependency-scheduling helper usage."""

from __future__ import annotations

import ast
from typing import Dict, Optional


def subscript_key(node: ast.Subscript) -> Optional[str]:
    slice_node = node.slice
    if isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, str):
        return slice_node.value
    index_type = getattr(ast, "Index", None)
    if index_type is not None and isinstance(slice_node, index_type):
        value = getattr(slice_node, "value", None)
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            return value.value
    return None


def classify_schedule_source(node: ast.AST, assigned_kinds: Dict[str, str]) -> Optional[str]:
    if isinstance(node, ast.Subscript):
        if isinstance(node.value, ast.Name) and subscript_key(node) == "df":
            return "selector_df"
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "pd"
        and node.func.attr == "DataFrame"
    ):
        return "reconstructed_df"
    if isinstance(node, ast.Name):
        return assigned_kinds.get(node.id)
    return None


def inspect_schedule_helper_sources(code: str) -> Optional[str]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None

    assigned_kinds: Dict[str, str] = {}
    for node in ast.walk(tree):
        value = None
        if isinstance(node, ast.Assign):
            value = node.value
            targets = node.targets
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            value = node.value
            targets = [node.target]
        else:
            continue

        if value is None:
            continue

        kind = classify_schedule_source(value, assigned_kinds)
        if kind is None:
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                assigned_kinds[target.id] = kind

    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "build_dependency_schedule"
        ):
            continue
        if len(node.args) < 2:
            return "missing_args"
        task_kind = classify_schedule_source(node.args[0], assigned_kinds)
        dep_kind = classify_schedule_source(node.args[1], assigned_kinds)
        if task_kind == "reconstructed_df" or dep_kind == "reconstructed_df":
            return "reconstructed_df"
        if task_kind != "selector_df" or dep_kind != "selector_df":
            return "non_selector_df"
    return None
