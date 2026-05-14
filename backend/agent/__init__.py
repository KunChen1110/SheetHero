"""Stable agent-layer exports.

This package is intentionally narrow:

- `SheetHero` is the only agent object external callers should instantiate
  directly in backend-only contexts.

Most callers, especially the frontend, should still prefer
`backend.SheetHeroService` instead of importing from this package. The
service layer preserves the full multi-stage flow and avoids bypassing
session, QA, diagnose, and clarification handling.
"""

from .core.SheetHero import SheetHero

__all__ = ["SheetHero"]
