"""Execution stage package.

Layout:

- `stage.py` / `runtime.py`:
  public facade and main execution control loop.
- `core/`:
  low-level execution runtime helpers such as parser, llm client, executor,
  history, and summary objects.
- `analysis/`:
  pure analysis helpers used by runtime to classify requests or inspect code
  structure without mutating execution state.
- `guards/`:
  bounded-execution guardrails, repair hints, output-contract checks, and
  loop-breaker templates.

External callers should keep importing `ExecutionStage` from
`src/backend/stages/execution/stage.py` rather than relying on deeper files.
"""

from .stage import ExecutionStage

__all__ = ["ExecutionStage"]
