"""Frontend-facing backend config schema.

Keep UI-editable settings separate from the full backend runtime config so the
frontend only depends on a small, stable surface.
"""

from __future__ import annotations

from typing import Any, Dict


FRONTEND_DEPLOYMENT_CHOICES = [
    "gpt-4o-mini",
    "gpt-4-32k",
    "gpt-4",
    "gpt-4o",
    "qwen3:8b",
    "qwen2.5:7b-instruct",
    "qwen2.5-coder:7b-instruct",
    "qwen2.5-coder:14b-instruct",
]


def build_frontend_defaults(deployment: str, max_turns: int, enable_diagnose: bool) -> Dict[str, Any]:
    """Return only the config values the frontend is allowed to edit."""
    return {
        "api_key": "",
        "base_url": None,
        "deployment": deployment,
        "max_turns": max_turns,
        "enable_diagnose": enable_diagnose,
    }


def build_frontend_schema(
    defaults: Dict[str, Any],
    *,
    timeout: int,
    max_qa_rounds: int,
    total_token_budget: int,
    max_retries: int,
) -> Dict[str, Dict[str, Any]]:
    """Describe which backend config fields are frontend-editable."""
    return {
        "api_key": {
            "label": "API Key",
            "type": "password",
            "default": defaults["api_key"],
            "frontend_editable": True,
            "required_when": "base_url is empty",
        },
        "base_url": {
            "label": "Base URL",
            "type": "string",
            "default": defaults["base_url"],
            "frontend_editable": True,
            "required_when": "api_key is empty for local/OpenAI-compatible servers",
        },
        "deployment": {
            "label": "Model",
            "type": "choice",
            "default": defaults["deployment"],
            "choices": FRONTEND_DEPLOYMENT_CHOICES,
            "frontend_editable": True,
        },
        "max_turns": {
            "label": "Max Turns",
            "type": "int",
            "default": defaults["max_turns"],
            "minimum": 1,
            "maximum": 10,
            "frontend_editable": True,
        },
        "enable_diagnose": {
            "label": "Enable Diagnose",
            "type": "bool",
            "default": defaults["enable_diagnose"],
            "frontend_editable": True,
        },
        "output_mode": {
            "label": "Output Mode",
            "type": "internal",
            "default": "file",
            "frontend_editable": False,
        },
        "output_file": {
            "label": "Output File",
            "type": "internal",
            "default": None,
            "frontend_editable": False,
        },
        "timeout": {
            "label": "Timeout",
            "type": "internal",
            "default": timeout,
            "frontend_editable": False,
        },
        "max_qa_rounds": {
            "label": "Max QA Rounds",
            "type": "internal",
            "default": max_qa_rounds,
            "frontend_editable": False,
        },
        "total_token_budget": {
            "label": "Token Budget",
            "type": "internal",
            "default": total_token_budget,
            "frontend_editable": False,
        },
        "max_retries": {
            "label": "Max Retries",
            "type": "internal",
            "default": max_retries,
            "frontend_editable": False,
        },
    }
