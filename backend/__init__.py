"""Stable public backend entrypoints.

Import only from this module in the frontend or other external callers.

Recommended usage:
- `ConfigFactory.get_frontend_defaults()`:
  source of truth for UI defaults.
- `ConfigFactory.get_frontend_schema()`:
  source of truth for which config fields the UI may edit.
- `SheetHeroService`:
  preferred runtime entrypoint for the GUI because it supports the
  full multi-stage flow, including diagnose, QA, cleaning, execution,
  validation, and clarification replies.
- `StreamDialogueDriver`:
  optional wrapper when the caller wants streaming events.

Internal modules such as stage runtimes, workflow helpers, and sandbox
namespaces should not be imported directly by the frontend. Those remain
implementation details and may change without preserving API stability.
"""

from .agent import SheetHero
from .config.settings import Config, ConfigFactory
from .service import SheetHeroService, StreamDialogueDriver

__all__ = [
    "SheetHero",
    "Config",
    "ConfigFactory",
    "SheetHeroService",
    "StreamDialogueDriver",
]
