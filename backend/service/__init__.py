"""Stable service-layer exports.

This package is the intended integration boundary for UI callers.

- `SheetHeroService` provides request/clarification submission on top of the
  full backend pipeline.
- `StreamDialogueDriver` wraps the service when the caller needs streaming
  progress events instead of a single final response.

Frontend code should import these exports either from this package or from
the top-level `backend` package, not from deeper runtime/stage modules.
"""

from .sheethero_service import SheetHeroService
from .stream_dialogue_driver import StreamDialogueDriver

__all__ = ["SheetHeroService", "StreamDialogueDriver"]
