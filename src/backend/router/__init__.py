"""Stable routing exports.

`DiagnoseRouter` decides whether a task should enter diagnose/QA based on
data evidence first, with narrow deterministic fallbacks. External callers do
not need any deeper router modules than these exports.
"""

from .diagnose_router import DiagnoseRouter, DiagnoseDecision

__all__ = ["DiagnoseRouter", "DiagnoseDecision"]
